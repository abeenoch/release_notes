from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"


class ReleaseAlreadyExistsError(ValueError):
    """GitHub already has a release for this tag (create returned 422/409).

    Subclasses ValueError so callers that already handle bad-input paths keep
    working, while being specific enough to treat as "already published".
    """


def _is_already_exists(response) -> bool:
    """True only when GitHub's errors payload says already_exists.

    A 422/409 alone proves nothing — e.g. `pre_receive ... tag names ... are
    not allowed` and `Published releases must have a valid tag` are validation
    rejections, not duplicates. Treating those as "already published" produced
    the lie "A release already exists" for releases that don't.
    """
    try:
        data = response.json()
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    return any(
        isinstance(err, dict) and err.get("code") == "already_exists"
        for err in data.get("errors") or []
    )


class GitHubApiError(RuntimeError):
    """A GitHub API call failed, carrying the HTTP status for mapping.

    `detail` is a short human-readable summary safe to show a user — never the
    raw httpx repr (which leaks request plumbing and reads like a crash).
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _detail_from_errors(response) -> str | None:
    """Prefer GitHub's own explanation (errors[].message) when it has one.

    e.g. a rejected release create says exactly why: "Published releases must
    have a valid tag" — far more useful than any canned message.
    """
    try:
        data = response.json()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    msgs: list[str] = []
    for err in data.get("errors") or []:
        if isinstance(err, dict) and err.get("message"):
            msg = str(err["message"]).removeprefix("pre_receive ").strip()
            if msg and msg not in msgs:
                msgs.append(msg)
    return " — ".join(msgs) or None


def _github_error_detail(response, action: str) -> str:
    """Build a short, non-leaky message for a failed GitHub call.

    Used instead of `str(httpx.HTTPStatusError)`, which dumps request plumbing
    at the user (e.g. "Client error '422 Unprocessable Entity' for url ...").
    """
    code = response.status_code
    explained = _detail_from_errors(response)
    if explained:
        return explained
    if code in (401, 403):
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining == "0":
            return "GitHub rate limit reached — try again in a few minutes"
        return "GitHub refused the request — reconnect GitHub and check the token's repo access"
    if code == 404:
        return "GitHub couldn't find that repo or tag — check the token's access to it"
    if code == 422:
        return "GitHub rejected the request (validation failed)"
    if code >= 500:
        return "GitHub is having trouble right now — try again shortly"
    logger.warning("GitHub API call failed (HTTP %s) while %s", code, action)
    return f"GitHub API error (HTTP {code})"


class GitHubClient:
    """Client for interacting with the GitHub API."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    async def exchange_code_for_token(self, code: str) -> str:
        """Exchange an OAuth authorization code for an access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GITHUB_OAUTH_TOKEN_URL,
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise ValueError(f"GitHub OAuth error: {data['error_description'] or data['error']}")
            return data["access_token"]

    async def get_user(self, token: str) -> dict[str, Any]:
        """Get the authenticated user's info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def get_user_emails(self, token: str) -> list[dict]:
        """List the user's verified emails (fallback when /user hides email)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user/emails",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def get_user_repos(self, token: str) -> list[dict[str, Any]]:
        """List repos the user has access to."""
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GITHUB_API_BASE}/user/repos",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"per_page": 100, "page": page, "sort": "updated"},
                )
                response.raise_for_status()
                page_repos = response.json()
                if not page_repos:
                    break
                repos.extend(page_repos)
                page += 1
        return repos

    async def get_repo(self, token: str, full_name: str) -> dict[str, Any]:
        """Get a single repository by full name (owner/repo)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{full_name}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def create_webhook(
        self, token: str, full_name: str, webhook_url: str, webhook_secret: str
    ) -> dict[str, Any]:
        """Create a push/tag webhook on a GitHub repo."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{full_name}/hooks",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={
                    "name": "web",
                    "active": True,
                    "events": ["push", "create"],
                    "config": {
                        "url": webhook_url,
                        "content_type": "json",
                        "secret": webhook_secret,
                    },
                },
            )
            response.raise_for_status()
            return response.json()

    async def delete_webhook(
        self, token: str, full_name: str, webhook_url: str
    ) -> bool:
        """Delete our webhook from a repo (best-effort, matches by URL).

        Returns True if a matching hook was deleted.
        """
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            }
            hooks_resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{full_name}/hooks", headers=headers
            )
            hooks_resp.raise_for_status()
            for hook in hooks_resp.json():
                if (hook.get("config") or {}).get("url") == webhook_url:
                    del_resp = await client.delete(
                        f"{GITHUB_API_BASE}/repos/{full_name}/hooks/{hook['id']}",
                        headers=headers,
                    )
                    del_resp.raise_for_status()
                    return True
            return False

    async def get_release_by_tag(
        self, token: str, full_name: str, tag: str
    ) -> dict[str, Any] | None:
        """Return the existing release for a tag, or None if there isn't one."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{full_name}/releases/tags/{tag}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            if response.status_code == 404:
                return None
            if response.status_code != 200:
                raise GitHubApiError(
                    response.status_code,
                    _github_error_detail(response, "looking up a release"),
                )
            return response.json()

    async def create_release(
        self,
        token: str,
        full_name: str,
        tag: str,
        name: str,
        body: str,
        target_commitish: str | None = None,
        prerelease: bool = False,
    ) -> dict[str, Any]:
        """Create a GitHub Release for an existing tag (or from a commitish)."""
        payload: dict[str, Any] = {
            "tag_name": tag,
            "name": name,
            "body": body,
            "prerelease": prerelease,
            "draft": False,
        }
        if target_commitish:
            payload["target_commitish"] = target_commitish
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{full_name}/releases",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json=payload,
            )
            if response.status_code in (422, 409):
                if _is_already_exists(response):
                    # A release for this tag really does exist. Not an error
                    # for us — the caller resolves it and reports
                    # "already published".
                    raise ReleaseAlreadyExistsError(
                        f"A release for {tag} already exists on GitHub"
                    )
                # Any other 422 (e.g. GitHub refusing a tag shape, bad name,
                # missing commitish) is a real failure — carry its message.
                raise GitHubApiError(
                    response.status_code,
                    _github_error_detail(response, "creating the release"),
                )
            if response.status_code != 201:
                raise GitHubApiError(
                    response.status_code,
                    _github_error_detail(response, "creating the release"),
                )
            return response.json()

    async def get_installation_repos(
        self, installation_token: str
    ) -> list[dict[str, Any]]:
        """List repos accessible to an installation."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/installation/repositories",
                headers={
                    "Authorization": f"Bearer {installation_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("repositories", [])
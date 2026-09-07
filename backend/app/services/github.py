from __future__ import annotations

from typing import Any

import httpx

GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"


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
            response.raise_for_status()
            return response.json()

    async def get_or_create_file_commit(
        self,
        token: str,
        full_name: str,
        branch: str,
        path: str,
        content: str,
        commit_message: str,
    ) -> dict[str, Any]:
        """
        Create or update a file on a branch via the Contents API and commit it.

        Handles the "file already exists" case by fetching the existing blob
        SHA first. Returns the GitHub API commit response.
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        encoded = content.encode("utf-8")
        import base64

        b64 = base64.b64encode(encoded).decode("ascii")
        async with httpx.AsyncClient() as client:
            # Does the file already exist on this branch?
            sha: str | None = None
            existing = await client.get(
                f"{GITHUB_API_BASE}/repos/{full_name}/contents/{path}",
                headers=headers,
                params={"ref": branch},
            )
            if existing.status_code == 200:
                sha = existing.json().get("sha")
            body: dict[str, Any] = {
                "message": commit_message,
                "content": b64,
                "branch": branch,
            }
            if sha:
                body["sha"] = sha
            response = await client.put(
                f"{GITHUB_API_BASE}/repos/{full_name}/contents/{path}",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            return response.json()

        """Get all installations of the GitHub App (uses app JWT)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/app/installations",
                headers={
                    "Authorization": f"Bearer {app_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            response.raise_for_status()
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
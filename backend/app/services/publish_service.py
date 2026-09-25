"""
Publishing actions for generated changelogs:

- publish a GitHub Release for the changelog's tag

Publishing is **create-once and idempotent**. Clicking "Publish" on a changelog
that was already published must not rewrite the release (the notes that are live
are identical anyway) and must not fail with GitHub's `422 already_exists`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decrypt_api_key
from app.models.changelog import Changelog as ChangelogModel
from app.models.repo import Repository
from app.models.user import User
from app.services.github import GitHubClient, ReleaseAlreadyExistsError

logger = logging.getLogger(__name__)

ALREADY_PUBLISHED_MESSAGE = (
    "The release notes for this changelog have already been published"
)


def _client() -> GitHubClient:
    return GitHubClient(
        client_id=settings.github_client_id or "",
        client_secret=settings.github_client_secret or "",
    )


async def _user_token(db: AsyncSession, user_id: str) -> str:
    result = await db.get(User, user_id)
    if result is None or not result.github_token:
        raise ValueError("No GitHub token available for this user")
    return decrypt_api_key(result.github_token)


def _release_body(changelog: ChangelogModel) -> str:
    return changelog.raw_markdown or "*No changelog content.*"


_SHA40_RE = None  # compiled lazily to keep import time trivial


def _release_tag(changelog: ChangelogModel) -> str | None:
    """The GitHub tag to publish under.

    Push-generated changelogs carry the full 40-hex commit SHA, which GitHub
    rejects outright ("branch or tag names consisting of 40 or 64 hex
    characters are not allowed"). Shorten those to the classic 7-char
    abbreviation — matching every release this repo already has — while the
    changelog record keeps holding the exact ref.
    """
    import re

    tag = changelog.to_tag or changelog.version
    if tag and re.fullmatch(r"[0-9a-f]{40}", tag):
        return tag[:7]
    return tag


def _record_publish_state(
    changelog: ChangelogModel, release: dict, db: AsyncSession
) -> None:
    """Persist which GitHub release holds this changelog's notes."""
    changelog.release_id = release.get("id") or changelog.release_id
    changelog.release_url = release.get("html_url") or changelog.release_url
    if changelog.published_at is None:
        changelog.published_at = datetime.now(timezone.utc)


def _published_response(changelog: ChangelogModel, tag: str) -> dict[str, str]:
    return {
        "status": "already_published",
        "message": ALREADY_PUBLISHED_MESSAGE,
        "tag": tag,
        "release_url": changelog.release_url or "",
    }


async def publish_release(
    changelog: ChangelogModel, repo: Repository, db: AsyncSession
) -> dict[str, str]:
    """Publish the changelog as a GitHub Release — at most once per tag.

    Returns {status, tag, release_url} (+ message when already published).
    `status` is "created" for a new release, "already_published" when a release
    for this tag already exists (either we recorded it earlier, or it was
    created outside this flow). A release body is never rewritten.
    """
    token = await _user_token(db, changelog.user_id)
    tag = _release_tag(changelog)
    if not tag or tag.startswith("HEAD"):
        raise ValueError(
            "This changelog has no tag — releases need a version tag. "
            "Create a tag in GitHub and regenerate first."
        )

    # 1. Already published by us → nothing to do (not even a GitHub call).
    if changelog.release_url:
        return _published_response(changelog, tag)

    # The release points at the exact commit the changelog covers, even when
    # the tag was shortened for GitHub's naming rules.
    target_commitish = changelog.to_tag if changelog.to_tag != tag else None

    client = _client()

    # 2. Maybe GitHub already has a release for this tag — published before we
    #    tracked it, or a concurrent double-click. Record it and report it
    #    rather than attempting a create that would 422.
    existing = await client.get_release_by_tag(token, repo.full_name, tag)
    if existing is not None:
        _record_publish_state(changelog, existing, db)
        await db.commit()
        logger.info("Release %s for %s already existed — recorded", tag, repo.full_name)
        return _published_response(changelog, tag)

    # 3. Create it.
    try:
        data = await client.create_release(
            token=token,
            full_name=repo.full_name,
            tag=tag,
            name=changelog.version or tag,
            body=_release_body(changelog),
            target_commitish=target_commitish,
        )
    except ReleaseAlreadyExistsError:
        # Lost a race with a concurrent publish — resolve what exists.
        existing = await client.get_release_by_tag(token, repo.full_name, tag)
        if existing is None:
            raise
        _record_publish_state(changelog, existing, db)
        await db.commit()
        return _published_response(changelog, tag)

    _record_publish_state(changelog, data, db)
    await db.commit()
    logger.info("Published release %s for %s", tag, repo.full_name)
    return {
        "status": "created",
        "tag": tag,
        "release_url": changelog.release_url or "",
    }

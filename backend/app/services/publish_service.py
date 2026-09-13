"""
Publishing actions for generated changelogs:

- publish a GitHub Release for the changelog's tag
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_api_key
from app.models.changelog import Changelog as ChangelogModel
from app.models.repo import Repository
from app.models.user import User
from app.services.github import GitHubClient
from app.config import settings

logger = logging.getLogger(__name__)


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


async def publish_release(
    changelog: ChangelogModel, repo: Repository, db: AsyncSession
) -> dict[str, str]:
    """Create a GitHub Release for the changelog. Returns {tag, release_url}."""
    token = await _user_token(db, changelog.user_id)
    tag = changelog.to_tag or changelog.version
    if not tag or tag.startswith("HEAD"):
        raise ValueError(
            "This changelog has no tag — releases need a version tag. "
            "Create a tag in GitHub and regenerate first."
        )
    client = _client()
    data = await client.create_release(
        token=token,
        full_name=repo.full_name,
        tag=tag,
        name=changelog.version or tag,
        body=_release_body(changelog),
    )
    logger.info("Published release %s for %s", tag, repo.full_name)
    return {"tag": tag, "release_url": data.get("html_url", "")}
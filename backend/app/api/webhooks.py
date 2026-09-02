from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_db
from app.models.repo import Repository
from app.models.user import User
from app.models.changelog import Changelog as ChangelogModel
from app.tasks.worker import run_changelog_generation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify the GitHub webhook HMAC-SHA256 signature."""
    if not signature:
        return False
    sig = signature.removeprefix("sha256=")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def is_tag_ref(ref: str) -> bool:
    return ref.startswith("refs/tags/")


def extract_tag_name(ref: str) -> str:
    return ref.removeprefix("refs/tags/")


async def _queue_changelog_for_tag(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    full_name: str,
    tag_name: str,
) -> dict:
    """Find the repo and queue a changelog generation."""
    result = await db.execute(
        select(Repository).where(Repository.full_name == full_name)
    )
    repo = result.scalar_one_or_none()
    if not repo or not repo.is_active:
        return {"status": "ignored", "message": f"Repository {full_name} not registered or inactive"}
    if not repo.is_active:
        return {"status": "ignored", "message": f"Repository {full_name} is inactive"}

    result = await db.execute(select(User).where(User.id == repo.user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"status": "error", "message": "User not found"}

    changelog = ChangelogModel(
        user_id=user.id,
        repo_id=repo.id,
        to_tag=tag_name,
        status="pending",
    )
    db.add(changelog)
    await db.flush()
    await db.refresh(changelog)
    # Commit explicitly so the background task (which uses its own session)
    # can see this changelog record.
    await db.commit()
    await db.refresh(changelog)

    background_tasks.add_task(run_changelog_generation, changelog.id)

    return {
        "status": "queued",
        "message": f"Changelog generation queued for {tag_name}",
        "changelog_id": changelog.id,
    }


@router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a GitHub webhook event.

    Handles:
    - `create` (with refs/tags/* ref) — when a tag is created
    - `push` (with refs/heads/<default_branch> ref) — when a commit is pushed
      to the default branch. We use the latest commit's message to set as
      the to_tag, falling back to commit SHA.
    - `release` (published) — when a GitHub release is published
    """
    body = await request.body()

    # Verify signature
    if settings.github_webhook_secret:
        signature = request.headers.get("x-hub-signature-256")
        if not verify_signature(body, signature, settings.github_webhook_secret):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    # Parse event type
    event = request.headers.get("x-github-event", "")
    if event not in ("push", "create", "release"):
        logger.info("Ignoring event: %s", event)
        return {"status": "ignored", "message": f"Event type '{event}' not handled"}

    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    full_name: str | None = None
    if "repository" in payload:
        full_name = payload["repository"].get("full_name")

    if not full_name:
        return {"status": "ignored", "message": "Missing repository in payload"}

    # 1) Tag creation event
    if event == "create" and is_tag_ref(payload.get("ref", "")):
        tag_name = extract_tag_name(payload["ref"])
        return await _queue_changelog_for_tag(db, background_tasks, full_name, tag_name)

    # 2) Release published event
    if event == "release" and payload.get("action") == "published":
        tag_name = payload.get("release", {}).get("tag_name") or "release"
        return await _queue_changelog_for_tag(db, background_tasks, full_name, tag_name)

    # 3) Push event to default branch
    if event == "push":
        ref = payload.get("ref", "")
        # Find repo to get its default branch
        result = await db.execute(
            select(Repository).where(Repository.full_name == full_name)
        )
        repo = result.scalar_one_or_none()
        if not repo:
            return {"status": "ignored", "message": f"Repository {full_name} not registered"}

        # Only trigger on push to the default branch
        expected_ref = f"refs/heads/{repo.default_branch}"
        if ref != expected_ref:
            return {
                "status": "ignored",
                "message": f"Push to {ref} (not default branch {expected_ref})",
            }

        # Use HEAD commit SHA as the version identifier
        head_sha = payload.get("head_commit", {}).get("id", "")[:7] or "HEAD"
        return await _queue_changelog_for_tag(db, background_tasks, full_name, head_sha)

    return {"status": "ignored", "message": "Not a tag, release, or default-branch push event"}
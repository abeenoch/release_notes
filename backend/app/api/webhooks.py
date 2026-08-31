from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_db
from app.models.repo import Repository
from app.models.user import User
from app.models.changelog import Changelog as ChangelogModel
from app.tasks.worker import run_changelog_generation

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


@router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a GitHub webhook event (push or create tag).

    Expects:
    - Header X-Hub-Signature-256: HMAC-SHA256 signature
    - Header X-GitHub-Event: push | create
    - Body: GitHub push event JSON
    """
    body = await request.body()

    # Verify signature
    if settings.github_webhook_secret:
        signature = request.headers.get("x-hub-signature-256")
        if not verify_signature(body, signature, settings.github_webhook_secret):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    # Parse event type
    event = request.headers.get("x-github-event", "")
    if event not in ("push", "create"):
        return {"status": "ignored", "message": f"Event type '{event}' not handled"}

    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    ref: str = payload.get("ref", "")
    full_name: str | None = None

    if "repository" in payload:
        full_name = payload["repository"].get("full_name")

    if not full_name or not ref:
        return {"status": "ignored", "message": "Missing repository or ref in payload"}

    # Only process tag creation events
    if event == "create" and is_tag_ref(ref):
        tag_name = extract_tag_name(ref)

        # Find the repository in our database
        result = await db.execute(
            select(Repository).where(Repository.full_name == full_name)
        )
        repo = result.scalar_one_or_none()
        if not repo or not repo.is_active:
            return {"status": "ignored", "message": "Repository not registered or inactive"}

        # Get the repo's owner (user)
        result = await db.execute(select(User).where(User.id == repo.user_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"status": "error", "message": "User not found"}

        # Create a pending changelog record
        changelog = ChangelogModel(
            user_id=user.id,
            repo_id=repo.id,
            to_tag=tag_name,
            status="pending",
        )
        db.add(changelog)
        await db.flush()
        await db.refresh(changelog)

        # Enqueue background task
        background_tasks.add_task(run_changelog_generation, changelog.id)

        return {
            "status": "queued",
            "message": f"Changelog generation queued for {tag_name}",
            "changelog_id": changelog.id,
        }

    return {"status": "ignored", "message": "Not a tag creation event"}
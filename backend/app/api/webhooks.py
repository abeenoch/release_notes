from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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


async def _find_active_repos(
    db: AsyncSession,
    full_name: str,
    github_repo_id: int | None = None,
) -> list[Repository]:
    """Every active registration this webhook event concerns.

    Resolution order:
      1. GitHub's numeric repository id — authoritative, survives renames,
         and matches *every* user who registered the same repo (each
         bringing their own GitHub token and notify config).
      2. full_name — fallback for rows imported before github_repo_id
         existed (or created outside the normal import path).
    """
    if github_repo_id is not None:
        result = await db.execute(
            select(Repository).where(
                Repository.github_repo_id == github_repo_id,
                Repository.is_active == True,  # noqa: E712
            )
        )
        rows = list(result.scalars().all())
        if rows:
            return rows
    result = await db.execute(
        select(Repository).where(
            Repository.full_name == full_name,
            Repository.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def _queue_for_repo(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    repo: Repository,
    tag_name: str,
) -> dict:
    """Queue one registration for `tag_name`.

    Idempotency: GitHub retries webhook deliveries, and concurrent retries
    can race past the pre-insert check. The (repo_id, to_tag) UNIQUE
    constraint is the final guard — IntegrityError maps to "ignored".
    """

    # Idempotency: GitHub retries webhook deliveries. Don't queue a duplicate
    # generation for the same tag while one is already pending/processing
    # (or already completed for this exact tag).
    existing = await db.execute(
        select(ChangelogModel)
        .where(
            ChangelogModel.repo_id == repo.id,
            ChangelogModel.to_tag == tag_name,
        )
        .order_by(ChangelogModel.created_at.desc())
    )
    duplicate = existing.scalars().first()
    if duplicate:
        if duplicate.status in ("pending", "processing"):
            return {
                "status": "ignored",
                "message": f"Changelog for {tag_name} already {duplicate.status}",
                "changelog_id": duplicate.id,
            }
        if duplicate.status == "completed":
            return {
                "status": "ignored",
                "message": f"Changelog for {tag_name} already completed",
                "changelog_id": duplicate.id,
            }
        if duplicate.status == "failed":
            # Retry: reuse the same row (UNIQUE on repo_id+to_tag forbids a
            # second row) — reset to pending and re-queue generation.
            duplicate.status = "pending"
            duplicate.error_message = None
            await db.flush()
            await db.commit()
            background_tasks.add_task(run_changelog_generation, duplicate.id)
            return {
                "status": "queued",
                "message": f"Changelog generation re-queued for {tag_name}",
                "changelog_id": duplicate.id,
            }

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
    try:
        await db.flush()
    except IntegrityError:
        # Lost the race with a concurrent delivery for the same tag.
        await db.rollback()
        raced = await db.execute(
            select(ChangelogModel)
            .where(
                ChangelogModel.repo_id == repo.id,
                ChangelogModel.to_tag == tag_name,
            )
            .order_by(ChangelogModel.created_at.desc())
        )
        dup = raced.scalars().first()
        return {
            "status": "ignored",
            "message": f"Changelog for {tag_name} already queued",
            "changelog_id": dup.id if dup else None,
        }
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


async def _queue_changelog_for_tag(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    full_name: str,
    tag_name: str,
    github_repo_id: int | None = None,
) -> dict:
    """Queue a changelog generation for *every* active registration.

    Multiple users may register the same repository — each brings their own
    GitHub token and notify config — so the webhook fans out to all of
    them instead of silently letting "first active row wins" pick a
    (possibly wrong) user's token. Single-registration responses keep the
    original {status, message, changelog_id} shape.

    Idempotency: GitHub retries webhook deliveries; each registration's
    duplicate rules run independently, and the (repo_id, to_tag) UNIQUE
    constraint is the final guard per repo.
    """
    repos = await _find_active_repos(db, full_name, github_repo_id)
    if not repos:
        return {"status": "ignored", "message": f"Repository {full_name} not registered or inactive"}

    outcomes = [await _queue_for_repo(db, background_tasks, repo, tag_name) for repo in repos]
    if len(outcomes) == 1:
        # Preserve the original single-repo response shape.
        return outcomes[0]
    queued = [o for o in outcomes if o["status"] == "queued"]
    return {
        "status": "queued" if queued else "ignored",
        "message": f"{len(queued)}/{len(outcomes)} registration(s) queued for {tag_name}",
        "results": outcomes,
    }


async def _handle_push(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    full_name: str,
    github_repo_id: int | None,
    ref: str,
    head_sha: str,
) -> dict:
    """Push-event rules: registered? default branch? then queue everywhere.

    Extracted from the webhook handler so multi-registration behavior is
    unit-testable — the old inline query used scalar_one_or_none and
    raised MultipleResultsFound the moment two users registered the
    same repo.
    """
    repos = await _find_active_repos(db, full_name, github_repo_id)
    if not repos:
        return {"status": "ignored", "message": f"Repository {full_name} not registered"}

    # Only trigger on push to the default branch (all registrations of the
    # same upstream repo share it).
    expected_ref = f"refs/heads/{repos[0].default_branch}"
    if ref != expected_ref:
        return {
            "status": "ignored",
            "message": f"Push to {ref} (not default branch {expected_ref})",
        }

    if head_sha in ("0000000000000000000000000000000000000000", ""):
        head_sha = "HEAD"
    return await _queue_changelog_for_tag(db, background_tasks, full_name, head_sha, github_repo_id)


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
    github_repo_id: int | None = None
    if "repository" in payload:
        full_name = payload["repository"].get("full_name")
        github_repo_id = payload["repository"].get("id")

    if not full_name:
        return {"status": "ignored", "message": "Missing repository in payload"}

    # 1) Tag creation event
    if event == "create" and is_tag_ref(payload.get("ref", "")):
        tag_name = extract_tag_name(payload["ref"])
        return await _queue_changelog_for_tag(db, background_tasks, full_name, tag_name, github_repo_id)

    # 2) Release published event
    if event == "release" and payload.get("action") == "published":
        tag_name = (
            payload.get("release", {}).get("tag_name")
            or payload.get("release", {}).get("target_commitish")
            or (payload.get("repository", {}).get("pushed_at") and f"release-{payload['repository']['pushed_at']}")
            or f"release-{request.headers.get('x-github-delivery', 'unknown')}"
        )
        return await _queue_changelog_for_tag(db, background_tasks, full_name, tag_name, github_repo_id)

    # 3) Push event to default branch
    if event == "push":
        # FULL HEAD commit SHA as the version identifier (never the 7-char
        # prefix — short SHAs can collide across pushes).
        head_sha = payload.get("head_commit", {}).get("id", "") or payload.get("after", "") or "HEAD"
        return await _handle_push(
            db, background_tasks, full_name, github_repo_id,
            ref=payload.get("ref", ""), head_sha=head_sha,
        )

    return {"status": "ignored", "message": "Not a tag, release, or default-branch push event"}
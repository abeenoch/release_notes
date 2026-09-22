
from __future__ import annotations

import logging

from sqlalchemy import select

from app.database import async_session_factory
from app.models.changelog import Changelog as ChangelogModel
from app.models.repo import Repository
from app.models.user import User
from app.services.changelog_service import ChangelogService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


async def _absorb_duplicate_tag_row(
    db: AsyncSession, changelog: ChangelogModel, to_tag: str | None
) -> None:
    """Remove a pre-existing row for the same (repo_id, to_tag), keeping ours.

    `POST /generate` inserts a row with no `to_tag` and the worker fills it in
    afterwards, so regenerating a repo that hasn't changed resolves to the same
    `(repo_id, to_tag)` as an existing changelog. UNIQUE(repo_id, to_tag) then
    rejects the write — which used to surface as a bogus "failed" changelog with
    a raw SQL error.

    We keep the *new* row (it's the one the UI is polling and just created) and
    drop the older duplicate, carrying its publish state over so a refresh never
    un-publishes a release.

    Deletes and flushes before the caller assigns `to_tag`, because SQLite
    enforces the unique constraint immediately.
    """
    if not to_tag:
        return
    result = await db.execute(
        select(ChangelogModel)
        .where(
            ChangelogModel.repo_id == changelog.repo_id,
            ChangelogModel.to_tag == to_tag,
            ChangelogModel.id != changelog.id,
        )
        .order_by(ChangelogModel.created_at.asc())
    )
    for older in result.scalars().all():
        # Carry publish state forward — the release is still live.
        if not changelog.release_url:
            changelog.release_id = older.release_id or changelog.release_id
            changelog.release_url = older.release_url or changelog.release_url
            changelog.published_at = older.published_at or changelog.published_at
        logger.info(
            "Changelog %s regenerates tag %s — replacing older duplicate %s",
            changelog.id, to_tag, older.id,
        )
        await db.delete(older)
    # Flush the DELETEs before the caller writes to_tag, or the UNIQUE
    # constraint trips on the row we just removed in the same transaction.
    await db.flush()


def _apply_result(target: ChangelogModel, result: ChangelogModel) -> None:
    """Copy generated fields onto `target`.

    Deliberately does not touch release_url/release_id/published_at: refreshing
    a changelog's notes must not un-publish it.
    """
    target.from_tag = result.from_tag
    target.to_tag = result.to_tag
    target.version = result.version
    target.previous_version = result.previous_version
    target.summary = result.summary
    target.raw_markdown = result.raw_markdown
    target.llm_provider = result.llm_provider
    target.commit_count = result.commit_count
    target.status = "completed"
    target.error_message = None


async def run_changelog_generation(changelog_id: str) -> None:
    """
    Background task: generate the changelog content, persist it, then
    deliver via the user's configured notification provider.

    Uses its own database session (independent of the request's session).
    Called from FastAPI BackgroundTasks or from an Arq worker.
    """
    async with async_session_factory() as db:
        try:
            # 1. Load the pending record
            changelog = await db.get(ChangelogModel, changelog_id)
            if changelog is None:
                logger.error("Changelog %s not found — aborting background task", changelog_id)
                return

            # 2. Mark as processing
            changelog.status = "processing"
            await db.commit()

            # 3. Resolve user + repo
            user = await db.get(User, changelog.user_id)
            repo = await db.get(Repository, changelog.repo_id)
            if not user or not repo:
                changelog.status = "failed"
                changelog.error_message = "User or repository not found"
                await db.commit()
                return

            # 4. Run generation
            logger.info("Generating changelog %s for %s", changelog_id, repo.full_name)
            service = ChangelogService()
            result = await service.generate(
                user, repo,
                from_tag=changelog.from_tag,
                to_tag=changelog.to_tag,
                db=db,
            )

            # 5. Persist the result. If an older changelog already occupies this
            #    (repo, tag) — e.g. the repo hasn't changed since last time —
            #    absorb it first (keeping our row, which the UI is polling, and
            #    carrying its publish state), then write.
            await _absorb_duplicate_tag_row(db, changelog, result.to_tag)
            _apply_result(changelog, result)
            await db.commit()

            # 6. Send notification (best-effort — never fails the generation)
            outcome = await NotificationService().notify_for_changelog(changelog, db)
            changelog.notification_status = outcome
            await db.commit()

            logger.info(
                "Changelog %s completed (notification: %s)",
                changelog_id, outcome or "none",
            )

        except Exception as exc:
            logger.exception("Background task failed for changelog %s", changelog_id)
            try:
                changelog = await db.get(ChangelogModel, changelog_id)
                if changelog:
                    changelog.status = "failed"
                    changelog.error_message = str(exc)[:2000]
                    await db.commit()
            except Exception:
                logger.exception("Could not update changelog %s with failure", changelog_id)


#Arq worker settings (for production with Redis)

class WorkerSettings:
    """Arq-compatible worker configuration — activates when Redis is present."""
    functions = [run_changelog_generation]
    redis_settings = {
        "host": "localhost",
        "port": 6379,
        "database": 0,
    }
    poll_delay = 1.0
    max_burst_jobs = 10
    job_timeout = 600  # 10 minutes — large repos can be slow

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

            # 5. Copy result fields onto the saved record
            changelog.from_tag = result.from_tag
            changelog.to_tag = result.to_tag
            changelog.version = result.version
            changelog.previous_version = result.previous_version
            changelog.summary = result.summary
            changelog.raw_markdown = result.raw_markdown
            changelog.llm_provider = result.llm_provider
            changelog.commit_count = result.commit_count
            changelog.status = "completed"
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
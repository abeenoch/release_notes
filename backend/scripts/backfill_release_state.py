"""Backfill GitHub Release publish state onto existing changelogs.

Why: `release_url` / `release_id` / `published_at` were added after some
changelogs had already been published. Without them the UI shows "Publish as
GitHub Release" for releases that already exist. Clicking is safe (the publish
endpoint resolves the existing release and reports "already published"), but this
script records it up front so the UI is accurate immediately.

Read-only against GitHub (one `GET /releases/tags/{tag}` per tagged changelog
that has no recorded release). Only writes to local rows that are still unset.

Usage (from backend/, with the venv):
    ./venv/bin/python scripts/backfill_release_state.py            # dry run
    ./venv/bin/python scripts/backfill_release_state.py --apply    # write
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models.notify_config  # noqa: F401,E402  (mapper registration)
import app.models.user_config  # noqa: F401,E402

from sqlalchemy import select  # noqa: E402

from app.core.security import decrypt_api_key  # noqa: E402
from app.database import async_session_factory, init_db  # noqa: E402
from app.models.changelog import Changelog  # noqa: E402
from app.models.repo import Repository  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.github import GitHubClient  # noqa: E402
from app.services.publish_service import _record_publish_state  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill-release-state")


async def main(apply: bool) -> int:
    await init_db()
    recorded = 0
    skipped = 0

    async with async_session_factory() as db:
        users = {u.id: u for u in (await db.execute(select(User))).scalars().all()}
        repos = {r.id: r for r in (await db.execute(select(Repository))).scalars().all()}
        changelogs = (
            await db.execute(
                select(Changelog).where(
                    Changelog.to_tag.isnot(None),
                    Changelog.status == "completed",
                    Changelog.release_url.is_(None),
                )
            )
        ).scalars().all()

        client = GitHubClient(client_id="", client_secret="")
        for changelog in changelogs:
            repo = repos.get(changelog.repo_id)
            user = users.get(changelog.user_id) if repo else None
            if not repo or not user or not user.github_token:
                skipped += 1
                continue
            tag = changelog.to_tag
            if not tag or tag.startswith("HEAD"):
                skipped += 1
                continue
            try:
                token = decrypt_api_key(user.github_token)
                release = await client.get_release_by_tag(token, repo.full_name, tag)
            except Exception as exc:  # noqa: BLE001 — best-effort backfill
                logger.warning("Skipping %s %s: %s", repo.full_name, tag, exc)
                skipped += 1
                continue
            if release is None:
                skipped += 1
                continue
            logger.info(
                "%s %s -> release %s (%s)",
                repo.full_name, tag, release.get("id"), release.get("html_url"),
            )
            if apply:
                _record_publish_state(changelog, release, db)
            recorded += 1

        if apply:
            await db.commit()

    verb = "Recorded" if apply else "Would record"
    logger.info("%s publish state for %s changelog(s); skipped %s", verb, recorded, skipped)
    if not apply and recorded:
        logger.info("Re-run with --apply to write these changes")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="write changes (default is a dry run)"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))

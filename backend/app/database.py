from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


#Lightweight SQLite dev migrations
# `create_all` only creates missing tables — it never adds columns to existing
# tables. For dev/pre-MVP this helper adds missing columns via ALTER TABLE.
# Production should use Alembic (see alembic/).

_CHANGELOG_ADDITIONS: dict[str, str] = {
    "status": "VARCHAR(20) DEFAULT 'pending' NOT NULL",
    "error_message": "TEXT",
    "notification_status": "VARCHAR(20)",
    "release_id": "INTEGER",
    "release_url": "VARCHAR(500)",
    "published_at": "DATETIME",
}

_UNIQUE_CHANGELOG_INDEX_SQL = text(
    "CREATE UNIQUE INDEX IF NOT EXISTS "
    "uq_changelogs_repo_to_tag ON changelogs(repo_id, to_tag)"
)

# Keeps one row per (repo_id, to_tag): prefer a usable result, then newest.
# Only touches rows that are duplicates of another row — nothing unique is lost.
_DEDUPE_CHANGELOGS_SQL = text(
    """
    DELETE FROM changelogs
    WHERE to_tag IS NOT NULL
      AND id NOT IN (
        SELECT id FROM (
            SELECT id,
                   ROW_NUMBER() OVER (
                     PARTITION BY repo_id, to_tag
                     ORDER BY CASE status
                                WHEN 'completed' THEN 0
                                WHEN 'processing' THEN 1
                                WHEN 'pending' THEN 2
                                ELSE 3
                              END,
                              created_at DESC,
                              id DESC
                   ) AS rn
            FROM changelogs
            WHERE to_tag IS NOT NULL
        )
        WHERE rn = 1
      )
    """
)


async def _ensure_unique_changelog_index(conn) -> None:
    """Create the (repo_id, to_tag) unique index — the last-line idempotency guard.

    Double webhook deliveries before the fix left duplicate rows, and SQLite
    refuses to build a unique index over them. Trying once and swallowing the
    error (the previous behaviour) silently disabled the guard in production,
    so on failure we dedupe first and retry. Dedupe only removes rows that have
    a twin with the same (repo_id, to_tag); nothing references changelogs by FK.
    """
    try:
        await conn.execute(_UNIQUE_CHANGELOG_INDEX_SQL)
        return
    except Exception as exc:
        logger.warning(
            "uq_changelogs_repo_to_tag could not be created (%s) — deduping changelogs", exc
        )
    try:
        before = (await conn.execute(text("SELECT COUNT(*) FROM changelogs"))).scalar()
        await conn.execute(_DEDUPE_CHANGELOGS_SQL)
        after = (await conn.execute(text("SELECT COUNT(*) FROM changelogs"))).scalar()
        removed = (before or 0) - (after or 0)
        if removed:
            logger.warning(
                "Removed %s duplicate changelog row(s) to enforce (repo_id, to_tag) uniqueness",
                removed,
            )
        await conn.execute(_UNIQUE_CHANGELOG_INDEX_SQL)
        logger.info("Created uq_changelogs_repo_to_tag (after dedupe)")
    except Exception as exc:
        logger.error(
            "Could not create uq_changelogs_repo_to_tag even after dedupe (%s) — "
            "webhook idempotency falls back to the pre-insert check only",
            exc,
        )


_REPO_ADDITIONS: dict[str, str] = {
    "last_generated_commit": "VARCHAR(40)",
    "public_enabled": "BOOLEAN NOT NULL DEFAULT 0",
}


async def _ensure_sqlite_columns() -> None:
    """Idempotently add newly-introduced columns to existing SQLite tables."""
    if not settings.database_url.startswith("sqlite"):
        return  # Postgres → use Alembic migrations instead
    async with engine.begin() as conn:
        for table, columns in (
            ("changelogs", _CHANGELOG_ADDITIONS),
            ("repositories", _REPO_ADDITIONS),
        ):
            try:
                result = await conn.execute(text(f"PRAGMA table_info({table})"))
                existing = {row[1] for row in result.fetchall()}
            except Exception:
                logger.warning("Could not introspect table %s — skipping dev migration", table)
                continue
            for col, ddl in columns.items():
                if col not in existing:
                    try:
                        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                        logger.info("Applied dev migration: added %s.%s", table, col)
                    except Exception as exc:  # column already exists etc.
                        logger.warning("Could not add %s.%s (%s)", table, col, exc)
        # Backfill the (repo_id, to_tag) idempotency constraint (SQLite has no
        # ADD CONSTRAINT). Old duplicates are deduped first, otherwise the
        # index cannot be built and idempotency would be unguarded.
        await _ensure_unique_changelog_index(conn)


# FastAPI dependency

async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency — yields an async DB session.

    Mutating handlers commit explicitly; this dependency only rolls back
    on error so read-only GETs never issue stray commits.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (idempotent — good for dev)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_sqlite_columns()
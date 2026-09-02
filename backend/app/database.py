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
}

_REPO_ADDITIONS: dict[str, str] = {
    "last_generated_commit": "VARCHAR(40)",
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


# FastAPI dependency

async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency — yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (idempotent — good for dev)."""
    await _ensure_sqlite_columns()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
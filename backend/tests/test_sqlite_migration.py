"""The (repo_id, to_tag) unique index is the last-line webhook idempotency
guard. Pre-fix double deliveries left duplicate rows, and SQLite refuses to
build a unique index over them — the old code swallowed that error, silently
leaving production unguarded. These tests pin the dedupe-then-create path.
"""
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import _ensure_unique_changelog_index

# Legacy schema: same shape as changelogs, but BEFORE UniqueConstraint existed.
_LEGACY_DDL = """
CREATE TABLE changelogs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    repo_id VARCHAR(36) NOT NULL,
    from_tag VARCHAR(255),
    to_tag VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    error_message TEXT,
    created_at DATETIME
)
"""


@pytest_asyncio.fixture
async def engine(tmp_path):
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/legacy.db")
    async with eng.begin() as conn:
        await conn.execute(text(_LEGACY_DDL))
    yield eng
    await eng.dispose()


async def _insert(conn, id_, repo_id, to_tag, status, created_at):
    await conn.execute(
        text(
            "INSERT INTO changelogs (id, user_id, repo_id, to_tag, status, created_at) "
            "VALUES (:id, 'u1', :repo, :tag, :status, :created)"
        ),
        {"id": id_, "repo": repo_id, "tag": to_tag, "status": status, "created": created_at},
    )


async def _count(conn) -> int:
    return (await conn.execute(text("SELECT COUNT(*) FROM changelogs"))).scalar()


@pytest.mark.asyncio
async def test_dedupe_then_index_on_legacy_rows(engine):
    async with engine.begin() as conn:
        # Same tag twice (the real-world double webhook delivery)
        await _insert(conn, "a1", "r1", "v1.0.0", "failed", "2026-01-01 00:00:00")
        await _insert(conn, "a2", "r1", "v1.0.0", "completed", "2026-01-02 00:00:00")
        # Status priority must beat recency: completed kept over newer failed
        await _insert(conn, "b1", "r1", "v2.0.0", "completed", "2026-01-01 00:00:00")
        await _insert(conn, "b2", "r1", "v2.0.0", "failed", "2026-01-05 00:00:00")
        # NULL to_tag rows are legitimately non-unique and must survive
        await _insert(conn, "c1", "r1", None, "pending", "2026-01-01 00:00:00")
        await _insert(conn, "c2", "r1", None, "pending", "2026-01-02 00:00:00")
        # Unrelated single row must survive untouched
        await _insert(conn, "d1", "r2", "v3.0.0", "completed", "2026-01-01 00:00:00")

        await _ensure_unique_changelog_index(conn)

        rows = (await conn.execute(text("SELECT id FROM changelogs ORDER BY id"))).scalars().all()
        assert rows == ["a2", "b1", "c1", "c2", "d1"]
        assert await _count(conn) == 5

        index_names = (
            await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='changelogs'")
            )
        ).scalars().all()
        assert "uq_changelogs_repo_to_tag" in index_names


@pytest.mark.asyncio
async def test_migration_is_idempotent(engine):
    async with engine.begin() as conn:
        await _insert(conn, "a1", "r1", "v1.0.0", "completed", "2026-01-01 00:00:00")
        await _ensure_unique_changelog_index(conn)
        await _ensure_unique_changelog_index(conn)  # second boot: must not delete anything
        assert await _count(conn) == 1


@pytest.mark.asyncio
async def test_duplicate_insert_rejected_after_migration(engine):
    from sqlalchemy.exc import IntegrityError

    async with engine.begin() as conn:
        await _ensure_unique_changelog_index(conn)

    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await _insert(conn, "x1", "r1", "v1.0.0", "pending", "2026-01-01 00:00:00")
            await _insert(conn, "x2", "r1", "v1.0.0", "pending", "2026-01-01 00:00:01")

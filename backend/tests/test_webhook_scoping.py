"""Webhook scoping — one upstream repo, many registrations.

The old lookup was "global full_name, first active row wins", and the push
branch used scalar_one_or_none (MultipleResultsFound once two users
registered the same repo). These tests pin the new behavior:

  * every active registration gets its own queued changelog,
  * GitHub's numeric repository id beats full_name (survives renames),
  * inactive registrations are skipped,
  * push events fan out instead of crashing.
"""
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.webhooks import (
    _find_active_repos,
    _handle_push,
    _queue_changelog_for_tag,
)
from app.database import Base
from app.models.changelog import Changelog
from app.models.repo import Repository
from app.models.user import User


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _register(db, login: str, full_name: str, github_repo_id=None, active=True) -> Repository:
    user = User(github_id=f"id-{login}", github_login=login)
    db.add(user)
    await db.flush()
    repo = Repository(
        user_id=user.id,
        full_name=full_name,
        default_branch="main",
        github_repo_id=github_repo_id,
        is_active=active,
    )
    db.add(repo)
    await db.commit()
    return repo


async def _changelog_repo_ids(db) -> set[str]:
    rows = list((await db.execute(select(Changelog))).scalars().all())
    return {r.repo_id for r in rows}


# ── fan-out ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_same_full_name_queues_for_every_user(db):
    r1 = await _register(db, "alice", "octocat/hello", github_repo_id=111)
    r2 = await _register(db, "bob", "octocat/hello", github_repo_id=111)

    result = await _queue_changelog_for_tag(db, MagicMock(), "octocat/hello", "v1.0.0", 111)

    assert result["status"] == "queued"
    assert len(result["results"]) == 2
    # Each registration got its own row — nobody was silently dropped.
    assert await _changelog_repo_ids(db) == {r1.id, r2.id}


@pytest.mark.asyncio
async def test_single_registration_keeps_original_response_shape(db):
    """Existing consumers (and tests) read changelog_id off the top level."""
    await _register(db, "alice", "octocat/hello", github_repo_id=111)
    result = await _queue_changelog_for_tag(db, MagicMock(), "octocat/hello", "v1.0.0", 111)
    assert result["status"] == "queued"
    assert "changelog_id" in result
    assert "results" not in result


# ── identity resolution ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_repo_id_beats_stale_full_name(db):
    """Repo renamed on GitHub: numeric id still finds the registration."""
    stale = await _register(db, "alice", "octocat/old-name", github_repo_id=111)

    repos = await _find_active_repos(db, "octocat/new-name", github_repo_id=111)
    assert [r.id for r in repos] == [stale.id]

    result = await _queue_changelog_for_tag(
        db, MagicMock(), "octocat/new-name", "v1.0.0", github_repo_id=111
    )
    assert result["status"] == "queued"
    assert await _changelog_repo_ids(db) == {stale.id}


@pytest.mark.asyncio
async def test_full_name_fallback_when_numeric_id_unknown(db):
    """Rows imported before github_repo_id existed still resolve by name."""
    legacy = await _register(db, "alice", "octocat/hello", github_repo_id=None)

    repos = await _find_active_repos(db, "octocat/hello", github_repo_id=None)
    assert [r.id for r in repos] == [legacy.id]

    # An id nobody registered falls back to a name lookup.
    repos = await _find_active_repos(db, "octocat/hello", github_repo_id=999)
    assert [r.id for r in repos] == [legacy.id]


@pytest.mark.asyncio
async def test_inactive_registration_is_skipped(db):
    active = await _register(db, "alice", "octocat/hello", github_repo_id=111, active=True)
    await _register(db, "bob", "octocat/hello", github_repo_id=111, active=False)

    result = await _queue_changelog_for_tag(db, MagicMock(), "octocat/hello", "v1.0.0", 111)
    assert result["status"] == "queued"  # single active → single-repo shape
    assert await _changelog_repo_ids(db) == {active.id}


@pytest.mark.asyncio
async def test_unregistered_repo_is_ignored(db):
    result = await _queue_changelog_for_tag(db, MagicMock(), "nobody/none", "v1.0.0", 404)
    assert result["status"] == "ignored"
    assert await _changelog_repo_ids(db) == set()


# ── push events ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_push_fans_out_instead_of_raising(db):
    """Old code: scalar_one_or_none → MultipleResultsFound with 2 rows."""
    r1 = await _register(db, "alice", "octocat/hello", github_repo_id=111)
    r2 = await _register(db, "bob", "octocat/hello", github_repo_id=111)

    result = await _handle_push(
        db, MagicMock(), "octocat/hello", 111,
        ref="refs/heads/main", head_sha="abc123" * 6 + "abcd",
    )
    assert result["status"] == "queued"
    assert await _changelog_repo_ids(db) == {r1.id, r2.id}

    # Pushes to non-default branches stay ignored.
    before = await _changelog_repo_ids(db)
    ignored = await _handle_push(
        db, MagicMock(), "octocat/hello", 111,
        ref="refs/heads/feature", head_sha="deadbeef",
    )
    assert ignored["status"] == "ignored"
    assert await _changelog_repo_ids(db) == before

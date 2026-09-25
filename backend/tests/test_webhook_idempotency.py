"""Tests for webhook idempotency — GitHub retries deliveries, we must not
queue duplicate changelog generations for the same tag."""
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.webhooks import _queue_changelog_for_tag, is_tag_ref, verify_signature
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


async def _seed(db: AsyncSession) -> Repository:
    user = User(github_id="1", github_login="octocat")
    db.add(user)
    await db.flush()
    repo = Repository(user_id=user.id, full_name="octocat/hello", default_branch="main")
    db.add(repo)
    await db.commit()
    return repo


@pytest.mark.asyncio
async def test_pending_changelog_not_duplicated(db):
    await _seed(db)
    bg = MagicMock()
    first = await _queue_changelog_for_tag(db, bg, "octocat/hello", "v1.0.0")
    assert first["status"] == "queued"

    # GitHub retry of the same delivery — must be ignored, not re-queued
    retry = await _queue_changelog_for_tag(db, bg, "octocat/hello", "v1.0.0")
    assert retry["status"] == "ignored"
    assert retry["changelog_id"] == first["changelog_id"]

    count = len((await db.execute(select(Changelog))).scalars().all())
    assert count == 1


@pytest.mark.asyncio
async def test_completed_changelog_not_regenerated(db):
    repo = await _seed(db)
    changelog = Changelog(user_id=repo.user_id, repo_id=repo.id, to_tag="v1.0.0", status="completed")
    db.add(changelog)
    await db.commit()

    bg = MagicMock()
    result = await _queue_changelog_for_tag(db, bg, "octocat/hello", "v1.0.0")
    assert result["status"] == "ignored"
    bg.add_task.assert_not_called()


@pytest.mark.asyncio
async def test_failed_changelog_can_be_retried(db):
    repo = await _seed(db)
    changelog = Changelog(user_id=repo.user_id, repo_id=repo.id, to_tag="v1.0.0", status="failed")
    db.add(changelog)
    await db.commit()

    bg = MagicMock()
    result = await _queue_changelog_for_tag(db, bg, "octocat/hello", "v1.0.0")
    assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_different_tag_still_queues(db):
    repo = await _seed(db)
    db.add(Changelog(user_id=repo.user_id, repo_id=repo.id, to_tag="v1.0.0", status="completed"))
    await db.commit()

    bg = MagicMock()
    result = await _queue_changelog_for_tag(db, bg, "octocat/hello", "v1.1.0")
    assert result["status"] == "queued"


def test_is_tag_ref():
    assert is_tag_ref("refs/tags/v1.0.0")
    assert not is_tag_ref("refs/heads/main")


def test_verify_signature():
    assert verify_signature(b"x", "sha256=" + "0" * 64, "secret") is False
    assert verify_signature(b"x", None, "secret") is False

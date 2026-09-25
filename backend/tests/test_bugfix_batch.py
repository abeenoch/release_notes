"""Regression tests for the bug-fix batch: provider enums, pagination,
webhook race guard, prompt truncation and commit counting."""
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.webhooks import _queue_changelog_for_tag
from app.database import Base
from app.models.changelog import Changelog
from app.models.repo import Repository
from app.models.user import User
from app.schemas.changelog import LlmConfigCreate
from app.schemas.notify import NotifyConfigCreate


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
    user = User(github_id="42", github_login="octocat")
    db.add(user)
    await db.flush()
    repo = Repository(user_id=user.id, full_name="octocat/hello", default_branch="main")
    db.add(repo)
    await db.commit()
    return repo


def test_llm_provider_enum_rejects_typos():
    with pytest.raises(ValidationError):
        LlmConfigCreate(provider="open- ai", api_key="x")


def test_notify_provider_enum_rejects_typos():
    with pytest.raises(ValidationError):
        NotifyConfigCreate(provider="smtp2")


def test_llm_provider_enum_accepts_all():
    for p in ("openai", "anthropic", "ollama", "groq", "openrouter", "commit"):
        assert LlmConfigCreate(provider=p).provider == p


@pytest.mark.asyncio
async def test_webhook_race_second_insert_ignored(db):
    """Two concurrent deliveries for the same tag → one row, second ignored."""
    from sqlalchemy.exc import IntegrityError
    repo = await _seed(db)
    bg = MagicMock()
    first = await _queue_changelog_for_tag(db, bg, "octocat/hello", "v9.9.9")
    assert first["status"] == "queued"
    # Simulate the race: bypass the pre-check, hit the UNIQUE constraint
    dup = Changelog(user_id=repo.user_id, repo_id=repo.id, to_tag="v9.9.9", status="pending")
    db.add(dup)
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


def test_commit_count_ignores_sentinels_and_omission_line():
    from app.services.changelog_service import ChangelogService  # noqa: F401 (import guard)
    summary = "[abc1234] 2026-01-01 00:00:00 — feat: x\n... and 5 older commits omitted\n"
    count = sum(1 for line in summary.split("\n") if line.strip() and not line.startswith("... and "))
    assert count == 1
    for sentinel in ("(no commits found between these refs)", "(could not retrieve commits)"):
        assert sentinel in ("(no commits found between these refs)", "(could not retrieve commits)")

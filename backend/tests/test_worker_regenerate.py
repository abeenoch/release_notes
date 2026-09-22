"""Re-generating a changelog whose tag already exists must not fail.

Regression context: UNIQUE(repo_id, to_tag) made the worker's write blow up when
a repo hadn't changed since the last generation (same resolved tag), surfacing as
a bogus "failed" changelog with a raw SQL error. The new row must win and absorb
the older duplicate, carrying its publish state.
"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.changelog import Changelog
from app.models.repo import Repository
from app.models.user import User
from app.tasks.worker import _absorb_duplicate_tag_row, _apply_result

# Resolve User's relationships for mapper configuration.
import app.models.user_config  # noqa: F401
import app.models.notify_config  # noqa: F401


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _repo(db: AsyncSession) -> Repository:
    user = User(github_id="11", github_login="regen")
    db.add(user)
    await db.flush()
    repo = Repository(user_id=user.id, full_name="octocat/regen", default_branch="main")
    db.add(repo)
    await db.commit()
    return repo


def _result_row(repo: Repository, to_tag: str, markdown: str) -> Changelog:
    """A transient object shaped like what ChangelogService.generate returns."""
    return Changelog(
        user_id=repo.user_id, repo_id=repo.id, to_tag=to_tag, version=to_tag,
        summary="refreshed", raw_markdown=markdown, llm_provider="commit",
        commit_count=2,
    )


@pytest.mark.asyncio
async def test_regenerate_same_tag_replaces_older_row_without_error(db):
    repo = await _repo(db)
    older = Changelog(
        user_id=repo.user_id, repo_id=repo.id, to_tag="HEAD (unreleased)",
        status="completed", raw_markdown="old notes",
        release_id=321, release_url="https://github.com/octocat/regen/releases/tag/x",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db.add(older)
    await db.commit()

    # The regeneration the API just queued: to_tag not yet resolved.
    new = Changelog(user_id=repo.user_id, repo_id=repo.id, status="pending")
    db.add(new)
    await db.commit()

    result = _result_row(repo, "HEAD (unreleased)", "new notes")
    await _absorb_duplicate_tag_row(db, new, result.to_tag)
    _apply_result(new, result)
    await db.commit()  # would raise IntegrityError before the fix

    rows = (await db.execute(select(Changelog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == new.id          # the row the UI is polling survives
    assert rows[0].status == "completed"
    assert rows[0].raw_markdown == "new notes"
    # The release stays published across a regeneration.
    assert rows[0].release_url == "https://github.com/octocat/regen/releases/tag/x"
    assert rows[0].release_id == 321


@pytest.mark.asyncio
async def test_regenerate_with_new_tag_keeps_history(db):
    repo = await _repo(db)
    db.add(Changelog(
        user_id=repo.user_id, repo_id=repo.id, to_tag="v1.0.0", status="completed",
    ))
    await db.commit()
    new = Changelog(user_id=repo.user_id, repo_id=repo.id, status="pending")
    db.add(new)
    await db.commit()

    result = _result_row(repo, "v2.0.0", "v2 notes")
    await _absorb_duplicate_tag_row(db, new, result.to_tag)
    _apply_result(new, result)
    await db.commit()

    rows = (await db.execute(select(Changelog))).scalars().all()
    assert {r.to_tag for r in rows} == {"v1.0.0", "v2.0.0"}  # nothing lost


@pytest.mark.asyncio
async def test_unresolved_tag_absorbs_nothing(db):
    """A generation that resolved no tag (e.g. failure path) must be untouched."""
    repo = await _repo(db)
    db.add(Changelog(
        user_id=repo.user_id, repo_id=repo.id, to_tag="v1.0.0", status="completed",
    ))
    await db.commit()
    new = Changelog(user_id=repo.user_id, repo_id=repo.id, status="pending")
    db.add(new)
    await db.commit()

    await _absorb_duplicate_tag_row(db, new, None)
    await db.commit()

    assert len((await db.execute(select(Changelog))).scalars().all()) == 2

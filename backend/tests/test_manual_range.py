"""Manual range trigger — POST /changelogs/generate with from_tag/to_tag.

Covers the three promises of this feature:
  * both ends or neither (partial ranges used to be silently ignored),
  * syntactic ref screening before anything is queued,
  * existence checks against the local clone when one is available.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.changelogs import generate_changelog
from app.database import Base
from app.models.changelog import Changelog
from app.models.repo import Repository
from app.models.user import User
from app.schemas.changelog import ChangelogTriggerRequest
from app.services.git_ops import ref_exists, validate_ref_shape


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


async def _trigger(db, repo, **kwargs):
    """Call the endpoint function directly with a mocked BackgroundTasks."""
    bg = MagicMock()
    resp = await generate_changelog(
        body=ChangelogTriggerRequest(repo_id=repo.id, **kwargs),
        background_tasks=bg,
        user_id=repo.user_id,
        db=db,
    )
    return resp, bg


async def _rows(db) -> list[Changelog]:
    return list((await db.execute(select(Changelog))).scalars().all())


# ── both ends or neither ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_from_only_is_rejected_before_queueing(db):
    repo = await _seed(db)
    with pytest.raises(HTTPException) as exc:
        await _trigger(db, repo, from_tag="v1.0.0")
    assert exc.value.status_code == 400
    assert "both" in exc.value.detail
    assert await _rows(db) == []  # nothing was created


@pytest.mark.asyncio
async def test_to_only_is_rejected_before_queueing(db):
    repo = await _seed(db)
    with pytest.raises(HTTPException) as exc:
        await _trigger(db, repo, to_tag="v1.0.0")
    assert exc.value.status_code == 400
    assert await _rows(db) == []


@pytest.mark.asyncio
async def test_full_range_is_queued(db):
    repo = await _seed(db)
    resp, bg = await _trigger(db, repo, from_tag="v1.0.0", to_tag="v1.1.0")
    assert resp.status == "pending"
    assert (resp.from_tag, resp.to_tag) == ("v1.0.0", "v1.1.0")
    bg.add_task.assert_called_once()

    rows = await _rows(db)
    assert len(rows) == 1
    assert (rows[0].from_tag, rows[0].to_tag) == ("v1.0.0", "v1.1.0")


@pytest.mark.asyncio
async def test_no_range_still_queues_incremental(db):
    """Neither end → today's default behavior, unchanged."""
    repo = await _seed(db)
    resp, bg = await _trigger(db, repo)
    assert resp.status == "pending"
    assert resp.from_tag is None and resp.to_tag is None
    bg.add_task.assert_called_once()


# ── syntactic screening ──────────────────────────────────────────────


def test_validate_ref_shape_accepts_real_refs():
    for ref in ("v1.0.0", "23cf490", "4a87346f2c0d1e5b7a9c8f6d4e2b0a1c3d5e7f90", "HEAD", "main", "release/1.0"):
        assert validate_ref_shape(ref) is None, ref


def test_validate_ref_shape_rejects_bad_refs():
    bad = {
        "": "empty",
        "--upload-pack=rm": "invalid character",
        "a..b": "'..'",
        "a b": "whitespace",
        "tag~1": "git-special",
        "x" * 256: "longer than",
        ".hidden": "invalid character",
    }
    for ref, needle in bad.items():
        err = validate_ref_shape(ref)
        assert err is not None, ref
        assert needle in err, (ref, err)


# ── existence check against a real clone ─────────────────────────────


def _make_clone(path: Path):
    """Tiny real git repo with one commit and tag v1.0.0."""
    import git as gitpy
    from git import Actor

    repo = gitpy.Repo.init(path)
    (path / "a.txt").write_text("hello\n")
    repo.index.add(["a.txt"])
    actor = Actor("Tester", "tester@example.com")
    repo.index.commit("init", author=actor, committer=actor)
    repo.create_tag("v1.0.0")
    return repo


@pytest.mark.asyncio
async def test_unknown_ref_in_existing_clone_is_400(db, tmp_path, monkeypatch):
    repo = await _seed(db)
    _make_clone(tmp_path)
    monkeypatch.setattr("app.api.changelogs.repo_work_dir", lambda uid, r: tmp_path)

    with pytest.raises(HTTPException) as exc:
        await _trigger(db, repo, from_tag="v1.0.0", to_tag="v9.9.9")
    assert exc.value.status_code == 400
    assert "v9.9.9" in exc.value.detail
    assert await _rows(db) == []


@pytest.mark.asyncio
async def test_existing_refs_in_clone_are_queued(db, tmp_path, monkeypatch):
    repo = await _seed(db)
    _make_clone(tmp_path)
    monkeypatch.setattr("app.api.changelogs.repo_work_dir", lambda uid, r: tmp_path)

    resp, bg = await _trigger(db, repo, from_tag="v1.0.0", to_tag="HEAD")
    assert resp.status == "pending"
    bg.add_task.assert_called_once()


def test_ref_exists_true_and_false(tmp_path):
    _make_clone(tmp_path)
    assert ref_exists(tmp_path, "v1.0.0") is True
    assert ref_exists(tmp_path, "HEAD") is True
    assert ref_exists(tmp_path, "v9.9.9") is False

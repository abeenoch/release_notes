"""Public vanity pages — /owner/repo, strictly opt-in.

Pins the privacy contract:
  * OFF by default: registering a repo never publishes it,
  * only the owner can flip the switch,
  * the public endpoint serves only completed changelogs and only from an
    opted-in registration — no ids, status, errors or notification state,
  * 404 (not 403) for everything not published, so existence never leaks.
"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.changelog  # noqa: F401
import app.models.notify_config  # noqa: F401
import app.models.repo  # noqa: F401

# Import every model module: User's relationships resolve by class name, so
# the mapper needs them all registered (this file doesn't transitively
# import user_config/notify_config like the API-heavy test modules do).
import app.models.user  # noqa: F401
import app.models.user_config  # noqa: F401
from app.api.public_pages import get_public_page
from app.api.repos import set_repo_public_page
from app.database import Base
from app.models.changelog import Changelog
from app.models.repo import Repository
from app.models.user import User
from app.schemas.repo import RepoPublicUpdate


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed(db, login: str, public: bool = False, private: bool = False) -> Repository:
    user = User(github_id=f"id-{login}", github_login=login)
    db.add(user)
    await db.flush()
    repo = Repository(
        user_id=user.id,
        full_name="octocat/hello",
        default_branch="main",
        github_repo_id=111,
        is_private=private,
        public_enabled=public,
    )
    db.add(repo)
    await db.flush()
    db.add(Changelog(
        user_id=user.id, repo_id=repo.id, to_tag="v1.0.0", version="v1.0.0",
        status="completed", raw_markdown="## Fixes\n- things",
        release_url="https://github.com/octocat/hello/releases/v1.0.0",
        notification_status="sent",
    ))
    db.add(Changelog(
        user_id=user.id, repo_id=repo.id, to_tag="wip42", status="processing",
        error_message="secret internal error", notification_status="failed",
    ))
    db.add(Changelog(
        user_id=user.id, repo_id=repo.id, to_tag="broken7", status="failed",
        error_message="another secret",
    ))
    await db.commit()
    return repo


async def _seed_named(db, login: str, public: bool, version: str) -> Repository:
    user = User(github_id=f"id-{login}", github_login=login)
    db.add(user)
    await db.flush()
    repo = Repository(
        user_id=user.id, full_name="octocat/hello", default_branch="main",
        github_repo_id=111, public_enabled=public,
    )
    db.add(repo)
    await db.flush()
    db.add(Changelog(
        user_id=user.id, repo_id=repo.id, to_tag=version, version=version,
        status="completed", raw_markdown="stuff",
    ))
    await db.commit()
    return repo


# ── ownership of the switch ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_only_owner_can_enable(db):
    repo = await _seed(db, "alice", public=False)

    with pytest.raises(HTTPException) as exc:
        await set_repo_public_page(
            repo.id, RepoPublicUpdate(enabled=True), user_id="someone-else", db=db
        )
    assert exc.value.status_code == 404
    await db.refresh(repo)
    assert repo.public_enabled is False  # unchanged

    resp = await set_repo_public_page(
        repo.id, RepoPublicUpdate(enabled=True), user_id=repo.user_id, db=db
    )
    assert resp.public_enabled is True

    resp = await set_repo_public_page(
        repo.id, RepoPublicUpdate(enabled=False), user_id=repo.user_id, db=db
    )
    assert resp.public_enabled is False


@pytest.mark.asyncio
async def test_private_repo_still_needs_opt_in(db):
    """Private repos are 404 until their owner explicitly opts in."""
    await _seed(db, "alice", public=False, private=True)
    with pytest.raises(HTTPException):
        await get_public_page("octocat", "hello", db)

    # …and opting in deliberately publishes it (owner's call, UI warns).
    repo = (await db.execute(
        select(Repository).where(Repository.full_name == "octocat/hello")
    )).scalars().first()
    repo.public_enabled = True
    repo.is_private = True
    await db.commit()

    page = await get_public_page("octocat", "hello", db)
    assert page.is_private is True
    assert [c.version for c in page.changelogs] == ["v1.0.0"]


@pytest.mark.asyncio
async def test_only_the_opted_in_registration_serves(db):
    """Two users, same name: only opted-in registrations ever serve."""
    await _seed(db, "alice", public=True)          # version v1.0.0
    await _seed_named(db, "bob", public=False, version="v9.9.9")

    page = await get_public_page("octocat", "hello", db)
    assert [c.version for c in page.changelogs] == ["v1.0.0"]
    assert "v9.9.9" not in [c.version for c in page.changelogs]

    # Bob opting in later must never MERGE the two users' changelogs —
    # exactly one registration wins (active + most recently updated).
    bob = (await db.execute(
        select(Repository).where(Repository.user_id != (  # the other row
            select(User.id).where(User.github_login == "alice").scalar_subquery()
        ))
    )).scalars().first()
    bob.public_enabled = True
    await db.commit()

    page = await get_public_page("octocat", "hello", db)
    assert len(page.changelogs) == 1  # single registration, never a mix


# ── opt-in gate ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_disabled_by_default_is_404(db):
    await _seed(db, "alice", public=False)
    with pytest.raises(HTTPException) as exc:
        await get_public_page("octocat", "hello", db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_unregistered_name_is_404(db):
    with pytest.raises(HTTPException) as exc:
        await get_public_page("nobody", "nothing", db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_opt_in_serves_page(db):
    await _seed(db, "alice", public=True)
    page = await get_public_page("octocat", "hello", db)
    assert page.full_name == "octocat/hello"


# ── what leaves the server ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_only_completed_changelogs_are_served(db):
    await _seed(db, "alice", public=True)
    page = await get_public_page("octocat", "hello", db)
    assert [c.version for c in page.changelogs] == ["v1.0.0"]  # processing + failed hidden


@pytest.mark.asyncio
async def test_payload_has_no_internals(db):
    """id / status / error_message / notification_status must never leak."""
    await _seed(db, "alice", public=True)
    page = await get_public_page("octocat", "hello", db)
    dumped = page.changelogs[0].model_dump()
    forbidden = {"id", "repo_id", "status", "error_message", "notification_status", "llm_provider"}
    assert not (set(dumped) & forbidden), set(dumped) & forbidden
    assert page.changelogs[0].release_url is not None

"""Publishing a changelog as a GitHub Release must be create-once.

Regression context: a second click used to POST again, get GitHub's
`422 already_exists`, and surface as a 502 whose message looked like a server
crash. It must instead report that the notes are already published — and never
rewrite an existing release.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.changelog import Changelog
from app.models.repo import Repository
from app.models.user import User

# Import sibling model modules so SQLAlchemy can resolve User's relationships
# (User.llm_configs / User.notify_configs) when configuring mappers.
import app.models.user_config  # noqa: F401
import app.models.notify_config  # noqa: F401

from app.services import publish_service
from app.services.github import (
    GitHubApiError, ReleaseAlreadyExistsError, _github_error_detail,
    _is_already_exists,
)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed(db: AsyncSession, **changelog_kwargs):
    user = User(github_id="7", github_login="publisher")
    db.add(user)
    await db.flush()
    repo = Repository(user_id=user.id, full_name="octocat/hello", default_branch="main")
    db.add(repo)
    await db.flush()
    defaults = dict(
        to_tag="v1.0.0", version="v1.0.0", status="completed",
        raw_markdown="# Changelog — v1.0.0\n\n- thing",
    )
    defaults.update(changelog_kwargs)
    changelog = Changelog(user_id=user.id, repo_id=repo.id, **defaults)
    db.add(changelog)
    await db.commit()
    return user, repo, changelog


class FakeGitHub:
    """Records calls so tests can assert what would hit the API."""

    def __init__(self, existing=None, create_raises=None):
        self.existing = existing
        self.create_raises = create_raises
        self.created = []

    async def get_release_by_tag(self, token, full_name, tag):
        return self.existing

    async def create_release(self, token, full_name, tag, name, body, **kw):
        self.created.append({"tag": tag, "name": name, "body": body})
        if self.create_raises:
            raise self.create_raises
        return {"id": 555, "html_url": f"https://github.com/{full_name}/releases/tag/{tag}"}


@pytest.fixture(autouse=True)
def _fake_token(monkeypatch):
    async def _token(db, user_id):
        return "fake-token"

    monkeypatch.setattr(publish_service, "_user_token", _token)



@pytest.mark.asyncio
async def test_stats_reports_full_totals_not_page_length(db, monkeypatch):
    """Dashboard counts must survive past the list default limit of 50."""
    from app.api.changelogs import changelog_stats, list_changelogs

    user = User(github_id="stats", github_login="counter")
    db.add(user)
    await db.flush()
    repo = Repository(user_id=user.id, full_name="octocat/stats", default_branch="main")
    db.add(repo)
    await db.flush()
    for i in range(55):
        db.add(Changelog(
            user_id=user.id, repo_id=repo.id, to_tag=f"v{i}", status="completed",
            release_url=f"https://x/{i}" if i % 2 == 0 else None,
        ))
    await db.commit()

    stats = await changelog_stats(repo_id=None, user_id=user.id, db=db)
    assert stats.changelogs_total == 55
    assert stats.changelogs_completed == 55
    assert stats.changelogs_failed == 0
    assert stats.changelogs_published == 28

    page = await list_changelogs(repo_id=None, limit=50, offset=0, user_id=user.id, db=db)
    assert len(page.changelogs) == 50          # page caps at the limit...
    assert page.total == 55                     # ...but the total tells the truth
    assert page.total == stats.changelogs_total


@pytest.mark.asyncio
async def test_stats_scopes_to_repo(db, monkeypatch):
    user = User(github_id="stats2", github_login="counter2")
    db.add(user)
    await db.flush()
    repos = []
    for name in ("octocat/a", "octocat/b"):
        repo = Repository(user_id=user.id, full_name=name, default_branch="main")
        db.add(repo)
        await db.flush()
        repos.append(repo)
    db.add(Changelog(user_id=user.id, repo_id=repos[0].id, to_tag="v1", status="completed"))
    db.add(Changelog(user_id=user.id, repo_id=repos[1].id, to_tag="v1", status="completed"))
    db.add(Changelog(user_id=user.id, repo_id=repos[1].id, to_tag="v2", status="failed"))
    await db.commit()

    from app.api.changelogs import changelog_stats
    scoped = await changelog_stats(repo_id=repos[1].id, user_id=user.id, db=db)
    assert (scoped.changelogs_total, scoped.changelogs_completed, scoped.changelogs_failed) == (2, 1, 1)


@pytest.mark.asyncio
async def test_second_publish_reports_already_published_without_touching_github(db, monkeypatch):
    """The accidental double-click: no create call, no overwrite, friendly status."""
    _, repo, changelog = await _seed(
        db, release_id=999, release_url="https://github.com/octocat/hello/releases/tag/v1.0.0",
    )
    fake = FakeGitHub()
    monkeypatch.setattr(publish_service, "_client", lambda: fake)

    result = await publish_service.publish_release(changelog, repo, db)

    assert result["status"] == "already_published"
    assert result["message"] == publish_service.ALREADY_PUBLISHED_MESSAGE
    assert result["release_url"].endswith("/v1.0.0")
    assert fake.created == []  # nothing was written


@pytest.mark.asyncio
async def test_release_created_outside_the_app_is_recorded_not_duplicated(db, monkeypatch):
    """Releases published before we tracked state must not 422 — resolve instead."""
    _, repo, changelog = await _seed(db)
    fake = FakeGitHub(existing={
        "id": 42,
        "html_url": "https://github.com/octocat/hello/releases/tag/v1.0.0",
    })
    monkeypatch.setattr(publish_service, "_client", lambda: fake)

    result = await publish_service.publish_release(changelog, repo, db)

    assert result["status"] == "already_published"
    assert fake.created == []
    await db.refresh(changelog)
    assert changelog.release_id == 42
    assert changelog.published_at is not None


@pytest.mark.asyncio
async def test_first_publish_creates_and_records(db, monkeypatch):
    _, repo, changelog = await _seed(db)
    fake = FakeGitHub()
    monkeypatch.setattr(publish_service, "_client", lambda: fake)

    result = await publish_service.publish_release(changelog, repo, db)

    assert result["status"] == "created"
    assert len(fake.created) == 1
    assert fake.created[0]["tag"] == "v1.0.0"
    await db.refresh(changelog)
    assert changelog.release_url.endswith("/v1.0.0")
    assert changelog.release_id == 555


@pytest.mark.asyncio
async def test_race_on_create_resolves_to_already_published(db, monkeypatch):
    """Two clicks at once: the losing create() resolves instead of erroring."""
    _, repo, changelog = await _seed(db)

    class RacingGitHub(FakeGitHub):
        async def create_release(self, *a, **kw):
            # Between our lookup and the create, the other click won.
            self.existing = {
                "id": 77,
                "html_url": "https://github.com/octocat/hello/releases/tag/v1.0.0",
            }
            raise ReleaseAlreadyExistsError("already exists")

    fake = RacingGitHub()
    monkeypatch.setattr(publish_service, "_client", lambda: fake)

    result = await publish_service.publish_release(changelog, repo, db)

    assert result["status"] == "already_published"
    await db.refresh(changelog)
    assert changelog.release_id == 77


@pytest.mark.asyncio
async def test_missing_tag_is_a_clear_error_not_a_github_call(db, monkeypatch):
    _, repo, changelog = await _seed(db, to_tag="HEAD (unreleased)", version=None)
    fake = FakeGitHub()
    monkeypatch.setattr(publish_service, "_client", lambda: fake)

    with pytest.raises(ValueError) as exc:
        await publish_service.publish_release(changelog, repo, db)
    assert "no tag" in str(exc.value)
    assert fake.created == []


@pytest.mark.asyncio
async def test_github_failure_carries_a_clean_message(db, monkeypatch):
    _, repo, changelog = await _seed(db)

    class FailingGitHub(FakeGitHub):
        async def get_release_by_tag(self, token, full_name, tag):
            raise GitHubApiError(403, "GitHub refused the request — reconnect GitHub")

    monkeypatch.setattr(publish_service, "_client", lambda: FailingGitHub())

    with pytest.raises(GitHubApiError) as exc:
        await publish_service.publish_release(changelog, repo, db)
    assert exc.value.status_code == 403
    # The message must be human, never the raw httpx repr.
    assert "httpx" not in exc.value.detail
    assert "for url" not in exc.value.detail


class _FakeResponse:
    """Minimal stand-in for httpx.Response for error-path tests."""

    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = {}

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


# The exact payload GitHub returned today for a 40-hex release tag.
PRE_RECEIVE_422 = {
    "message": "Validation Failed",
    "errors": [
        {
            "resource": "Release",
            "code": "custom",
            "field": "pre_receive",
            "message": "pre_receive Sorry, branch or tag names consisting of 40 or 64 hex characters are not allowed.",
        },
        {
            "resource": "Release",
            "code": "custom",
            "message": "Published releases must have a valid tag",
        },
    ],
}

ALREADY_EXISTS_422 = {
    "message": "Validation Failed",
    "errors": [{"resource": "Release", "code": "already_exists", "field": "tag_name"}],
}


def test_already_exists_only_when_payload_says_so():
    assert _is_already_exists(_FakeResponse(422, ALREADY_EXISTS_422)) is True
    assert _is_already_exists(_FakeResponse(409, ALREADY_EXISTS_422)) is True
    # A 422 for other reasons (tag-shape rejection etc.) is NOT a duplicate.
    assert _is_already_exists(_FakeResponse(422, PRE_RECEIVE_422)) is False
    assert _is_already_exists(_FakeResponse(422, {"message": "Validation Failed"})) is False
    assert _is_already_exists(_FakeResponse(422, None)) is False


def test_error_detail_prefers_githubs_own_explanation():
    detail = _github_error_detail(_FakeResponse(422, PRE_RECEIVE_422), "creating the release")
    assert "Published releases must have a valid tag" in detail
    assert "40 or 64 hex" in detail
    assert "httpx" not in detail and "for url" not in detail


def test_release_tag_shortens_full_sha():
    from app.services import publish_service as ps
    from types import SimpleNamespace

    mk = lambda tag, **kw: SimpleNamespace(to_tag=tag, version=kw.get("version"))
    assert ps._release_tag(mk("23cf4904f513493d05d06f4c2977bc698bddd230")) == "23cf490"
    assert ps._release_tag(mk("4a87346")) == "4a87346"
    assert ps._release_tag(mk("v1.2.3")) == "v1.2.3"
    assert ps._release_tag(mk(None, version=None)) is None


@pytest.mark.asyncio
async def test_publish_shortens_forbidden_tag_and_points_at_commit(db, monkeypatch):
    """The 23cf490 case: create goes out with tag '23cf490' aimed at the full SHA."""
    _, repo, changelog = await _seed(db, to_tag="23cf4904f513493d05d06f4c2977bc698bddd230")

    calls: dict = {}

    class RecordingGitHub(FakeGitHub):
        async def create_release(self, token, full_name, tag, name, body, **kw):
            calls.update(tag=tag, target_commitish=kw.get("target_commitish"))
            return await super().create_release(token, full_name, tag, name, body, **kw)

    monkeypatch.setattr(publish_service, "_client", lambda: RecordingGitHub())
    result = await publish_service.publish_release(changelog, repo, db)

    assert result["status"] == "created"
    assert result["tag"] == "23cf490"
    assert calls["tag"] == "23cf490"
    assert calls["target_commitish"] == "23cf4904f513493d05d06f4c2977bc698bddd230"
    await db.refresh(changelog)
    assert changelog.release_url.endswith("/23cf490")

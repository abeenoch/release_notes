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
from app.services.github import GitHubApiError, ReleaseAlreadyExistsError


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

"""Subscribers — double opt-in, fan-out via the OWNER's own SMTP/SendGrid.

Decision pinned here: there is NO platform-wide sender. Every send uses the
repo owner's stored UserNotifyConfig; no email-capable config means
subscribe 400s and fan-out reports "skipped" — never a silent fake send.
"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.changelog  # noqa: F401
import app.models.notify_config  # noqa: F401
import app.models.repo  # noqa: F401
import app.models.subscriber  # noqa: F401
import app.models.user  # noqa: F401 — register all mappers (see test_public_pages)
import app.models.user_config  # noqa: F401
from app.api.public_pages import confirm_subscription, subscribe, unsubscribe
from app.core.security import encrypt_api_key
from app.database import Base
from app.models.changelog import Changelog
from app.models.notify_config import UserNotifyConfig
from app.models.repo import Repository
from app.models.subscriber import Subscriber
from app.models.user import User
from app.schemas.changelog import SubscribeRequest
from app.services.subscriber_service import SubscriberService


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


class FakeProvider:
    """Captures sends instead of touching any real SMTP/SendGrid."""

    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []  # (to, subject, body)

    async def send(self, from_addr="", to_addr="", subject="", body="", html_body=None):
        self.sent.append((to_addr, subject, body))


@pytest.fixture
def outbox(monkeypatch):
    """Every NotificationService.build_provider call returns this one box."""
    box = FakeProvider()
    monkeypatch.setattr(
        "app.services.notification_service.create_notify_provider",
        lambda **kwargs: box,
    )
    return box


async def _seed(db, public=True, email_cfg=True, cfg_provider="smtp"):
    user = User(github_id="u1", github_login="alice")
    db.add(user)
    await db.flush()
    repo = Repository(
        user_id=user.id, full_name="octocat/hello", default_branch="main",
        github_repo_id=111, public_enabled=public,
    )
    db.add(repo)
    await db.flush()
    if email_cfg:
        db.add(UserNotifyConfig(
            user_id=user.id,
            provider=cfg_provider,
            smtp_host="smtp.example.com" if cfg_provider == "smtp" else None,
            smtp_pass_encrypted=encrypt_api_key("pw") if cfg_provider == "smtp" else None,
            sendgrid_api_key_encrypted=encrypt_api_key("sg") if cfg_provider == "sendgrid" else None,
            slack_webhook_url="https://hooks.example/x" if cfg_provider == "slack" else None,
            from_email="owner@example.com",
            to_email="owner@example.com",
            is_active=True,
        ))
    db.add(Changelog(
        user_id=user.id, repo_id=repo.id, to_tag="v1.0.0", version="v1.0.0",
        status="completed", raw_markdown="# v1.0.0\n- thing happened",
    ))
    await db.commit()
    return repo, user


async def _subscribe_and_confirm(db, email: str) -> Subscriber:
    await subscribe("octocat", "hello", SubscribeRequest(email=email), db)
    sub = (await db.execute(
        select(Subscriber).where(Subscriber.email == email.strip().lower())
    )).scalar_one()
    await confirm_subscription(sub.confirm_token, db)
    await db.refresh(sub)
    return sub


# ── subscribe / confirm / unsubscribe ────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_sends_confirmation_and_normalizes_email(db, outbox):
    await _seed(db)
    resp = await subscribe(
        "octocat", "hello", SubscribeRequest(email="  Fan@Example.COM "), db
    )
    assert resp.status == "pending_confirmation"

    sub = (await db.execute(select(Subscriber))).scalars().one()
    assert sub.email == "fan@example.com"  # trimmed + lowercased
    assert sub.confirmed_at is None        # NOT subscribed yet (double opt-in)

    assert len(outbox.sent) == 1
    to, subject, body = outbox.sent[0]
    assert to == "fan@example.com"
    assert "/confirm/" in body             # the link is in the mail


@pytest.mark.asyncio
async def test_confirmed_subscriber_is_idempotent(db, outbox):
    await _seed(db)
    await _subscribe_and_confirm(db, "fan@example.com")

    resp = await subscribe(
        "octocat", "hello", SubscribeRequest(email="fan@example.com"), db
    )
    assert resp.status == "already_subscribed"
    assert len(outbox.sent) == 1  # only the original confirmation — no resend


@pytest.mark.asyncio
async def test_unconfirmed_resend_issues_fresh_link(db, outbox):
    await _seed(db)
    await subscribe("octocat", "hello", SubscribeRequest(email="a@b.co"), db)
    first = (await db.execute(select(Subscriber))).scalars().one()
    first_token = first.confirm_token

    await subscribe("octocat", "hello", SubscribeRequest(email="a@b.co"), db)
    await db.refresh(first)
    rows = (await db.execute(select(Subscriber))).scalars().all()
    assert len(rows) == 1                      # never a duplicate row
    assert first.confirm_token != first_token  # fresh link on resend
    assert len(outbox.sent) == 2


@pytest.mark.asyncio
async def test_subscribe_requires_public_page(db, outbox):
    await _seed(db, public=False)
    with pytest.raises(HTTPException) as exc:
        await subscribe("octocat", "hello", SubscribeRequest(email="a@b.co"), db)
    assert exc.value.status_code == 404
    assert outbox.sent == []


@pytest.mark.asyncio
async def test_subscribe_without_owner_email_config_400s(db, outbox):
    await _seed(db, email_cfg=False)
    with pytest.raises(HTTPException) as exc:
        await subscribe("octocat", "hello", SubscribeRequest(email="a@b.co"), db)
    assert exc.value.status_code == 400
    assert "email notifications" in exc.value.detail
    assert (await db.execute(select(Subscriber))).scalars().all() == []


@pytest.mark.asyncio
async def test_confirm_unknown_token(db):
    resp = await confirm_subscription("nope-nope", db)
    assert resp.status == "not_found"


# ── fan-out (the actual release mail) ────────────────────────────────


@pytest.mark.asyncio
async def test_fanout_goes_only_to_confirmed(db, outbox):
    await _seed(db)
    await _subscribe_and_confirm(db, "confirmed@x.io")
    await subscribe("octocat", "hello", SubscribeRequest(email="pending@x.io"), db)
    outbox.sent.clear()  # ignore confirmation mails

    changelog = (await db.execute(select(Changelog))).scalars().one()
    outcome = await SubscriberService().notify_subscribers(changelog, db)

    assert outcome == "sent"
    recipients = [to for to, _, _ in outbox.sent]
    assert recipients == ["confirmed@x.io"]
    # Mail carries the changelog content + unsubscribe is owner-branded subject
    assert "thing happened" in outbox.sent[0][2]


@pytest.mark.asyncio
async def test_unsubscribed_is_excluded_from_next_release(db, outbox):
    await _seed(db)
    await _subscribe_and_confirm(db, "staying@x.io")
    leaving = await _subscribe_and_confirm(db, "leaving@x.io")

    result = await unsubscribe(leaving.unsubscribe_token, db)
    assert result.status == "unsubscribed"
    emails = {s.email for s in (await db.execute(select(Subscriber))).scalars().all()}
    assert emails == {"staying@x.io"}

    outbox.sent.clear()
    changelog = (await db.execute(select(Changelog))).scalars().one()
    outcome = await SubscriberService().notify_subscribers(changelog, db)
    assert outcome == "sent"
    assert [to for to, _, _ in outbox.sent] == ["staying@x.io"]


@pytest.mark.asyncio
async def test_fanout_skips_without_owner_email_config(db, outbox):
    """No email-capable config → 'skipped', zero sends, no crash."""
    repo, _ = await _seed(db, email_cfg=False)
    db.add(Subscriber(
        repo_id=repo.id, email="orphan@x.io",
        confirm_token="c1", unsubscribe_token="u1",
        confirmed_at=datetime.now(timezone.utc),
    ))
    await db.commit()

    changelog = (await db.execute(select(Changelog))).scalars().one()
    outcome = await SubscriberService().notify_subscribers(changelog, db)
    assert outcome == "skipped"
    assert outbox.sent == []


@pytest.mark.asyncio
async def test_subscribe_rejected_when_only_slack(db, outbox):
    """The confirmation mail itself needs email — Slack-only can't opt in."""
    await _seed(db, cfg_provider="slack")
    with pytest.raises(HTTPException) as exc:
        await subscribe("octocat", "hello", SubscribeRequest(email="a@b.co"), db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_fanout_skips_for_slack_only_config(db, outbox):
    """Owner switched to Slack AFTER people subscribed → 'skipped', not a crash."""
    repo, _ = await _seed(db, cfg_provider="slack")
    db.add(Subscriber(
        repo_id=repo.id, email="fan@x.io",
        confirm_token="c2", unsubscribe_token="u2",
        confirmed_at=datetime.now(timezone.utc),
    ))
    await db.commit()

    changelog = (await db.execute(select(Changelog))).scalars().one()
    outcome = await SubscriberService().notify_subscribers(changelog, db)
    assert outcome == "skipped"
    assert outbox.sent == []


@pytest.mark.asyncio
async def test_fanout_none_when_nobody_subscribed(db, outbox):
    await _seed(db)
    changelog = (await db.execute(select(Changelog))).scalars().one()
    outcome = await SubscriberService().notify_subscribers(changelog, db)
    assert outcome is None  # nothing to do — not even a "skipped"

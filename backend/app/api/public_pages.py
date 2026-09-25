from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.changelog import Changelog as ChangelogModel
from app.models.repo import Repository
from app.models.subscriber import Subscriber
from app.schemas.changelog import (
    PublicChangelogResponse,
    PublicPageResponse,
    SubscribeRequest,
    SubscribeResponse,
    TokenActionResponse,
)
from app.services.subscriber_service import SubscriberService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["public"])


async def _resolve_public_repo(db: AsyncSession, owner: str, repo: str) -> Repository:
    """The opted-in registration for /owner/repo, or 404 (never 403 — the
    endpoint must not confirm existence of unpublished pages)."""
    full_name = f"{owner}/{repo}"
    result = await db.execute(
        select(Repository)
        .where(
            Repository.full_name == full_name,
            Repository.public_enabled == True,  # noqa: E712
        )
        .order_by(Repository.is_active.desc(), Repository.updated_at.desc())
    )
    registration = result.scalars().first()
    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Changelog page not found",
        )
    return registration


# ── Token actions (declared BEFORE /{owner}/{repo}: same segment count) ──


@router.get("/confirm/{token}", response_model=TokenActionResponse)
async def confirm_subscription(token: str, db: AsyncSession = Depends(get_db)):
    """Redeem a double opt-in confirmation link. Idempotent, always 200."""
    sub = (await db.execute(
        select(Subscriber).where(Subscriber.confirm_token == token)
    )).scalar_one_or_none()
    if not sub:
        return TokenActionResponse(
            status="not_found",
            message="This confirmation link is invalid or has expired.",
        )
    if not sub.confirmed_at:
        sub.confirmed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()
    return TokenActionResponse(
        status="confirmed",
        message="Subscription confirmed — you'll get release notes by email.",
    )


@router.get("/unsubscribe/{token}", response_model=TokenActionResponse)
async def unsubscribe(token: str, db: AsyncSession = Depends(get_db)):
    """Remove a subscription via its own token. Idempotent, always 200."""
    sub = (await db.execute(
        select(Subscriber).where(Subscriber.unsubscribe_token == token)
    )).scalar_one_or_none()
    if not sub:
        return TokenActionResponse(
            status="not_found",
            message="This unsubscribe link is invalid.",
        )
    await db.delete(sub)
    await db.flush()
    await db.commit()
    return TokenActionResponse(
        status="unsubscribed",
        message="You've been unsubscribed. You can subscribe again any time.",
    )


# ── Public page + subscribe ──────────────────────────────────────────


@router.post("/{owner}/{repo}/subscribe", response_model=SubscribeResponse)
async def subscribe(
    owner: str,
    repo: str,
    body: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start a double-opt-in subscription.

    Emails go through the OWNER's stored SMTP/SendGrid config — if they
    haven't set one up, this 400s with a clear message instead of
    pretending. Resubscribing an unconfirmed address resends the
    confirmation; confirmed addresses are idempotent (no mail).
    """
    registration = await _resolve_public_repo(db, owner, repo)  # 404 if not public

    existing = (await db.execute(
        select(Subscriber).where(
            Subscriber.repo_id == registration.id,
            Subscriber.email == body.email,
        )
    )).scalar_one_or_none()

    if existing and existing.confirmed_at:
        return SubscribeResponse(
            status="already_subscribed",
            message="You're already subscribed with this address.",
        )

    svc = SubscriberService()
    cfg = await svc.get_email_config(registration.user_id, db)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The owner hasn't configured email notifications yet, "
                   "so subscriptions are closed for this page.",
        )

    if existing:
        sub = existing
        sub.confirm_token = secrets.token_urlsafe(32)  # fresh link on resend
    else:
        sub = Subscriber(
            repo_id=registration.id,
            email=body.email,
            confirm_token=secrets.token_urlsafe(32),
            unsubscribe_token=secrets.token_urlsafe(32),
        )
        db.add(sub)
    await db.flush()
    await db.commit()

    try:
        await svc.send_confirmation(cfg, sub, registration.full_name)
    except Exception:
        # Don't leak send failures to the public form; the row stays pending
        # and a retry (resubscribe) issues a fresh link.
        logger.exception(
            "Confirmation mail failed for %s (%s)", body.email, registration.full_name
        )

    return SubscribeResponse(
        status="pending_confirmation",
        message="Almost there — check your inbox and confirm the subscription.",
    )


@router.get("/{owner}/{repo}", response_model=PublicPageResponse)
async def get_public_page(
    owner: str,
    repo: str,
    db: AsyncSession = Depends(get_db),
):
    """Read-only public changelog page for /owner/repo — no auth.

    Serves ONLY opted-in registrations (public_enabled, off by default) and
    only completed changelogs: ids, status, error messages and notification
    state never leave the server.
    """
    registration = await _resolve_public_repo(db, owner, repo)

    rows = (await db.execute(
        select(ChangelogModel)
        .where(
            ChangelogModel.repo_id == registration.id,
            ChangelogModel.status == "completed",
        )
        .order_by(ChangelogModel.created_at.desc())
    )).scalars().all()

    return PublicPageResponse(
        full_name=registration.full_name,
        is_private=registration.is_private,
        changelogs=[
            PublicChangelogResponse(
                version=c.version,
                previous_version=c.previous_version,
                from_tag=c.from_tag,
                to_tag=c.to_tag,
                summary=c.summary,
                raw_markdown=c.raw_markdown,
                commit_count=c.commit_count,
                release_url=c.release_url,
                published_at=c.published_at,
                created_at=c.created_at,
            )
            for c in rows
        ],
    )

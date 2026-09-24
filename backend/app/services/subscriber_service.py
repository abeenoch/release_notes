"""Email subscribers of a public changelog page.

Decision (agreed): every send goes through the REPO OWNER's own stored
notify config (UserNotifyConfig — their SMTP or SendGrid), never a
platform-wide sender. No email-capable config → subscriber mail is
"skipped", never silently faked.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.changelog import Changelog as ChangelogModel
from app.models.notify_config import UserNotifyConfig
from app.models.subscriber import Subscriber
from app.services.email_template import changelog_email_html
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def email_capable(cfg: UserNotifyConfig) -> bool:
    """True when this config can actually address an email to someone.

    Slack can't mail subscribers; SMTP/SendGrid need a from-address and
    their credentials. Mirrors NotificationService.send_changelog's checks.
    """
    if not cfg.from_email:
        return False
    if cfg.provider == "smtp":
        return bool(cfg.smtp_host and cfg.smtp_pass_encrypted)
    if cfg.provider == "sendgrid":
        return bool(cfg.sendgrid_api_key_encrypted)
    return False


class SubscriberService:
    """Confirmation mail + per-release fan-out for confirmed subscribers."""

    async def get_email_config(self, user_id: str, db: AsyncSession) -> UserNotifyConfig | None:
        cfg = await NotificationService().get_active_config(user_id, db)
        if cfg and email_capable(cfg):
            return cfg
        return None

    async def send_confirmation(
        self,
        cfg: UserNotifyConfig,
        subscriber: Subscriber,
        full_name: str,
    ) -> None:
        """Send the double opt-in confirmation link. Raises on delivery error."""
        link = f"{(settings.public_base_url or '').rstrip('/')}/confirm/{subscriber.confirm_token}"
        subject = f"Confirm subscription — {full_name}"
        markdown = (
            f"**Confirm your subscription**\n\n"
            f"You'll receive release notes for **{full_name}** at this address.\n\n"
            f"[Confirm subscription]({link})\n\n"
            f"If you didn't request this, simply ignore this email."
        )
        html = changelog_email_html(subject=subject, markdown=markdown)
        provider = NotificationService().build_provider(cfg)
        await provider.send(
            from_addr=cfg.from_email or "",
            to_addr=subscriber.email,
            subject=subject,
            body=markdown,
            html_body=html,
        )

    async def notify_subscribers(
        self, changelog: ChangelogModel, db: AsyncSession
    ) -> str | None:
        """Fan-out one completed changelog to the repo's confirmed subscribers.

        Returns subscriber_status: "sent" (all delivered) | "partial" |
        "skipped" (no subscribers or no email-capable owner config) |
        "failed" | None (nothing to do / unexpected error is "failed").
        Never raises — subscriber mail must not fail the generation.
        """
        try:
            subs = list((await db.execute(
                select(Subscriber).where(
                    Subscriber.repo_id == changelog.repo_id,
                    Subscriber.confirmed_at.is_not(None),
                )
            )).scalars().all())
            if not subs:
                return None

            cfg = await self.get_email_config(changelog.user_id, db)
            if cfg is None:
                logger.info(
                    "Repo %s has confirmed subscribers but no email-capable "
                    "notify config — subscriber mail skipped",
                    changelog.repo_id,
                )
                return "skipped"

            ns = NotificationService()
            subject = ns.build_subject(cfg, changelog)
            html_subject = ns.build_html_subject(cfg, subject)
            markdown = changelog.raw_markdown or "*No changelog content.*"
            html = changelog_email_html(subject=html_subject or subject, markdown=markdown)
            provider = ns.build_provider(cfg)

            sent = 0
            for sub in subs:
                try:
                    await provider.send(
                        from_addr=cfg.from_email or "",
                        to_addr=sub.email,
                        subject=subject,
                        body=markdown,
                        html_body=html,
                    )
                    sent += 1
                except Exception:
                    logger.exception(
                        "Subscriber mail failed for %s (changelog %s)",
                        sub.email, changelog.id,
                    )
            if sent == len(subs):
                return "sent"
            return "partial" if sent else "failed"
        except Exception:
            logger.exception("Subscriber fan-out failed for changelog %s", changelog.id)
            return "failed"

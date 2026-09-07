
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_api_key
from app.models.changelog import Changelog as ChangelogModel
from app.models.notify_config import UserNotifyConfig
from app.services.notify.factory import create_notify_provider
from app.services.email_template import changelog_email_html

logger = logging.getLogger(__name__)


class NotificationService:
    """Build a provider from a UserNotifyConfig and send changelogs through it."""

    async def get_active_config(
        self, user_id: str, db: AsyncSession
    ) -> UserNotifyConfig | None:
        """Return the user's active notification config, if any."""
        result = await db.execute(
            select(UserNotifyConfig).where(
                UserNotifyConfig.user_id == user_id,
                UserNotifyConfig.is_active == True,  # noqa: E712
            ).limit(1)
        )
        return result.scalar_one_or_none()

    def build_provider(self, cfg: UserNotifyConfig):
        """Instantiate the concrete provider from a stored config."""
        return create_notify_provider(
            provider=cfg.provider,
            smtp_host=cfg.smtp_host,
            smtp_port=cfg.smtp_port or 587,
            smtp_user=cfg.smtp_user,
            smtp_pass=(
                decrypt_api_key(cfg.smtp_pass_encrypted)
                if cfg.smtp_pass_encrypted else None
            ),
            smtp_secure=cfg.smtp_secure or False,
            sendgrid_api_key=(
                decrypt_api_key(cfg.sendgrid_api_key_encrypted)
                if cfg.sendgrid_api_key_encrypted else None
            ),
            slack_webhook_url=cfg.slack_webhook_url,
            slack_channel=cfg.slack_channel,
        )

    def build_subject(self, cfg: UserNotifyConfig, changelog: ChangelogModel) -> str:
        prefix = cfg.subject_prefix or "[Changelog]"
        version = changelog.version or changelog.to_tag or "release"
        return f"{prefix} {version}".strip()

    async def send_changelog(
        self, cfg: UserNotifyConfig, changelog: ChangelogModel
    ) -> str:
        """
        Send a changelog through the given config.

        Returns one of:
          - "sent"   → delivered successfully
          - "skipped"→ config exists but is incomplete (missing email/keys)
        Raises for delivery failures.
        """
        body = changelog.raw_markdown or "*No changelog content.*"
        subject = self.build_subject(cfg, changelog)
        html_body = changelog_email_html(
            subject=subject.replace(cfg.subject_prefix or "[Changelog]", "").strip() or subject,
            markdown=body,
        )

        if cfg.provider == "slack":
            if not cfg.slack_webhook_url:
                logger.warning("Slack config missing webhook URL — skipping")
                return "skipped"
            provider = self.build_provider(cfg)
            await provider.send(from_addr="", to_addr="", subject=subject, body=body, html_body=html_body)
            return "sent"

        # SMTP / SendGrid require from + to email
        if not cfg.from_email or not cfg.to_email:
            logger.warning(
                "%s config missing from/to email — skipping notification",
                cfg.provider,
            )
            return "skipped"

        if cfg.provider == "smtp" and not (cfg.smtp_host and cfg.smtp_pass_encrypted):
            logger.warning("SMTP config incomplete — skipping notification")
            return "skipped"

        if cfg.provider == "sendgrid" and not cfg.sendgrid_api_key_encrypted:
            logger.warning("SendGrid config missing API key — skipping notification")
            return "skipped"

        provider = self.build_provider(cfg)
        await provider.send(
            from_addr=cfg.from_email,
            to_addr=cfg.to_email,
            subject=subject,
            body=body,
            html_body=html_body,
        )
        return "sent"

    async def notify_for_changelog(
        self, changelog: ChangelogModel, db: AsyncSession
    ) -> str | None:
        """
        Look up the user's active notification config and deliver the changelog.

        Returns the notification_status outcome ("sent" | "skipped" | "failed")
        or None if the user has no notification config configured.
        Never raises — failures are recorded on the changelog instead.
        """
        try:
            cfg = await self.get_active_config(changelog.user_id, db)
            if cfg is None:
                logger.info("No notification config for user %s — nothing to send", changelog.user_id)
                return None

            outcome = await self.send_changelog(cfg, changelog)
            if outcome == "sent":
                logger.info(
                    "Changelog %s sent via %s",
                    changelog.id,
                    cfg.provider,
                )
            return outcome
        except Exception as exc:
            logger.exception("Notification failed for changelog %s", changelog.id)
            return "failed"
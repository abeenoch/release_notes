"""
Notification provider factory.
"""
from __future__ import annotations

from app.services.notify.base import NotifyProviderInterface
from app.services.notify.smtp import SmtpProvider
from app.services.notify.sendgrid import SendGridProvider
from app.services.notify.slack import SlackProvider


def create_notify_provider(
    provider: str,
    smtp_host: str | None = None,
    smtp_port: int = 587,
    smtp_user: str | None = None,
    smtp_pass: str | None = None,
    smtp_secure: bool = False,
    sendgrid_api_key: str | None = None,
    slack_webhook_url: str | None = None,
    slack_channel: str | None = None,
) -> NotifyProviderInterface:
    """Create a notification provider instance."""
    if provider == "smtp":
        return SmtpProvider(
            host=smtp_host or "",
            port=smtp_port,
            user=smtp_user or "",
            password=smtp_pass or "",
            secure=smtp_secure,
        )
    elif provider == "sendgrid":
        return SendGridProvider(api_key=sendgrid_api_key or "")
    elif provider == "slack":
        return SlackProvider(
            webhook_url=slack_webhook_url or "",
            channel=slack_channel,
        )
    else:
        raise ValueError(f"Unknown notification provider: {provider}")
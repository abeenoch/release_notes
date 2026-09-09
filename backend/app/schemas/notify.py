
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


def _ensure_utc(value):
    """SQLite returns naive timestamps (stored as UTC). Attach UTC so the API
    serializes them with an offset and browsers don't misread them as local."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class NotifyConfigCreate(BaseModel):
    provider: str  # smtp, sendgrid, slack

    # SMTP fields
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_secure: bool | None = None

    # SendGrid
    sendgrid_api_key: str | None = None

    # Slack
    slack_webhook_url: str | None = None
    slack_channel: str | None = None

    # Email common
    from_email: str | None = None
    to_email: str | None = None
    subject_prefix: str | None = None


class NotifyConfigUpdate(BaseModel):
    """Partial update for an existing notification config."""
    provider: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_secure: bool | None = None
    sendgrid_api_key: str | None = None
    slack_webhook_url: str | None = None
    slack_channel: str | None = None
    from_email: str | None = None
    to_email: str | None = None
    subject_prefix: str | None = None
    is_active: bool | None = None


class NotifyConfigResponse(BaseModel):
    id: str
    provider: str
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    has_smtp_pass: bool = False
    smtp_secure: bool | None = None
    has_sendgrid_key: bool = False
    slack_webhook_url: str | None = None
    slack_channel: str | None = None
    from_email: str | None = None
    to_email: str | None = None
    subject_prefix: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _utc(cls, v):
        return _ensure_utc(v)


class NotifyConfigListResponse(BaseModel):
    configs: list[NotifyConfigResponse]
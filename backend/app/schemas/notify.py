
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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


class NotifyConfigListResponse(BaseModel):
    configs: list[NotifyConfigResponse]
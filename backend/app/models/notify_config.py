
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import uuid_column

if TYPE_CHECKING:
    from app.models.user import User


class UserNotifyConfig(Base):
    __tablename__ = "user_notify_configs"

    id: Mapped[str] = uuid_column()
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # smtp, sendgrid, slack

    # SMTP
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_pass_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_secure: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # SendGrid
    sendgrid_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Slack
    slack_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    slack_channel: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Common email fields
    from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject_prefix: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notify_configs")
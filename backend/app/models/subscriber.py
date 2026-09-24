from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import uuid_column


class Subscriber(Base):
    """A public-page email subscriber (double opt-in).

    Nothing is emailed until confirm_token is redeemed; unsubscribe_token is
    separate so a leaked confirmation link can't unsubscribe anyone.
    Emails are stored lowercased — (repo_id, email) is unique.
    """

    __tablename__ = "subscribers"
    __table_args__ = (
        UniqueConstraint("repo_id", "email", name="uq_subscribers_repo_email"),
    )

    id: Mapped[str] = uuid_column()
    repo_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    confirm_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

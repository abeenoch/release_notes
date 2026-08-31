from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import uuid_column

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.repo import Repository


class Changelog(Base):
    __tablename__ = "changelogs"

    id: Mapped[str] = uuid_column()
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repo_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    commit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Background task status
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | processing | completed | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # None | sent | skipped | failed

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="changelogs")
    repo: Mapped["Repository"] = relationship("Repository", back_populates="changelogs")
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import uuid_column

if TYPE_CHECKING:
    from app.models.changelog import Changelog
    from app.models.user import User


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = uuid_column()
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Webhook + public-page lookup keys (hot paths): github_repo_id is the
    # authoritative match (survives renames), full_name the legacy fallback.
    github_repo_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)  # "owner/repo"
    clone_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    # Public vanity page (/owner/repo) — strictly opt-in, off by default so
    # registering a (private) repo never accidentally publishes it.
    public_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    last_cloned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Incremental changelog tracking: the HEAD commit covered by the last
    # generated changelog. Next push generates from this commit onward.
    last_generated_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="repos")
    changelogs: Mapped[List["Changelog"]] = relationship(
        "Changelog", back_populates="repo", cascade="all, delete-orphan"
    )

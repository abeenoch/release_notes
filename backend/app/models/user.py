from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import uuid_column

if TYPE_CHECKING:
    from app.models.repo import Repository
    from app.models.changelog import Changelog
    from app.models.user_config import UserLlmConfig
    from app.models.notify_config import UserNotifyConfig


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = uuid_column()
    github_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    github_login: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    repos: Mapped[List["Repository"]] = relationship(
        "Repository", back_populates="user", cascade="all, delete-orphan"
    )
    llm_configs: Mapped[List["UserLlmConfig"]] = relationship(
        "UserLlmConfig", back_populates="user", cascade="all, delete-orphan"
    )
    notify_configs: Mapped[List["UserNotifyConfig"]] = relationship(
        "UserNotifyConfig", back_populates="user", cascade="all, delete-orphan"
    )
    changelogs: Mapped[List["Changelog"]] = relationship(
        "Changelog", back_populates="user", cascade="all, delete-orphan"
    )
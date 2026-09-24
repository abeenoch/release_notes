
from __future__ import annotations

from datetime import datetime, timezone

from typing import Literal

from pydantic import BaseModel, field_validator


def _ensure_utc(value):
    """SQLite returns naive timestamps (stored as UTC). Attach UTC so the API
    serializes them with an offset and browsers don't misread them as local."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value



LlmProviderName = Literal["openai", "anthropic", "ollama", "groq", "openrouter", "commit"]


class LlmConfigCreate(BaseModel):
    provider: LlmProviderName
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None


class LlmConfigUpdate(BaseModel):
    """Partial update for an existing LLM config."""
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    is_active: bool | None = None


class LlmConfigResponse(BaseModel):
    id: str
    provider: str
    model: str | None = None
    base_url: str | None = None
    is_active: bool
    has_api_key: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _utc(cls, v):
        return _ensure_utc(v)



class ChangelogTriggerRequest(BaseModel):
    """Manually trigger a changelog generation."""
    repo_id: str
    from_tag: str | None = None
    to_tag: str | None = None


class ChangelogResponse(BaseModel):
    id: str
    repo_id: str
    from_tag: str | None = None
    to_tag: str | None = None
    version: str | None = None
    previous_version: str | None = None
    summary: str | None = None
    raw_markdown: str | None = None
    llm_provider: str | None = None
    commit_count: int | None = None
    status: str = "pending"
    error_message: str | None = None
    notification_status: str | None = None
    # GitHub Release publish state
    release_url: str | None = None
    published_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "published_at", mode="before")
    @classmethod
    def _utc(cls, v):
        return _ensure_utc(v)


class ChangelogListResponse(BaseModel):
    changelogs: list[ChangelogResponse]
    total: int  # full count ignoring limit/offset (stats read this, not len())


class ChangelogStatsResponse(BaseModel):
    """Dashboard counts — always full totals, never a page length."""
    changelogs_total: int
    changelogs_completed: int
    changelogs_failed: int
    changelogs_published: int


class PublicChangelogResponse(BaseModel):
    """One completed changelog on a public page — no ids, no internals."""
    version: str | None = None
    previous_version: str | None = None
    from_tag: str | None = None
    to_tag: str | None = None
    summary: str | None = None
    raw_markdown: str | None = None
    commit_count: int | None = None
    release_url: str | None = None
    published_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "published_at", mode="before")
    @classmethod
    def _utc(cls, v):
        return _ensure_utc(v)


class PublicPageResponse(BaseModel):
    """Payload for GET /public/{owner}/{repo} — read-only, unauthenticated."""
    full_name: str
    is_private: bool
    changelogs: list[PublicChangelogResponse]
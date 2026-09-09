
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


def _ensure_utc(value: datetime) -> datetime:
    """SQLite returns naive timestamps (stored as UTC). Attach UTC so the API
    serializes them with an offset and browsers don't misread them as local."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class RepoToggleActive(BaseModel):
    """Body for toggling/setting a repo's active state."""
    is_active: bool | None = None


class RepoImportRequest(BaseModel):
    """Body for importing selected repos from GitHub."""
    full_names: list[str]


class GitHubRepoPreview(BaseModel):
    """A repo from GitHub shown in the sync preview (not yet imported)."""
    full_name: str
    default_branch: str
    is_private: bool
    description: str | None = None
    already_added: bool = False


class GitHubRepoListResponse(BaseModel):
    """Response from the sync/preview endpoint."""
    repos: list[GitHubRepoPreview]


class RepoCreate(BaseModel):
    """Body for adding a repo manually (via PAT or GitHub App install)."""
    full_name: str  # "owner/repo"
    clone_url: str | None = None
    default_branch: str = "main"


class RepoResponse(BaseModel):
    id: str
    full_name: str
    default_branch: str
    is_active: bool
    is_private: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _utc(cls, v):
        return _ensure_utc(v)


class RepoListResponse(BaseModel):
    repos: list[RepoResponse]
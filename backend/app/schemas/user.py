
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class GitHubAuthRequest(BaseModel):
    """Request body for GitHub OAuth callback."""
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    github_login: str | None = None
    email: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None

    model_config = {"from_attributes": True}
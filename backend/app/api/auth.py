from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user_id
from app.models.user import User
from app.schemas.user import GitHubAuthRequest, TokenResponse, UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/github", response_model=TokenResponse)
async def login_with_github(
    body: GitHubAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a GitHub OAuth code for a JWT token."""
    try:
        auth_service = AuthService()
        user, token = await auth_service.login_with_github(body.code, db)
        return TokenResponse(access_token=token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's profile."""
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=user.id,
        github_login=user.github_login,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )
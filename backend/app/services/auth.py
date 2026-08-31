
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    encrypt_api_key,
)
from app.models.user import User
from app.services.github import GitHubClient


class AuthService:
    """Handles user registration, login, and token management."""

    def __init__(self) -> None:
        self.github = GitHubClient(
            client_id=settings.github_client_id or "",
            client_secret=settings.github_client_secret or "",
        )

    async def login_with_github(self, code: str, db: AsyncSession) -> tuple[User, str]:
        """
        Exchange a GitHub OAuth code for a user session.

        1. Exchange code for access token
        2. Fetch user info from GitHub
        3. Upsert user in local DB
        4. Return (user, jwt_token)
        """
        # 1. Get GitHub access token
        gh_token = await self.github.exchange_code_for_token(code)

        # 2. Get GitHub user info
        gh_user = await self.github.get_user(gh_token)
        github_id = str(gh_user["id"])
        github_login = gh_user.get("login", "")
        email = gh_user.get("email")
        display_name = gh_user.get("name") or github_login
        avatar_url = gh_user.get("avatar_url")

        # 3. Upsert user in local DB
        result = await db.execute(select(User).where(User.github_id == github_id))
        user = result.scalar_one_or_none()

        if user:
            user.github_login = github_login
            user.github_token = encrypt_api_key(gh_token)
            user.email = email or user.email
            user.display_name = display_name or user.display_name
            user.avatar_url = avatar_url or user.avatar_url
        else:
            user = User(
                github_id=github_id,
                github_login=github_login,
                github_token=encrypt_api_key(gh_token),
                email=email,
                display_name=display_name,
                avatar_url=avatar_url,
            )
            db.add(user)

        await db.flush()

        # 4. Create JWT
        token = create_access_token(user_id=user.id)
        return user, token
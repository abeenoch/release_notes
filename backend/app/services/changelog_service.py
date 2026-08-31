from __future__ import annotations

import os
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_api_key
from app.models.repo import Repository
from app.models.user import User
from app.models.user_config import UserLlmConfig
from app.models.changelog import Changelog as ChangelogModel
from app.services.git_ops import GitClient
from app.services.llm.base import changelog_system_prompt, changelog_user_prompt
from app.services.llm.factory import create_llm_provider
from app.config import settings


class ChangelogService:
    """Orchestrate changelog generation from git tags through LLM."""

    async def generate(
        self,
        user: User,
        repo: Repository,
        from_tag: str | None = None,
        to_tag: str | None = None,
        db: AsyncSession | None = None,
    ) -> ChangelogModel:
        """
        Generate a changelog for a repository.

        1. Ensure repo is cloned
        2. Resolve tags
        3. Get diff + commit log
        4. Call LLM (or commit parser)
        5. Return result
        """
        # 1. Clone / pull the repo
        work_dir = Path(settings.clone_work_dir) / user.id / repo.full_name.replace("/", "_")
        work_dir.mkdir(parents=True, exist_ok=True)

        if repo.clone_url:
            git = GitClient.clone_repo(repo.clone_url, str(work_dir), repo.default_branch)
        else:
            # Clone via GitHub using user's token
            if not user.github_token:
                raise ValueError("No GitHub token available to clone repository")
            gh_token = decrypt_api_key(user.github_token)
            clone_url = f"https://x-access-token:{gh_token}@github.com/{repo.full_name}.git"
            git = GitClient.clone_repo(clone_url, str(work_dir), repo.default_branch)

        # 2. Resolve tags
        from_tag, to_tag = git.resolve_tags(from_tag, to_tag)

        # 3. Get git data
        diff_summary = git.get_diff_summary(from_tag, to_tag)
        diff_patch = git.get_diff_patch(from_tag, to_tag)
        from_name = git.get_tag_name(from_tag)
        to_name = git.get_tag_name(to_tag)

        # 4. Get the user's active LLM config
        llm_provider_name = "commit"
        llm_provider_config: UserLlmConfig | None = None

        if db is not None:
            result = await db.execute(
                select(UserLlmConfig).where(
                    UserLlmConfig.user_id == user.id,
                    UserLlmConfig.is_active == True,  # noqa: E712
                ).limit(1)
            )
            llm_provider_config = result.scalar_one_or_none()

        if llm_provider_config:
            llm_provider_name = llm_provider_config.provider
            api_key = ""
            if llm_provider_config.api_key_encrypted:
                api_key = decrypt_api_key(llm_provider_config.api_key_encrypted)

            llm = create_llm_provider(
                provider=llm_provider_config.provider,
                api_key=api_key,
                model=llm_provider_config.model,
                base_url=llm_provider_config.base_url,
            )
        else:
            llm = create_llm_provider(provider="commit")

        # 5. Generate
        system_prompt = changelog_system_prompt()
        user_prompt = changelog_user_prompt(
            from_tag=from_name,
            to_tag=to_name,
            diff_summary=diff_summary,
            diff_patch=diff_patch,
        )

        markdown = await llm.generate(user_prompt, system_prompt)

        # 6. Count commits
        commit_count = len(diff_summary.split("\n")) if diff_summary != "(no commits found between these refs)" else 0

        # 7. Create the changelog record
        changelog = ChangelogModel(
            user_id=user.id,
            repo_id=repo.id,
            from_tag=from_name,
            to_tag=to_name,
            version=to_name,
            previous_version=from_name,
            summary=f"Changes from {from_name} to {to_name}",
            raw_markdown=markdown,
            llm_provider=llm_provider_name,
            commit_count=commit_count,
        )
        return changelog

    async def generate_and_save(
        self,
        user: User,
        repo: Repository,
        db: AsyncSession,
        from_tag: str | None = None,
        to_tag: str | None = None,
    ) -> ChangelogModel:
        """Generate a changelog and persist it to the database."""
        changelog = await self.generate(user, repo, from_tag, to_tag, db)
        db.add(changelog)
        await db.flush()
        return changelog
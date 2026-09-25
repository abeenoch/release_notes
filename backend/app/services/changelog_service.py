from __future__ import annotations

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

import re


def _fix_changelog_heading(markdown: str, version: str) -> str:
    """Replace the '# Changelog ...' heading with the real version identifier."""
    heading = f"# Changelog — {version}"
    if re.search(r"^#\s+Changelog", markdown, flags=re.MULTILINE):
        return re.sub(r"^#\s+Changelog.*$", heading, markdown, count=1, flags=re.MULTILINE)
    # No heading found — prepend one
    return f"{heading}\n\n{markdown}"


def repo_work_dir(user_id: str, repo: Repository) -> Path:
    """Absolute per-user clone directory.

    Shared by generation and the API's manual-range ref validation, and
    resolved to an absolute path so systemd/uvicorn invocations from
    different CWDs all land in the same directory.
    """
    base_dir = Path(settings.clone_work_dir)
    if not base_dir.is_absolute():
        data_dir = Path(settings.data_dir)
        if not data_dir.is_absolute():
            # config.py defaults are relative to backend/ root
            data_dir = Path(__file__).resolve().parent.parent.parent / data_dir
        base_dir = (data_dir / base_dir.name).resolve() if base_dir.name else data_dir.resolve()
    return base_dir / user_id / repo.full_name.replace("/", "_")


def resolve_range_base(
    git: GitClient,
    from_ref: str | None,
    to_ref: str | None,
    last_generated_commit: str | None,
) -> tuple[str | None, bool]:
    """Choose the base ref for a non-release range, and whether it's incremental.

    Tag-derived bases are correct for releases ("changes since the previous
    release") but wrong for plain pushes: a push creates no tag, so the base
    never moves and every new changelog re-covers everything since the last
    tag — yesterday's work reappearing in today's changelog, with the commit
    count creeping up by one each time.

    When the last generated commit sits strictly between the tag-derived base
    and the target, it is the honest boundary: prefer it. Returns the base
    unchanged when it doesn't (stale/rewritten history, or a genuinely newer
    tag), so nothing regresses.
    """
    if not from_ref or not to_ref or not last_generated_commit:
        return from_ref, False
    if not git.is_ancestor(from_ref, last_generated_commit):
        return from_ref, False
    if not git.is_ancestor(last_generated_commit, to_ref):
        return from_ref, False
    if git.is_ancestor(to_ref, last_generated_commit):
        # Tracking already sits exactly at the target (nothing new, e.g. a
        # regenerate on an unchanged repo). Switching bases here would emit
        # an empty "no commits" changelog that then absorbs the previous,
        # meaningful row for the same tag — keep the tag base instead.
        return from_ref, False
    return last_generated_commit, True


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
        2. Resolve the commit range:
           - explicit from/to tags if given (e.g. tag creation events)
           - otherwise incremental: from the repo's last generated commit → HEAD
           - otherwise full history (root commit → HEAD)
        3. Get diff + commit log
        4. Call LLM (or commit parser)
        5. Return result
        """
        # 1. Clone / pull the repo (work dir shared with API ref validation)
        work_dir = repo_work_dir(user.id, repo)
        work_dir.mkdir(parents=True, exist_ok=True)

        if repo.clone_url:
            git = GitClient.clone_repo(repo.clone_url, str(work_dir), repo.default_branch)
        else:
            # Clone via GitHub using the user's token. The token travels in
            # the git http.extraHeader (never in the clone URL) so it is not
            # persisted in .git/config's origin URL.
            if not user.github_token:
                raise ValueError("No GitHub token available to clone repository")
            gh_token = decrypt_api_key(user.github_token)
            clone_url = f"https://github.com/{repo.full_name}.git"
            git = GitClient.clone_repo(clone_url, str(work_dir), repo.default_branch, token=gh_token)

        # 2. Resolve the commit range
        incremental = False
        full_history = False

        if from_tag and to_tag:
            # Explicit range (e.g. tag-creation or release events)
            from_ref, to_ref = from_tag, to_tag
        else:
            from_ref, to_ref = git.resolve_tags(from_tag, to_tag)
            # Pushes don't create tags, so a tag-derived base would never
            # advance and every changelog would re-cover everything since the
            # last tag. Prefer the last generated commit when it's newer
            # (skip this for real tag targets — releases keep "since the
            # previous release" semantics).
            if from_ref and not git.has_tag(to_ref or ""):
                from_ref, incremental = resolve_range_base(
                    git, from_ref, to_ref, repo.last_generated_commit
                )
            if not from_ref:
                # Tagless repo — try incremental from the last generated commit
                if repo.last_generated_commit:
                    from_ref = repo.last_generated_commit
                    incremental = True
                else:
                    # First-ever generation with no tags → full history
                    from_ref = git.get_root_sha()
                    full_history = True

        # HARDENING: only diff an incremental range when it's actually valid.
        # A force-push / history rewrite can make the stored from_ref (or a
        # passed from-tag) no longer an ancestor of to_ref. In that case we
        # reset to full history (and clear incremental tracking) so we never
        # emit an overlapping/misleading partial range.
        if from_ref and to_ref and not git.is_ancestor(from_ref, to_ref):
            from_ref = git.get_root_sha()
            full_history = True
            incremental = False

        # 3. Get git data
        diff_summary = git.get_diff_summary(from_ref, to_ref)
        diff_patch = git.get_diff_patch(from_ref, to_ref)
        from_name = git.get_tag_name(from_ref)
        to_name = git.get_tag_name(to_ref) if to_ref else "HEAD"
        head_sha = git.get_head_sha()

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

        # 5. Generate — pass the real version identifier so the LLM doesn't
        #    invent one (e.g. a hardcoded "v1.0.0")
        system_prompt = changelog_system_prompt()
        user_prompt = changelog_user_prompt(
            from_tag=from_name,
            to_tag=to_name,
            diff_summary=diff_summary,
            diff_patch=diff_patch,
            version=to_name,
        )

        markdown = await llm.generate(user_prompt, system_prompt)

        # 5b. Post-process: force the heading to the real version identifier
        #     (guards against the LLM inventing "v1.0.0" anyway)
        markdown = _fix_changelog_heading(markdown, to_name)

        # 6. Count commits (sentinel strings mean zero real commits)
        if diff_summary in ("(no commits found between these refs)", "(could not retrieve commits)"):
            commit_count = 0
        else:
            commit_count = sum(1 for line in diff_summary.split("\n") if line.strip() and not line.startswith("... and "))

        # 7. Human-readable summary
        if full_history:
            summary = f"Full history through {to_name}"
        elif incremental:
            summary = f"Updates since {from_name}, through {to_name}"
        else:
            summary = f"Changes from {from_name} to {to_name}"

        # 8. Track incremental progress: if this generation reached the
        #    current HEAD, remember it so the next push generates only
        #    the new commits.
        if db is not None and (to_ref == "HEAD" or to_ref.startswith(head_sha[:7])):
            repo.last_generated_commit = head_sha

        # 9. Create the changelog record
        changelog = ChangelogModel(
            user_id=user.id,
            repo_id=repo.id,
            from_tag=from_name,
            to_tag=to_name,
            version=to_name,
            previous_version=from_name,
            summary=summary,
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
        await db.commit()
        return changelog
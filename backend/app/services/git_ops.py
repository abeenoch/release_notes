
from __future__ import annotations

import logging
from pathlib import Path

import base64
from contextlib import nullcontext as _nullcontext
from git import Repo as GitRepo
from git.exc import GitCommandError

logger = logging.getLogger(__name__)


def _semver_sort_key(tag: str) -> list[tuple[int, int | str]]:
    """Ordering key for version-ish tags that can never raise.

    The old key mixed ints and strings (`1.2` → [1,2] vs `1f21a87` → ['1f21a87']),
    so sorting a repo whose tags were commit SHAs raised
    `TypeError: '<' not supported between instances of 'str' and 'int'` and the
    whole changelog generation failed. Tagging each part with its type makes
    every comparison well-defined: numeric parts sort before non-numeric ones
    at the same position, and SHA-style tags get a stable (if semantically
    arbitrary) order.
    """
    return [
        (0, int(part)) if part.isdigit() else (1, part)
        for part in tag.lstrip("v").split(".")
    ]


class GitClient:
    """Wrapper around git operations for the changelog tool."""

    def __init__(self, repo_path: str, max_diff_length: int = 15_000) -> None:
        self.repo_path = repo_path
        self.max_diff_length = max_diff_length
        self._repo: GitRepo | None = None

    @property
    def repo(self) -> GitRepo:
        if self._repo is None:
            self._repo = GitRepo(self.repo_path)
        return self._repo

    def resolve_tags(self, from_tag: str | None = None, to_tag: str | None = None) -> tuple[str, str]:
        """
        Resolve the 'from' and 'to' tags.
        Returns (from_tag, to_tag) where from_tag is the older/base tag.

        If only one tag exists or none exist, falls back to:
        - to_tag: HEAD (latest commit)
        - from_tag: root commit (or empty string for full history)
        """
        if from_tag and to_tag:
            return from_tag, to_tag

        all_tag_names = [t.name for t in self.repo.tags if t.name]
        tags = sorted(
            [t for t in all_tag_names if t.startswith("v") or (t and t[0].isdigit())],
            key=_semver_sort_key,
        )
        ignored = len(all_tag_names) - len(tags)
        if ignored:
            logger.info(
                "resolve_tags: ignoring %d non-semver tag(s) (only v*/digit tags used)",
                ignored,
            )

        latest = tags[-1] if tags else "HEAD"
        previous = tags[-2] if len(tags) >= 2 else (tags[-1] if tags else None)
        return from_tag or previous, to_tag or latest

    def is_ancestor(self, ancestor_ref: str, descendant_ref: str = "HEAD") -> bool:
        """
        Return True if ancestor_ref is an ancestor of descendant_ref.
        False also when the refs don't resolve (e.g. rewritten history).
        """
        try:
            # `git merge-base --is-ancestor` exits 0 (no output) if ancestor,
            # non-zero otherwise; GitPython raises on non-zero exit.
            self.repo.git.merge_base("--is-ancestor", ancestor_ref, descendant_ref)
            return True
        except GitCommandError:
            return False

    def get_diff_summary(self, from_ref: str | None, to_ref: str, max_commits: int = 300) -> str:
        """Get the commit log between two refs.

        No silent fallback is attempted — if the range is invalid the caller
        is responsible for resetting tracking, so we never emit an overlapping
        "recent N commits" dump. Large histories are truncated to the newest
        `max_commits` so LLM prompts stay bounded.
        """
        try:
            if from_ref:
                commits = list(self.repo.iter_commits(f"{from_ref}..{to_ref}"))
            else:
                commits = list(self.repo.iter_commits(to_ref))
        except GitCommandError:
            return "(could not retrieve commits)"

        if not commits:
            return "(no commits found between these refs)"

        total = len(commits)
        if total > max_commits:
            logger.info(
                "Truncating diff summary: %d commits → newest %d", total, max_commits
            )
            # iter_commits yields newest-first, so slice keeps the newest.
            commits = commits[:max_commits]

        lines: list[str] = []
        for commit in commits:
            date = commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")
            msg = commit.message.split("\n")[0].strip()
            lines.append(f"[{commit.hexsha[:7]}] {date} — {msg}")
        if total > max_commits:
            lines.append(f"... and {total - max_commits} older commits omitted")
        return "\n".join(lines)

    def get_diff_patch(self, from_ref: str, to_ref: str) -> str | None:
        """Get the raw diff (code changes) between two refs, truncated."""
        try:
            diff = self.repo.git.diff(from_ref, to_ref)
            if len(diff) > self.max_diff_length:
                return diff[:self.max_diff_length] + "\n\n... [diff truncated]"
            return diff
        except GitCommandError:
            return None

    def get_tag_name(self, ref: str) -> str:
        """Get the tag name for a ref (e.g. 'v1.2.3' or 'HEAD')."""
        if ref == "HEAD":
            try:
                desc = self.repo.git.describe("--tags", "--exact-match", "HEAD")
                return desc.strip() or "HEAD"
            except GitCommandError:
                return "HEAD (unreleased)"
        return ref

    def get_head_sha(self) -> str:
        """Get the full SHA of the current HEAD commit."""
        return self.repo.head.commit.hexsha

    def get_root_sha(self) -> str:
        """Get the SHA of the first (root) commit on the current branch."""
        return self.repo.git.rev_list("--max-parents=0", "HEAD").split("\n")[0].strip()

    def get_repo_url(self) -> str:
        """Get the current repository URL (origin remote)."""
        try:
            origin = self.repo.remotes.origin
            return origin.url
        except (AttributeError, ValueError):
            return "unknown"

    @classmethod
    def clone_repo(
        cls,
        clone_url: str,
        clone_path: str,
        branch: str = "main",
        token: str | None = None,
    ) -> "GitClient":
        """Clone a repository and return a GitClient for it.

        When `token` is given, it is passed via the
        `http.extraHeader` git config (Authorization: Bearer …) so the
        secret never lands in `.git/config`'s origin URL. `clone_url`
        must therefore be token-free in that case.
        """
        path = Path(clone_path)
        # Only treat as existing if it's a valid git repo (has .git dir/file)
        is_valid_repo = path.exists() and (path / ".git").exists()

        # Token travels via git's GIT_CONFIG_* env config (http.extraHeader),
        # never in the clone URL (which persists it in .git/config) and never
        # as a CLI arg (which would land in `ps` output). GitPython's `env=`
        # kwarg is NOT a supported parameter — it leaks the dict into the
        # command line and breaks fetch parsing — so use custom_environment.
        from git.cmd import Git as GitCmd
        extra_env = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            # GitHub's git-over-HTTPS endpoint rejects raw `Authorization: Bearer`
            # / `token` headers (unlike the REST API) — Basic with the OAuth
            # username `x-access-token` is what it accepts.
            "GIT_CONFIG_VALUE_0": "Authorization: Basic "
            + base64.b64encode(f"x-access-token:{token}".encode()).decode(),
        } if token else {}

        def _git_env(git_cmd: GitCmd):
            return git_cmd.custom_environment(**extra_env) if extra_env else _nullcontext()

        if is_valid_repo:
            # Pull instead. NOTE: use repo.git (flag-safe CLI interface), not
            # Remote.fetch — `fetch("--tags", "--force")` silently swallowed
            # --force into the `progress` parameter, so tags were NEVER updated
            # after the initial clone.
            repo = GitRepo(clone_path)
            try:
                with _git_env(repo.git):
                    repo.git.fetch("--tags", "--force", "origin")
            except Exception:
                logger.warning("fetch --tags failed for %s", clone_path, exc_info=True)
            try:
                with _git_env(repo.git):
                    repo.git.checkout(branch)
            except Exception:
                logger.warning("checkout %s failed for %s", branch, clone_path, exc_info=True)
            try:
                with _git_env(repo.git):
                    repo.git.pull("--ff-only", "origin", branch)
            except Exception:
                logger.warning("pull --ff-only failed for %s", clone_path, exc_info=True)
        else:
            # Remove any stale empty/partial dir, then clone fresh
            if path.exists():
                import shutil
                shutil.rmtree(clone_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with _git_env(GitCmd()):
                GitRepo.clone_from(
                    clone_url, clone_path, branch=branch,
                    multi_options=["--tags"],
                )
        return cls(repo_path=clone_path)
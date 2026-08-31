
from __future__ import annotations

import os
from pathlib import Path

from git import Repo as GitRepo
from git.exc import GitCommandError


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
        """
        if from_tag and to_tag:
            return from_tag, to_tag

        tags = sorted(
            [t.name for t in self.repo.tags if t.name.startswith("v") or t.name[0].isdigit()],
            key=lambda t: [int(p) if p.isdigit() else p for p in t.lstrip("v").split(".")],
        )

        if len(tags) < 2:
            if len(tags) == 1:
                return tags[0], "HEAD"
            raise ValueError(
                "Could not find at least two version tags in this repository. "
                "Please specify --from-tag and --to-tag manually."
            )

        latest = tags[-1]
        previous = tags[-2]
        return from_tag or previous, to_tag or latest

    def get_diff_summary(self, from_ref: str, to_ref: str) -> str:
        """Get the commit log between two refs."""
        try:
            commits = list(self.repo.iter_commits(f"{from_ref}..{to_ref}"))
            if not commits:
                return "(no commits found between these refs)"

            lines: list[str] = []
            for commit in commits:
                date = commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")
                msg = commit.message.split("\n")[0].strip()
                lines.append(f"[{commit.hexsha[:7]}] {date} — {msg}")
            return "\n".join(lines)

        except GitCommandError:
            # Try with from_ref alone (e.g., when from_ref is a parent)
            try:
                commits = list(self.repo.iter_commits(to_ref, max_count=50))
                lines = []
                for commit in commits:
                    date = commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    msg = commit.message.split("\n")[0].strip()
                    lines.append(f"[{commit.hexsha[:7]}] {date} — {msg}")
                return "\n".join(lines)
            except GitCommandError:
                return "(could not retrieve commits)"

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

    def get_repo_url(self) -> str:
        """Get the current repository URL (origin remote)."""
        try:
            origin = self.repo.remotes.origin
            return origin.url
        except (AttributeError, ValueError):
            return "unknown"

    @classmethod
    def clone_repo(cls, clone_url: str, clone_path: str, branch: str = "main") -> "GitClient":
        """Clone a repository and return a GitClient for it."""
        path = Path(clone_path)
        if path.exists():
            # Pull instead
            repo = GitRepo(clone_path)
            repo.remotes.origin.fetch("--tags", "--force")
            repo.git.checkout(branch)
            repo.remotes.origin.pull()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            GitRepo.clone_from(clone_url, clone_path, branch=branch, multi_options=["--tags"])
        return cls(repo_path=clone_path)
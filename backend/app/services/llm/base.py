"""
Base LLM provider interface and prompt builders.

Ported from TypeScript src/llm/index.ts
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LlmProviderInterface(ABC):
    """Implement this to add new AI backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """User-friendly name for the provider."""
        ...

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Send a system + user prompt and return the text response."""
        ...


def changelog_system_prompt() -> str:
    """Build the system prompt for changelog generation."""
    return """You are a changelog generator. Your task is to summarize git diffs into a clean, well-structured changelog.

Rules:
1. Categorize changes under: Features, Bug Fixes, Documentation, Chores, Refactors, Performance, Other
2. Use clear, user-friendly language — avoid internal jargon and commit-hash references
3. If the diff contains breaking changes, add a "BREAKING CHANGES" section at the top
4. Keep descriptions concise (one line per change when possible)
5. Output ONLY valid markdown — no extra commentary

Format:
# Changelog — v{new_version}

## Summary
{1-2 sentence high-level summary of this release}

## Features
- {description of each feature}

## Bug Fixes
- {description of each fix}

## Other Changes
- {docs, chores, refactors, perf, etc.}

## Full Commit Log
{For reference, include the raw commit list}"""


def changelog_user_prompt(
    from_tag: str,
    to_tag: str,
    diff_summary: str,
    diff_patch: str | None = None,
) -> str:
    """Build the user prompt from diff data."""
    prompt = (
        f"Generate a changelog for the changes between {from_tag} and {to_tag}.\n\n"
        f"## Commit Summary (messages)\n"
        f"{diff_summary}\n"
    )
    if diff_patch:
        prompt += f"\n## Code Diff (truncated)\n{diff_patch}\n"
    prompt += "\nOutput the changelog in markdown format as specified."
    return prompt
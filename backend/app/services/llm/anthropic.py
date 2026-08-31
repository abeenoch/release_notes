"""
Anthropic (Claude) LLM provider.

Ported from TypeScript src/llm/anthropic.ts
"""
from __future__ import annotations

from anthropic import AsyncAnthropic

from app.services.llm.base import LlmProviderInterface


class AnthropicProvider(LlmProviderInterface):
    name = "Anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        response = await self.client.messages.create(
            model=self.model,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.3,
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        return "(no response from LLM)"
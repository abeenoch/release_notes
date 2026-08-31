"""
OpenRouter LLM provider (multi-model gateway via OpenAI-compatible API).

Ported from TypeScript src/llm/openrouter.ts
"""
from __future__ import annotations

from openai import AsyncOpenAI

from app.services.llm.base import LlmProviderInterface

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LlmProviderInterface):
    name = "OpenRouter"

    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet") -> None:
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://github.com/user/auto-changelog",
                "X-Title": "auto-changelog",
            },
        )
        self.model = model

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.3,
            max_tokens=4096,
        )
        return response.choices[0].message.content or "(no response from LLM)"
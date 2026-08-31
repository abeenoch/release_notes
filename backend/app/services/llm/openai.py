"""
OpenAI LLM provider.

Ported from TypeScript src/llm/openai.ts
"""
from __future__ import annotations

from openai import AsyncOpenAI

from app.services.llm.base import LlmProviderInterface


class OpenAiProvider(LlmProviderInterface):
    name = "OpenAI"

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self.client = AsyncOpenAI(api_key=api_key)
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
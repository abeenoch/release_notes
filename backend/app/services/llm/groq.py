"""
Groq LLM provider (OpenAI-compatible API).

Ported from TypeScript src/llm/groq.ts
"""
from __future__ import annotations

from openai import AsyncOpenAI

from app.services.llm.base import LlmProviderInterface

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(LlmProviderInterface):
    name = "Groq"

    def __init__(self, api_key: str, model: str = "mixtral-8x7b-32768") -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
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
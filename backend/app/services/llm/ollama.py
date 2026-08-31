"""
Ollama (local LLMs) provider.

Ported from TypeScript src/llm/ollama.ts
"""
from __future__ import annotations

import httpx

from app.services.llm.base import LlmProviderInterface


class OllamaProvider(LlmProviderInterface):
    name = "Ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.3") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        url = f"{self.base_url}/api/chat"
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "(no response from LLM)")
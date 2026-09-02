"""
LLM provider factory — creates the right provider based on config.
"""
from __future__ import annotations

from app.services.llm.base import LlmProviderInterface
from app.services.llm.openai import OpenAiProvider
from app.services.llm.anthropic import AnthropicProvider
from app.services.llm.ollama import OllamaProvider
from app.services.llm.groq import GroqProvider
from app.services.llm.openrouter import OpenRouterProvider
from app.services.llm.commit import CommitProvider


def create_llm_provider(
    provider: str,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LlmProviderInterface:
    """Create an LLM provider instance."""
    if provider == "openai":
        return OpenAiProvider(
            api_key=api_key or "",
            model=model or "gpt-4o",
        )
    elif provider == "anthropic":
        return AnthropicProvider(
            api_key=api_key or "",
            model=model or "claude-sonnet-4-20250514",
        )
    elif provider == "ollama":
        return OllamaProvider(
            base_url=base_url or "http://localhost:11434",
            model=model or "llama3.3",
        )
    elif provider == "groq":
        return GroqProvider(
            api_key=api_key or "",
            model=model or "openai/gpt-oss-120b",
        )
    elif provider == "openrouter":
        return OpenRouterProvider(
            api_key=api_key or "",
            model=model or "anthropic/claude-3.5-sonnet",
        )
    elif provider == "commit":
        return CommitProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
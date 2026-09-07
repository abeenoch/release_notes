"""
Base notification provider interface.

Ported from TypeScript src/notify/index.ts
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class NotifyProviderInterface(ABC):
    """Implement this to add new notification backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """User-friendly name."""
        ...

    @abstractmethod
    async def send(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        """Send a notification. html_body, when given, is a pre-rendered rich
        HTML alternative (falls back to a simple markdown-to-HTML conversion)."""
        ...
"""LLM client protocol — allows swapping providers without changing agent code."""
from __future__ import annotations

from typing import Any, Protocol


class LLMClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        ...

    async def embed(self, text: str) -> list[float]:
        ...

    async def close(self) -> None:
        ...

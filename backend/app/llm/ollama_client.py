"""Async Ollama client wrapping /api/chat and /api/embeddings."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class OllamaClient:
    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.host = (host or settings.OLLAMA_HOST).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.embedding_model = embedding_model or settings.EMBEDDING_MODEL
        self._client = httpx.AsyncClient(timeout=timeout)

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        if json_mode:
            payload["format"] = "json"

        log.debug("Ollama chat request: model=%s json_mode=%s", self.model, json_mode)
        r = await self._client.post(f"{self.host}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
        # Ollama response shape: {"message": {"role": "assistant", "content": "..."}, ...}
        return data["message"]["content"]

    async def chat_json(self, messages: list[dict[str, str]], **kw: Any) -> Any:
        """Convenience wrapper: returns parsed JSON from a json_mode chat call."""
        raw = await self.chat(messages, json_mode=True, **kw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning("Failed to parse JSON from LLM: %s; raw=%r", e, raw[:300])
            raise

    async def embed(self, text: str) -> list[float]:
        r = await self._client.post(
            f"{self.host}/api/embeddings",
            json={"model": self.embedding_model, "prompt": text},
        )
        r.raise_for_status()
        return r.json()["embedding"]

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

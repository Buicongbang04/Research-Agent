"""Embeddings wrapper over Ollama's nomic-embed-text."""
from __future__ import annotations

from app.llm.ollama_client import OllamaClient


async def embed_text(text: str) -> list[float]:
    """Returns a 768-dim embedding vector for the given text."""
    async with OllamaClient() as llm:
        return await llm.embed(text)

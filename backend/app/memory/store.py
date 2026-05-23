"""Long-term memory store backed by Postgres + pgvector."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory
from app.memory.embeddings import embed_text

log = logging.getLogger(__name__)


async def add_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    content: str,
    source_type: str | None = None,
    source_ref: str | None = None,
) -> Memory:
    embedding = await embed_text(content)
    mem = Memory(
        user_id=user_id,
        content=content,
        embedding=embedding,
        source_type=source_type,
        source_ref=source_ref,
    )
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    return mem


async def search_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> list[Memory]:
    """Return top-k memories most similar to `query` via cosine distance."""
    query_emb = await embed_text(query)
    # pgvector exposes `.cosine_distance(...)` on Vector columns
    stmt = (
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.embedding.cosine_distance(query_emb))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

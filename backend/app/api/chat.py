"""Chat endpoint: conversation with long-term memory (pgvector retrieval)."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.db.models import Conversation, Message, MessageRole
from app.db.session import AsyncSessionLocal
from app.llm.ollama_client import OllamaClient
from app.memory.store import add_memory, search_memories
from app.schemas.chat import ChatRequest, ChatResponse

log = logging.getLogger(__name__)
router = APIRouter()


SYSTEM_PROMPT = """You are a helpful research assistant. You may be given relevant
memories from past interactions to inform your answer. Cite them naturally when
useful, but do not fabricate facts not present in either the memories or the
ongoing conversation."""


async def _persist_memory(user_id: uuid.UUID, content: str, source_ref: str) -> None:
    """Background-task helper to write a memory after responding to the user."""
    async with AsyncSessionLocal() as session:
        try:
            await add_memory(session, user_id=user_id, content=content, source_type="chat", source_ref=source_ref)
        except Exception as e:
            log.warning("Failed to persist memory: %s", e)


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    background: BackgroundTasks,
    db: DbSession,
    user: CurrentUser,
) -> ChatResponse:
    # Get or create conversation
    if payload.conversation_id is not None:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            user_id=user.id,
            title=payload.message[:80],
        )
        db.add(conversation)
        await db.flush()  # populate id

    # Retrieve recent messages in this conversation
    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    recent_msgs = list(reversed(msgs_result.scalars().all()))

    # Semantic memory recall
    try:
        memories = await search_memories(db, user_id=user.id, query=payload.message, top_k=4)
    except Exception as e:
        log.warning("Memory search failed: %s", e)
        memories = []

    # Build messages for the LLM
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if memories:
        memory_block = "Relevant memories from past conversations:\n" + "\n".join(
            f"- {m.content}" for m in memories
        )
        messages.append({"role": "system", "content": memory_block})
    for m in recent_msgs:
        messages.append({"role": m.role.value, "content": m.content})
    messages.append({"role": "user", "content": payload.message})

    # LLM call
    async with OllamaClient() as llm:
        try:
            response_text = await llm.chat(messages, temperature=0.5, max_tokens=1024)
        except Exception as e:
            log.exception("Chat LLM failed")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM error: {e}")

    # Persist user + assistant messages
    db.add(Message(conversation_id=conversation.id, role=MessageRole.user, content=payload.message))
    db.add(Message(conversation_id=conversation.id, role=MessageRole.assistant, content=response_text))
    await db.commit()
    await db.refresh(conversation)

    # Background: persist this exchange as a memory for future recall
    background.add_task(
        _persist_memory,
        user.id,
        f"User asked: {payload.message}\nAssistant answered: {response_text[:500]}",
        str(conversation.id),
    )

    return ChatResponse(
        conversation_id=conversation.id,
        response=response_text,
        used_memories=len(memories),
    )

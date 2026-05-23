"""Planner agent: decompose the user prompt into 3-5 search queries (subtasks)."""
from __future__ import annotations

import json
import logging

from app.agents.progress import publish_event
from app.agents.state import ResearchState
from app.llm.ollama_client import OllamaClient

log = logging.getLogger(__name__)

SYSTEM = """You are a research planner. Given a user research prompt, decompose it
into 3 to 5 concise search queries suitable for searching the arXiv academic database.
Each query should target a distinct sub-aspect of the topic.

You MUST return ONLY a valid JSON object with this EXACT shape (no extra fields, no nesting):
{"subtasks": ["query string 1", "query string 2", "query string 3"]}

Rules:
- Each item in "subtasks" MUST be a plain string (NOT an object).
- Each query: 3-8 words, in English, no quotes, no punctuation."""


def _coerce_subtasks(raw: object) -> list[str]:
    """Accept list[str] or list[dict] (use first string-valued field) and normalize."""
    out: list[str] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
        elif isinstance(item, dict):
            # Prefer common keys, else first string value
            for key in ("query", "name", "title", "description", "subtask"):
                v = item.get(key)
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
                    break
            else:
                for v in item.values():
                    if isinstance(v, str) and v.strip():
                        out.append(v.strip())
                        break
    return out


async def planner_node(state: ResearchState) -> dict:
    prompt = state["prompt"]
    report_id = state.get("report_id")

    progress = [await publish_event(report_id, "planner_start", {"prompt": prompt})]

    async with OllamaClient() as llm:
        try:
            data = await llm.chat_json(
                [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            subtasks = _coerce_subtasks(data.get("subtasks", []))
            if not subtasks:
                subtasks = [prompt[:120]]
        except (json.JSONDecodeError, KeyError, Exception) as e:
            log.warning("Planner LLM failed (%s); falling back to prompt-as-query", e)
            subtasks = [prompt[:120]]

    progress.append(
        await publish_event(report_id, "planner_done", {"subtasks": subtasks, "count": len(subtasks)})
    )
    return {"subtasks": subtasks[:5], "progress": progress}

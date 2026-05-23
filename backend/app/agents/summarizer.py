"""Summarizer agent: for each paper, extract key findings & methods via the LLM."""
from __future__ import annotations

import asyncio
import logging

from app.agents.progress import publish_event
from app.agents.state import ResearchState
from app.llm.ollama_client import OllamaClient

log = logging.getLogger(__name__)

SYSTEM = """You are a research summarizer. Given a paper's title and abstract,
extract the most important information as a JSON object with this exact shape:
{
  "key_points": ["point 1", "point 2", "point 3"],
  "methods": "1-2 sentence description of the approach/methodology",
  "findings": "1-2 sentence description of the main result or contribution"
}
Be concise, factual, and ground every claim in the abstract."""


async def _summarize_one(llm: OllamaClient, paper: dict) -> dict:
    user_msg = (
        f"Title: {paper['title']}\n\n"
        f"Authors: {', '.join(paper.get('authors', [])[:3])}\n\n"
        f"Abstract:\n{paper['abstract']}"
    )
    try:
        data = await llm.chat_json(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
        )
        return {
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "pdf_url": paper["pdf_url"],
            "authors": paper.get("authors", []),
            "key_points": data.get("key_points", []),
            "methods": data.get("methods", ""),
            "findings": data.get("findings", ""),
        }
    except Exception as e:
        log.warning("Summarizer failed for %s: %s", paper.get("arxiv_id"), e)
        return {
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "pdf_url": paper["pdf_url"],
            "authors": paper.get("authors", []),
            "key_points": [paper["abstract"][:200] + "..."],
            "methods": "",
            "findings": "",
        }


async def summarizer_node(state: ResearchState) -> dict:
    report_id = state.get("report_id")
    papers = state.get("search_results", [])

    progress = [await publish_event(report_id, "summarizer_start", {"papers": len(papers)})]

    if not papers:
        return {
            "summaries": [],
            "progress": progress + [await publish_event(report_id, "summarizer_done", {"summaries": 0})],
        }

    async with OllamaClient() as llm:
        # Sequential to avoid overloading local Ollama with parallel calls
        summaries = []
        for i, paper in enumerate(papers, 1):
            summary = await _summarize_one(llm, paper)
            summaries.append(summary)
            progress.append(
                await publish_event(
                    report_id,
                    "summarizer_progress",
                    {"index": i, "total": len(papers), "arxiv_id": paper["arxiv_id"]},
                )
            )

    progress.append(await publish_event(report_id, "summarizer_done", {"summaries": len(summaries)}))
    return {"summaries": summaries, "progress": progress}

"""Writer agent: synthesize all summaries into a final markdown report."""
from __future__ import annotations

import logging

from app.agents.progress import publish_event
from app.agents.state import ResearchState
from app.llm.ollama_client import OllamaClient

log = logging.getLogger(__name__)

SYSTEM = """You are a research writer. Given a set of paper summaries and the user's
original research question, produce a well-structured markdown research report.

Structure:
# Title (derived from the question)
## Introduction (2-3 sentences setting up the topic)
## Key Findings (group related findings with citations like [1], [2])
## Methods Overview (briefly describe common methodological themes)
## Limitations & Open Questions (1 short paragraph)
## Conclusion (2-3 sentences)
## References (numbered list, format: "[N] Authors. Title. arXiv:ID. [link](pdf_url)")

Cite every claim with [N] references corresponding to the References list.
Be factual; do not invent results not present in the summaries."""


def _build_user_message(prompt: str, summaries: list[dict]) -> str:
    lines = [f"Research question: {prompt}", "", "Paper summaries:"]
    for i, s in enumerate(summaries, 1):
        authors = ", ".join(s.get("authors", [])[:3])
        if len(s.get("authors", [])) > 3:
            authors += " et al."
        lines.append(f"\n[{i}] {s['title']}")
        lines.append(f"    Authors: {authors}")
        lines.append(f"    arXiv: {s['arxiv_id']}")
        lines.append(f"    PDF: {s['pdf_url']}")
        if s.get("key_points"):
            lines.append(f"    Key points:")
            for kp in s["key_points"]:
                lines.append(f"      - {kp}")
        if s.get("methods"):
            lines.append(f"    Methods: {s['methods']}")
        if s.get("findings"):
            lines.append(f"    Findings: {s['findings']}")
    return "\n".join(lines)


def _fallback_report(prompt: str, summaries: list[dict]) -> str:
    """If LLM fails, assemble a basic deterministic report so the user gets something."""
    lines = [f"# Research report: {prompt}", "", "## Summaries"]
    for i, s in enumerate(summaries, 1):
        lines.append(f"\n### [{i}] {s['title']}")
        for kp in s.get("key_points", []):
            lines.append(f"- {kp}")
        if s.get("findings"):
            lines.append(f"\n**Findings:** {s['findings']}")
    lines.append("\n## References")
    for i, s in enumerate(summaries, 1):
        authors = ", ".join(s.get("authors", [])[:3])
        lines.append(f"{i}. {authors}. {s['title']}. arXiv:{s['arxiv_id']}. [pdf]({s['pdf_url']})")
    return "\n".join(lines)


async def writer_node(state: ResearchState) -> dict:
    report_id = state.get("report_id")
    prompt = state["prompt"]
    summaries = state.get("summaries", [])

    progress = [await publish_event(report_id, "writer_start", {"summaries": len(summaries)})]

    if not summaries:
        report = f"# Research report: {prompt}\n\n_No papers were found for this topic._"
        progress.append(await publish_event(report_id, "writer_done", {"length": len(report)}))
        return {"report": report, "progress": progress}

    user_msg = _build_user_message(prompt, summaries)
    async with OllamaClient() as llm:
        try:
            report = await llm.chat(
                [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
                temperature=0.4,
                max_tokens=2048,
            )
        except Exception as e:
            log.warning("Writer LLM failed (%s); using deterministic fallback", e)
            report = _fallback_report(prompt, summaries)

    progress.append(await publish_event(report_id, "writer_done", {"length": len(report)}))
    return {"report": report, "progress": progress}

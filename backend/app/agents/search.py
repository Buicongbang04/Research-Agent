"""Search agent: query arXiv for each subtask, dedupe results."""
from __future__ import annotations

import logging

from app.agents.progress import publish_event
from app.agents.state import ResearchState
from app.tools.arxiv_search import arxiv_search

log = logging.getLogger(__name__)

# Per-subtask cap to keep total papers manageable for the summarizer
PER_QUERY = 3
TOTAL_CAP = 8


async def search_node(state: ResearchState) -> dict:
    report_id = state.get("report_id")
    subtasks = state.get("subtasks", [])

    progress = [await publish_event(report_id, "search_start", {"queries": subtasks})]

    seen: set[str] = set()
    aggregated: list[dict] = []

    for query in subtasks:
        try:
            papers = await arxiv_search(query, max_results=PER_QUERY)
        except Exception as e:
            log.warning("arXiv search failed for %r: %s", query, e)
            await publish_event(report_id, "search_query_failed", {"query": query, "error": str(e)})
            continue

        for p in papers:
            if p.arxiv_id in seen:
                continue
            seen.add(p.arxiv_id)
            aggregated.append(p.to_dict())
            if len(aggregated) >= TOTAL_CAP:
                break

        progress.append(
            await publish_event(report_id, "search_query_done", {"query": query, "found": len(papers)})
        )
        if len(aggregated) >= TOTAL_CAP:
            break

    progress.append(
        await publish_event(report_id, "search_done", {"unique_papers": len(aggregated)})
    )
    return {"search_results": aggregated, "progress": progress}

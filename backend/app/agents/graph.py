"""Build and run the research LangGraph.

Standalone usage:
    python -m app.agents.graph "your research question"
"""
from __future__ import annotations

import asyncio
import logging
import sys

from langgraph.graph import END, START, StateGraph

from app.agents.planner import planner_node
from app.agents.search import search_node
from app.agents.state import ResearchState
from app.agents.summarizer import summarizer_node
from app.agents.writer import writer_node
from app.core.logging import configure_logging

log = logging.getLogger(__name__)


def build_research_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("planner", planner_node)
    graph.add_node("search", search_node)
    graph.add_node("summarizer", summarizer_node)
    graph.add_node("writer", writer_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "summarizer")
    graph.add_edge("summarizer", "writer")
    graph.add_edge("writer", END)

    return graph.compile()


async def run_research(prompt: str, report_id: str | None = None) -> ResearchState:
    app = build_research_graph()
    initial: ResearchState = {"prompt": prompt, "report_id": report_id, "progress": []}
    result = await app.ainvoke(initial)
    return result


async def _cli(prompt: str) -> None:
    configure_logging("INFO")
    print(f"\n>>> Running research for: {prompt!r}\n")
    result = await run_research(prompt)
    print("\n=== REPORT ===\n")
    print(result.get("report", "(no report)"))
    print(f"\n=== {len(result.get('progress', []))} progress events ===")


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Recent advances in retrieval augmented generation"
    asyncio.run(_cli(prompt))

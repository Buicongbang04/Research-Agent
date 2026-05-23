"""Shared state for the research multi-agent graph."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ResearchState(TypedDict, total=False):
    # Inputs
    prompt: str
    report_id: str | None  # for progress publishing

    # Planner output
    subtasks: list[str]

    # Search output: list of {arxiv_id, title, abstract, authors, published, pdf_url}
    search_results: list[dict[str, Any]]

    # Summarizer output: list of {arxiv_id, title, key_points, methods, findings}
    summaries: list[dict[str, Any]]

    # Writer output
    report: str

    # Progress events (accumulated across nodes via reducer)
    progress: Annotated[list[dict[str, Any]], operator.add]

    # Error flag
    error: str | None

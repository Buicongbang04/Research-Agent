"""arXiv search tool — wraps the `arxiv` Python lib."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import arxiv

log = logging.getLogger(__name__)


@dataclass
class Paper:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published: str
    pdf_url: str

    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "published": self.published,
            "pdf_url": self.pdf_url,
        }


def _search_sync(query: str, max_results: int = 5) -> list[Paper]:
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    papers: list[Paper] = []
    # arXiv recommends >=3s between requests; bump retries to survive transient 429s
    client = arxiv.Client(page_size=max_results, delay_seconds=3.0, num_retries=5)
    for result in client.results(search):
        papers.append(
            Paper(
                arxiv_id=result.entry_id.rsplit("/", 1)[-1],
                title=result.title.strip().replace("\n", " "),
                abstract=result.summary.strip().replace("\n", " "),
                authors=[a.name for a in result.authors],
                published=result.published.isoformat() if result.published else "",
                pdf_url=result.pdf_url,
            )
        )
    return papers


async def arxiv_search(query: str, max_results: int = 5) -> list[Paper]:
    """Search arXiv for papers matching the query. Runs blocking call in a thread."""
    log.info("arXiv search: %r (max_results=%d)", query, max_results)
    return await asyncio.to_thread(_search_sync, query, max_results)

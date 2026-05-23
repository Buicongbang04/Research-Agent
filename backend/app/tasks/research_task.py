"""Celery task: run the LangGraph research pipeline and persist the report.

Celery workers run a sync entrypoint that drives the async pipeline via asyncio.run().
Each task uses a sync DB session (psycopg2) so we don't fight the worker's event loop
for connection management.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.agents.graph import run_research
from app.config import settings
from app.db.models import Report, ReportStatus
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)

# Sync engine for the Celery worker. We rebuild on first use to avoid forking issues.
_sync_engine = None
_SyncSession = None


def _session():
    global _sync_engine, _SyncSession
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True, future=True)
        _SyncSession = sessionmaker(bind=_sync_engine, expire_on_commit=False, future=True)
    return _SyncSession()


@celery_app.task(name="research.run", bind=True)
def run_research_task(self, report_id: str) -> dict:
    log.info("Starting research task for report %s", report_id)

    with _session() as session:
        report = session.scalar(select(Report).where(Report.id == uuid.UUID(report_id)))
        if report is None:
            log.error("Report %s not found", report_id)
            return {"status": "error", "reason": "not_found"}

        prompt = report.prompt
        session.execute(
            update(Report).where(Report.id == report.id).values(status=ReportStatus.running)
        )
        session.commit()

    try:
        result = asyncio.run(run_research(prompt, report_id=report_id))
        report_md = result.get("report") or "(no report generated)"
        metadata = {
            "subtasks": result.get("subtasks", []),
            "paper_count": len(result.get("search_results", [])),
            "summary_count": len(result.get("summaries", [])),
            "papers": [
                {"arxiv_id": p["arxiv_id"], "title": p["title"], "pdf_url": p["pdf_url"]}
                for p in result.get("search_results", [])
            ],
        }
        with _session() as session:
            session.execute(
                update(Report)
                .where(Report.id == uuid.UUID(report_id))
                .values(
                    status=ReportStatus.completed,
                    result_md=report_md,
                    extra=metadata,
                )
            )
            session.commit()
        log.info("Research task %s completed (report len=%d)", report_id, len(report_md))
        return {"status": "completed", "report_id": report_id}

    except Exception as e:
        log.exception("Research task %s failed", report_id)
        with _session() as session:
            session.execute(
                update(Report)
                .where(Report.id == uuid.UUID(report_id))
                .values(status=ReportStatus.failed, error=str(e))
            )
            session.commit()
        return {"status": "failed", "report_id": report_id, "error": str(e)}

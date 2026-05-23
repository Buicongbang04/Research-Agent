"""Research endpoints: create job, poll, list, SSE stream of progress."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import AsyncIterator

import redis.asyncio as redis_async
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.core.deps import CurrentUser, DbSession
from app.db.models import Report, ReportStatus
from app.schemas.research import ReportOut, ReportSummary, ResearchCreate
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_research(payload: ResearchCreate, db: DbSession, user: CurrentUser) -> Report:
    report = Report(user_id=user.id, prompt=payload.prompt, status=ReportStatus.pending)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    # Enqueue Celery task
    celery_app.send_task("research.run", args=[str(report.id)])

    return report


@router.get("", response_model=list[ReportSummary])
async def list_research(db: DbSession, user: CurrentUser) -> list[Report]:
    result = await db.execute(
        select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())


@router.get("/{report_id}", response_model=ReportOut)
async def get_research(report_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Report:
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user.id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/stream")
async def stream_research(report_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Server-Sent Events stream of progress events for a running research job."""
    # Verify ownership
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user.id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    channel = f"research:{report_id}"

    async def event_gen() -> AsyncIterator[dict]:
        client = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)

        # Send initial snapshot so a late subscriber knows current status
        yield {
            "event": "snapshot",
            "data": json.dumps(
                {"status": report.status.value, "created_at": report.created_at.isoformat()}
            ),
        }

        try:
            timeout_iters = 0
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg is None:
                    timeout_iters += 1
                    # Heartbeat every 10s to keep the connection alive
                    if timeout_iters >= 10:
                        yield {"event": "ping", "data": "{}"}
                        timeout_iters = 0
                    # Stop streaming once report has reached a terminal state.
                    # Re-check DB every ~5 idle seconds.
                    if timeout_iters % 5 == 0:
                        result = await db.execute(
                            select(Report.status).where(Report.id == report_id)
                        )
                        current_status = result.scalar_one_or_none()
                        if current_status in (ReportStatus.completed, ReportStatus.failed):
                            yield {
                                "event": "done",
                                "data": json.dumps({"status": current_status.value}),
                            }
                            break
                    continue

                timeout_iters = 0
                data = msg.get("data", "")
                try:
                    parsed = json.loads(data)
                    event_name = parsed.pop("event", "progress")
                except json.JSONDecodeError:
                    event_name = "progress"
                    parsed = {"raw": data}

                yield {"event": event_name, "data": json.dumps(parsed)}

                if event_name == "writer_done":
                    yield {"event": "done", "data": json.dumps({"status": "completed"})}
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await client.aclose()

    return EventSourceResponse(event_gen())

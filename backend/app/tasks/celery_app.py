"""Celery app — broker is Redis, tasks are imported lazily."""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "research_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.research_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # Long-running tasks: one at a time per worker
)

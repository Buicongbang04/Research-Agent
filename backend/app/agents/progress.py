"""Publish progress events to Redis pub/sub (consumed by SSE endpoint).

If `report_id` is missing or Redis is unreachable, events are silently dropped —
the in-state `progress` log still captures them for inspection.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis.asyncio as redis_async

from app.config import settings

log = logging.getLogger(__name__)


_pool: redis_async.Redis | None = None


def _get_redis() -> redis_async.Redis | None:
    global _pool
    if _pool is None:
        try:
            _pool = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as e:
            log.warning("Redis unavailable, progress will not be streamed: %s", e)
            return None
    return _pool


async def publish_event(report_id: str | None, event: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build an event record, publish to Redis if possible, return the record."""
    record = {"event": event, "ts": time.time(), **data}
    if report_id:
        client = _get_redis()
        if client is not None:
            try:
                await client.publish(f"research:{report_id}", json.dumps(record))
            except Exception as e:
                log.debug("Redis publish failed for %s: %s", report_id, e)
    log.info("[progress %s] %s %s", report_id or "-", event, data)
    return record

"""Shared Redis client + pub/sub helpers for job progress."""

from __future__ import annotations

import json
from typing import Any

import redis
import redis.asyncio as aioredis

from app.core.config import settings

_sync_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Synchronous client (used by Celery worker)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _sync_client


def get_async_redis() -> aioredis.Redis:
    """Async client (used by FastAPI WebSocket relay)."""
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def job_channel(job_id: str) -> str:
    return f"job:{job_id}"


def publish_progress(job_id: str, payload: dict[str, Any]) -> None:
    """Publish a progress event (called from the worker)."""
    client = get_redis()
    channel = job_channel(job_id)
    message = json.dumps(payload)
    client.publish(channel, message)
    # Also cache the latest state so a late WS subscriber gets the current value.
    client.set(f"{channel}:last", message, ex=3600)

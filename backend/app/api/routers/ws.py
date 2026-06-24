"""WebSocket job-progress relay.

Subscribes to the Redis channel for a job and forwards progress events to the client.
Because progress lives in Redis pub/sub, any API replica can serve any job's stream
(horizontally scalable, collaboration-ready).
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.redis_client import get_async_redis, job_channel

logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def job_progress(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    redis = get_async_redis()
    channel = job_channel(job_id)

    # Send the last cached state immediately (in case the job already advanced).
    last = await redis.get(f"{channel}:last")
    if last:
        await websocket.send_text(last)
        try:
            if json.loads(last).get("status") in {"completed", "failed"}:
                await websocket.close()
                await redis.aclose()
                return
        except json.JSONDecodeError:
            pass

    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
            if message is None:
                # keepalive ping
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue
            data = message["data"]
            await websocket.send_text(data)
            try:
                if json.loads(data).get("status") in {"completed", "failed"}:
                    break
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("WS relay error for job %s: %s", job_id, exc)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis.aclose()
        with_closed = asyncio.shield(_safe_close(websocket))
        await with_closed


async def _safe_close(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except Exception:  # noqa: BLE001
        pass

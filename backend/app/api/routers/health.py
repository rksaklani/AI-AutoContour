"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.redis_client import get_redis
from app.db.session import engine
from app.services import storage

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> dict:
    checks = {"database": False, "redis": False, "storage": False}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        get_redis().ping()
        checks["redis"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        storage.ensure_bucket()
        checks["storage"] = True
    except Exception:  # noqa: BLE001
        pass
    checks["status"] = "ok" if all(v for k, v in checks.items() if k != "status") else "degraded"
    return checks

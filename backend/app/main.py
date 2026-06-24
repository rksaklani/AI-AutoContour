"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import ai, auth, health, jobs, reports, results, studies, ws
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    logger.info("%s API starting (env=%s)", settings.LUMIRA_APP_NAME, settings.ENVIRONMENT)
    try:
        from app.services import storage

        storage.ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not ensure bucket on startup: %s", exc)
    yield
    logger.info("%s API shutting down", settings.LUMIRA_APP_NAME)


app = FastAPI(
    title=f"{settings.LUMIRA_APP_NAME} API",
    version="0.1.0",
    description="AI-powered medical imaging platform API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health (unversioned, for probes).
app.include_router(health.router)

# Versioned API.
prefix = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=prefix)
app.include_router(studies.router, prefix=prefix)
app.include_router(jobs.router, prefix=prefix)
app.include_router(results.router, prefix=prefix)
app.include_router(reports.router, prefix=prefix)
app.include_router(ai.router, prefix=prefix)
app.include_router(ws.router, prefix=prefix)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.LUMIRA_APP_NAME,
        "docs": "/docs",
        "version": "0.1.0",
    }

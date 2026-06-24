"""AI assistant schemas (VILA-M3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AiStatusOut(BaseModel):
    engine: str
    sidecar_reachable: bool
    sidecar_mode: str | None = None
    gpu_available: bool | None = None
    vila_loaded: bool | None = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


class AskResponse(BaseModel):
    answer: str
    engine: str
    mode: str | None = None

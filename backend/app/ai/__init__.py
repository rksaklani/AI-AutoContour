"""AI engine package.

The pipeline depends on the :class:`AIEngine` protocol, never on a concrete model.
``get_engine()`` returns the active implementation controlled by ``AI_ENGINE``:

- ``stub`` — deterministic local engine (tests, no sidecar)
- ``vila_m3`` — MONAI VILA-M3 sidecar (lite mode without GPU; full VLM with GPU image)
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.ai.engine import AIEngine
from app.ai.stub import StubAIEngine
from app.core.config import settings

if TYPE_CHECKING:
    from app.ai.vila_m3_engine import VilaM3Engine


@lru_cache
def get_engine() -> AIEngine:
    engine_id = (settings.AI_ENGINE or "stub").lower().strip()
    if engine_id == "vila_m3":
        from app.ai.vila_m3_engine import VilaM3Engine

        return VilaM3Engine()
    return StubAIEngine()


def get_vila_engine() -> VilaM3Engine | None:
    """Return VILA-M3 engine when active (for ask / narrative endpoints)."""
    from app.ai.vila_m3_engine import VilaM3Engine

    engine = get_engine()
    return engine if isinstance(engine, VilaM3Engine) else None


__all__ = ["AIEngine", "get_engine", "get_vila_engine"]

"""VILA-M3 engine — delegates inference to the GPU sidecar HTTP service."""

from __future__ import annotations

import httpx

from app.ai.engine import Detection, SegmentationResult, StudyContext
from app.ai.stub import StubAIEngine
from app.ai.vila_m3_client import VilaM3Client, VilaM3ClientError, parse_analyze_response
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_HTTP_ERRORS = (VilaM3ClientError, httpx.HTTPError, httpx.TimeoutException)


class VilaM3Engine:
    name = "vila-m3"

    def __init__(self) -> None:
        self._client = VilaM3Client()
        self._last_mode: str | None = None
        self._cached: tuple[list[Detection], list[SegmentationResult]] | None = None
        self._fallback = StubAIEngine()

    def _run_analyze(self, ctx: StudyContext) -> tuple[list[Detection], list[SegmentationResult]]:
        if self._cached is not None:
            return self._cached
        try:
            data = self._client.analyze(ctx)
            self._last_mode = data.get("mode", "unknown")
            self._cached = parse_analyze_response(data)
            return self._cached
        except _HTTP_ERRORS as exc:
            if settings.VILA_M3_FALLBACK_STUB:
                logger.warning("VILA-M3 sidecar unavailable, using stub fallback: %s", exc)
                detections = self._fallback.detect(ctx)
                segmentations = self._fallback.segment(ctx, detections)
                self._cached = (detections, segmentations)
                self._last_mode = "stub-fallback"
                return self._cached
            raise

    def detect(self, ctx: StudyContext) -> list[Detection]:
        return self._run_analyze(ctx)[0]

    def segment(
        self, ctx: StudyContext, detections: list[Detection]
    ) -> list[SegmentationResult]:
        del detections  # sidecar returns segmentations aligned with detect pass
        return self._run_analyze(ctx)[1]

    def ask(
        self,
        study_id: str,
        question: str,
        *,
        modality: str | None = None,
        body_part: str | None = None,
        description: str | None = None,
        findings_summary: list[dict] | None = None,
        series_instances: list[dict] | None = None,
    ) -> str:
        try:
            data = self._client.ask(
                study_id,
                question,
                modality=modality,
                body_part=body_part,
                description=description,
                findings_summary=findings_summary,
                series_instances=series_instances,
            )
            self._last_mode = data.get("mode")
            return data.get("answer", "")
        except _HTTP_ERRORS as exc:
            if settings.VILA_M3_FALLBACK_STUB:
                logger.warning("VILA-M3 ask fallback: %s", exc)
                return (
                    f"[Stub fallback] Unable to reach VILA-M3 sidecar. "
                    f"Question received: {question[:200]}"
                )
            raise

    def report_narrative(
        self,
        study_id: str,
        *,
        patient_name: str | None = None,
        modality: str | None = None,
        body_part: str | None = None,
        description: str | None = None,
        findings: list[dict] | None = None,
        series_instances: list[dict] | None = None,
    ) -> dict[str, str]:
        try:
            data = self._client.report_narrative(
                study_id,
                patient_name=patient_name,
                modality=modality,
                body_part=body_part,
                description=description,
                findings=findings,
                series_instances=series_instances,
            )
            return {
                "narrative": data.get("narrative", ""),
                "impression": data.get("impression", ""),
                "mode": data.get("mode", ""),
            }
        except _HTTP_ERRORS as exc:
            if settings.VILA_M3_FALLBACK_STUB:
                logger.warning("VILA-M3 report narrative fallback: %s", exc)
                return {"narrative": "", "impression": "", "mode": "stub-fallback"}
            raise

"""HTTP client for the VILA-M3 sidecar service."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.ai.engine import Detection, SegmentationResult, StudyContext
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class VilaM3ClientError(Exception):
    """Sidecar request failed."""


class VilaM3Client:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.VILA_M3_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.VILA_M3_TIMEOUT_SEC

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{self.base_url}/health")
            r.raise_for_status()
            return r.json()

    def analyze(self, ctx: StudyContext) -> dict[str, Any]:
        payload = {
            "study_id": ctx.get("study_id", ""),
            "modality": ctx.get("modality"),
            "body_part": ctx.get("body_part"),
            "description": ctx.get("description"),
            "instance_count": ctx.get("instance_count", 0),
            "series_instances": ctx.get("series_instances") or [],
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/v1/analyze", json=payload)
            if r.status_code >= 400:
                raise VilaM3ClientError(f"analyze failed ({r.status_code}): {r.text}")
            return r.json()

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
    ) -> dict[str, Any]:
        payload = {
            "study_id": study_id,
            "question": question,
            "modality": modality,
            "body_part": body_part,
            "description": description,
            "findings_summary": findings_summary or [],
            "series_instances": series_instances or [],
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/v1/ask", json=payload)
            if r.status_code >= 400:
                raise VilaM3ClientError(f"ask failed ({r.status_code}): {r.text}")
            return r.json()

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
    ) -> dict[str, Any]:
        payload = {
            "study_id": study_id,
            "patient_name": patient_name,
            "modality": modality,
            "body_part": body_part,
            "description": description,
            "findings": findings or [],
            "series_instances": series_instances or [],
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/v1/report/narrative", json=payload)
            if r.status_code >= 400:
                raise VilaM3ClientError(f"report narrative failed ({r.status_code}): {r.text}")
            return r.json()


def parse_analyze_response(
    data: dict[str, Any],
) -> tuple[list[Detection], list[SegmentationResult]]:
    detections: list[Detection] = []
    for d in data.get("detections", []):
        det: Detection = Detection(
            label=d["label"],
            location=d["location"],
            confidence=float(d["confidence"]),
            severity=d["severity"],
            bbox=d.get("bbox") or {},
            description=d.get("description", ""),
            recommendation=d.get("recommendation", ""),
        )
        if d.get("size_cm") is not None:
            det["size_cm"] = float(d["size_cm"])
        if d.get("size_mm") is not None:
            det["size_mm"] = float(d["size_mm"])
        if d.get("volume_cc") is not None:
            det["volume_cc"] = float(d["volume_cc"])
        detections.append(det)

    segmentations: list[SegmentationResult] = []
    for s in data.get("segmentations", []):
        mask_b64 = s.get("mask_png_b64")
        mask_png = base64.b64decode(mask_b64) if mask_b64 else None
        segmentations.append(
            SegmentationResult(
                label=s["label"],
                structure_type=s["structure_type"],
                color=s["color"],
                stats={
                    **(s.get("stats") or {}),
                    "contours": s.get("contours") or [],
                },
                mask_png=mask_png,
            )
        )
    return detections, segmentations

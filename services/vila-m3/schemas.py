"""Request/response models for the VILA-M3 sidecar HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SeriesInstance(BaseModel):
    series_id: str
    instance_id: str
    modality: str
    object_key: str
    url: str
    instance_number: int | None = None


class StudyAnalyzeRequest(BaseModel):
    study_id: str
    modality: str | None = None
    body_part: str | None = None
    description: str | None = None
    instance_count: int = 0
    series_instances: list[SeriesInstance] = Field(default_factory=list)


class DetectionOut(BaseModel):
    label: str
    location: str
    confidence: float
    severity: str
    bbox: dict[str, Any]
    description: str
    recommendation: str
    size_cm: float | None = None
    size_mm: float | None = None
    volume_cc: float | None = None


class SegmentationOut(BaseModel):
    label: str
    structure_type: str
    color: str
    stats: dict[str, Any]
    mask_png_b64: str | None = None
    contours: list[dict[str, Any]] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    engine: str
    mode: str  # lite | vila
    detections: list[DetectionOut]
    segmentations: list[SegmentationOut]


class AskRequest(BaseModel):
    study_id: str
    question: str
    modality: str | None = None
    body_part: str | None = None
    description: str | None = None
    findings_summary: list[dict[str, Any]] = Field(default_factory=list)
    series_instances: list[SeriesInstance] = Field(default_factory=list)


class AskResponse(BaseModel):
    answer: str
    engine: str
    mode: str


class ReportNarrativeRequest(BaseModel):
    study_id: str
    patient_name: str | None = None
    modality: str | None = None
    body_part: str | None = None
    description: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    series_instances: list[SeriesInstance] = Field(default_factory=list)


class ReportNarrativeResponse(BaseModel):
    narrative: str
    impression: str
    engine: str
    mode: str


class HealthResponse(BaseModel):
    status: str
    engine: str
    mode: str
    gpu_available: bool
    vila_loaded: bool
    load_error: str | None = None
    model_path: str | None = None

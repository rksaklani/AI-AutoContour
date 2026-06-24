"""Job, finding, segmentation, annotation and report schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    status: str
    stage: str
    progress: int
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    segmentation_id: uuid.UUID | None = None
    label: str
    location: str
    confidence: float
    volume_cc: float | None = None
    severity: str
    bbox: dict[str, Any]
    description: str
    recommendation: str


class SegmentationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    label: str
    structure_type: str
    mask_object_key: str | None = None
    color: str
    stats: dict[str, Any]
    mask_url: str | None = None


class ContourPolygonOut(BaseModel):
    z_mm: float
    points: list[list[float]]


class RoiOverlayOut(BaseModel):
    segmentation_id: uuid.UUID | None = None
    label: str
    color: str
    structure_type: str
    contours: list[ContourPolygonOut] = []
    bbox: dict[str, Any] = {}
    mask_url: str | None = None


class StudyOverlayOut(BaseModel):
    slice_z_mm: list[float]
    rois: list[RoiOverlayOut]


class AnnotationCreate(BaseModel):
    kind: str = "text"
    geometry: dict[str, Any] = {}
    text: str = ""
    finding_id: uuid.UUID | None = None


class AnnotationUpdate(BaseModel):
    kind: str | None = None
    geometry: dict[str, Any] | None = None
    text: str | None = None


class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    finding_id: uuid.UUID | None = None
    kind: str
    geometry: dict[str, Any]
    text: str
    ai_generated: bool


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID
    status: str
    summary: dict[str, Any]
    created_at: datetime
    formats: list[str] = []

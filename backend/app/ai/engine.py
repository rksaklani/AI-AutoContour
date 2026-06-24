"""The AIEngine contract.

This Protocol is the stable boundary between the pipeline and any model implementation.
Real engines (TotalSegmentator, nnU-Net, MONAI) implement the same interface so they can
be swapped in with zero changes to tasks, API or DB.
"""

from __future__ import annotations

from typing import Any, NotRequired, Protocol, TypedDict, runtime_checkable


class StudyContext(TypedDict, total=False):
    """Lightweight study description passed to the engine."""

    study_id: str
    modality: str
    body_part: str
    description: str
    instance_count: int
    # Presigned URLs + object keys for image series (VILA-M3 / volume engines).
    series_instances: list[dict]


class Detection(TypedDict):
    label: str
    location: str
    confidence: float  # 0..1
    severity: str  # low | moderate | high
    bbox: dict[str, Any]  # {x, y, z, w, h, d} in normalized coords
    description: str
    recommendation: str
    size_cm: NotRequired[float | None]
    size_mm: NotRequired[float | None]
    volume_cc: NotRequired[float | None]


class SegmentationResult(TypedDict):
    label: str
    structure_type: str  # organ | tumor | lesion | bone | vessel
    color: str
    stats: dict[str, Any]  # volume_cc, voxel_count, ...
    # In a real engine this would also carry mask bytes (NIfTI/PNG); the stub
    # generates a synthetic mask separately.
    mask_png: bytes | None


@runtime_checkable
class AIEngine(Protocol):
    name: str

    def detect(self, ctx: StudyContext) -> list[Detection]:
        """Detect abnormalities. Returns zero or more detections."""
        ...

    def segment(
        self, ctx: StudyContext, detections: list[Detection]
    ) -> list[SegmentationResult]:
        """Produce segmentation masks for organs/findings."""
        ...

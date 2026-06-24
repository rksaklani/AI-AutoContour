"""Deterministic stub AI engine.

Produces realistic-looking findings and synthetic segmentation masks based on the study's
modality / body part, so the entire product works end-to-end without a GPU. Output is
deterministic per study id (hash-seeded) for reproducible demos and tests.
"""

from __future__ import annotations

import hashlib
import io
import struct
import zlib

from app.ai.engine import Detection, SegmentationResult, StudyContext

# Catalogue of plausible findings keyed by modality / body part keyword.
_CATALOG: dict[str, list[dict]] = {
    "ct_chest": [
        {
            "label": "Lung Nodule",
            "location": "Right Upper Lobe",
            "confidence": 0.92,
            "severity": "moderate",
            "volume_cc": 1.8,
            "structure_type": "lesion",
            "color": "#f59e0b",
            "description": "Well-circumscribed solid nodule in the right upper lobe.",
            "recommendation": "Short-interval CT follow-up; correlate clinically.",
        },
    ],
    "ct_abdomen": [
        {
            "label": "Liver Lesion",
            "location": "Hepatic Segment VII",
            "confidence": 0.88,
            "severity": "moderate",
            "volume_cc": 6.4,
            "structure_type": "lesion",
            "color": "#10b981",
            "description": "Hypodense focal lesion in the right hepatic lobe.",
            "recommendation": "Multiphase MRI for characterization recommended.",
        },
        {
            "label": "Kidney Tumor",
            "location": "Left Renal Upper Pole",
            "confidence": 0.81,
            "severity": "high",
            "volume_cc": 11.0,
            "structure_type": "tumor",
            "color": "#ef4444",
            "description": "Enhancing solid mass at the left renal upper pole.",
            "recommendation": "Urology referral; consider biopsy.",
        },
    ],
    "mr_brain": [
        {
            "label": "Brain Tumor",
            "location": "Left Frontal Lobe",
            "confidence": 0.96,
            "severity": "high",
            "volume_cc": 14.2,
            "structure_type": "tumor",
            "color": "#a855f7",
            "description": "Abnormal enhancing lesion with surrounding vasogenic edema "
            "in the left frontal lobe.",
            "recommendation": "Neurosurgical review recommended.",
        },
    ],
    "xr_chest": [
        {
            "label": "Pneumonia",
            "location": "Right Lower Zone",
            "confidence": 0.84,
            "severity": "moderate",
            "volume_cc": None,
            "structure_type": "lesion",
            "color": "#f97316",
            "description": "Air-space opacification in the right lower zone.",
            "recommendation": "Correlate with clinical findings; follow-up radiograph.",
        },
    ],
    "default": [
        {
            "label": "Suspicious Region",
            "location": "Region of Interest",
            "confidence": 0.76,
            "severity": "moderate",
            "volume_cc": 3.1,
            "structure_type": "lesion",
            "color": "#38bdf8",
            "description": "Abnormal region detected requiring further review.",
            "recommendation": "Radiologist review recommended.",
        },
    ],
}

# Organ segmentations always emitted alongside findings (whole-study context).
_ORGANS = {
    "ct_chest": [("Lungs", "organ", "#60a5fa", 4200.0), ("Heart", "organ", "#f472b6", 700.0)],
    "ct_abdomen": [("Liver", "organ", "#34d399", 1500.0), ("Kidneys", "organ", "#fbbf24", 300.0)],
    "mr_brain": [("Brain", "organ", "#818cf8", 1350.0)],
    "xr_chest": [],
    "default": [("Target Structure", "organ", "#94a3b8", 500.0)],
}

# Approximate normalized axial bounding boxes for organ masks (demo overlays).
_ORGAN_BBOX: dict[str, dict] = {
    "Lungs": {"x": 0.12, "y": 0.18, "w": 0.76, "h": 0.58, "slice": 0.5},
    "Heart": {"x": 0.42, "y": 0.38, "w": 0.28, "h": 0.32, "slice": 0.5},
    "Liver": {"x": 0.35, "y": 0.25, "w": 0.45, "h": 0.5, "slice": 0.5},
    "Kidneys": {"x": 0.2, "y": 0.35, "w": 0.6, "h": 0.4, "slice": 0.5},
    "Brain": {"x": 0.2, "y": 0.15, "w": 0.6, "h": 0.7, "slice": 0.5},
    "Target Structure": {"x": 0.35, "y": 0.35, "w": 0.3, "h": 0.3, "slice": 0.5},
}


def _category(ctx: StudyContext) -> str:
    modality = (ctx.get("modality") or "").upper()
    text = " ".join(
        [ctx.get("body_part", ""), ctx.get("description", "")]
    ).lower()
    if modality in {"CT"} and ("chest" in text or "lung" in text or "thorax" in text):
        return "ct_chest"
    if modality in {"CT"} and ("abdomen" in text or "liver" in text or "kidney" in text):
        return "ct_abdomen"
    if modality in {"MR", "MRI"} and ("brain" in text or "head" in text):
        return "mr_brain"
    if modality in {"CR", "DX", "XR"} or ("chest" in text and modality in {"CR", "DX"}):
        return "xr_chest"
    # Reasonable defaults by modality alone.
    if modality == "CT":
        return "ct_chest"
    if modality in {"MR", "MRI"}:
        return "mr_brain"
    if modality in {"CR", "DX", "XR"}:
        return "xr_chest"
    return "default"


def _seed(study_id: str) -> int:
    return int(hashlib.sha256(study_id.encode()).hexdigest(), 16)


def _make_png(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    """Generate a minimal solid-color RGBA PNG (no external deps)."""
    r, g, b, a = rgba

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    row = bytes([r, g, b, a]) * width
    for _ in range(height):
        raw.append(0)  # filter type 0
        raw.extend(row)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = io.BytesIO()
    png.write(b"\x89PNG\r\n\x1a\n")
    png.write(chunk(b"IHDR", ihdr))
    png.write(chunk(b"IDAT", zlib.compress(bytes(raw))))
    png.write(chunk(b"IEND", b""))
    return png.getvalue()


def _hex_to_rgba(hex_color: str, alpha: int = 128) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


class StubAIEngine:
    name = "stub-v1"

    def detect(self, ctx: StudyContext) -> list[Detection]:
        cat = _category(ctx)
        seed = _seed(ctx.get("study_id", "x"))
        items = _CATALOG.get(cat, _CATALOG["default"])
        detections: list[Detection] = []
        for i, item in enumerate(items):
            # Deterministic pseudo-random bbox derived from the seed.
            jitter = ((seed >> (i * 5)) % 30) / 100.0
            x = round(0.30 + jitter, 3)
            y = round(0.35 + jitter / 2, 3)
            detections.append(
                Detection(
                    label=item["label"],
                    location=item["location"],
                    confidence=item["confidence"],
                    severity=item["severity"],
                    bbox={"x": x, "y": y, "w": 0.18, "h": 0.16, "slice": 0.5},
                    description=item["description"],
                    recommendation=item["recommendation"],
                )
            )
        return detections

    def segment(
        self, ctx: StudyContext, detections: list[Detection]
    ) -> list[SegmentationResult]:
        cat = _category(ctx)
        results: list[SegmentationResult] = []

        # Organ segmentations.
        for label, stype, color, volume in _ORGANS.get(cat, _ORGANS["default"]):
            bbox = _ORGAN_BBOX.get(label, _ORGAN_BBOX["Target Structure"])
            results.append(
                SegmentationResult(
                    label=label,
                    structure_type=stype,
                    color=color,
                    stats={"volume_cc": volume, "voxel_count": int(volume * 1000), "bbox": bbox},
                    mask_png=_make_png(64, 64, _hex_to_rgba(color, 90)),
                )
            )

        # A mask per finding.
        catalog = {c["label"]: c for c in _CATALOG.get(cat, _CATALOG["default"])}
        for det in detections:
            meta = catalog.get(det["label"], {})
            color = meta.get("color", "#38bdf8")
            volume = meta.get("volume_cc")
            results.append(
                SegmentationResult(
                    label=det["label"],
                    structure_type=meta.get("structure_type", "lesion"),
                    color=color,
                    stats=(
                        {"volume_cc": volume, "bbox": det["bbox"]}
                        if volume
                        else {"bbox": det["bbox"]}
                    ),
                    mask_png=_make_png(64, 64, _hex_to_rgba(color, 140)),
                )
            )
        return results

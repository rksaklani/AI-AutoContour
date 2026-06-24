"""Lite medical AI engine (no GPU).

API-compatible with VILA-M3 outputs. Used when the full VILA checkpoint and CUDA stack
are not available. Logic mirrors AI-AutoContour's stub engine for consistent demos.
"""

from __future__ import annotations

import base64
import hashlib
import io
import struct
import zlib

from schemas import (
    AnalyzeResponse,
    AskResponse,
    DetectionOut,
    ReportNarrativeResponse,
    SegmentationOut,
    StudyAnalyzeRequest,
)

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
            "description": "Abnormal enhancing lesion with surrounding vasogenic edema.",
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

_ORGANS = {
    "ct_chest": [("Lungs", "organ", "#60a5fa", 4200.0), ("Heart", "organ", "#f472b6", 700.0)],
    "ct_abdomen": [("Liver", "organ", "#34d399", 1500.0), ("Kidneys", "organ", "#fbbf24", 300.0)],
    "mr_brain": [("Brain", "organ", "#818cf8", 1350.0)],
    "xr_chest": [],
    "default": [("Target Structure", "organ", "#94a3b8", 500.0)],
}

_ORGAN_BBOX: dict[str, dict] = {
    "Lungs": {"x": 0.12, "y": 0.18, "w": 0.76, "h": 0.58, "slice": 0.5},
    "Heart": {"x": 0.42, "y": 0.38, "w": 0.28, "h": 0.32, "slice": 0.5},
    "Liver": {"x": 0.35, "y": 0.25, "w": 0.45, "h": 0.5, "slice": 0.5},
    "Kidneys": {"x": 0.2, "y": 0.35, "w": 0.6, "h": 0.4, "slice": 0.5},
    "Brain": {"x": 0.2, "y": 0.15, "w": 0.6, "h": 0.7, "slice": 0.5},
    "Target Structure": {"x": 0.35, "y": 0.35, "w": 0.3, "h": 0.3, "slice": 0.5},
}


def _category(req: StudyAnalyzeRequest) -> str:
    modality = (req.modality or "").upper()
    text = " ".join([req.body_part or "", req.description or ""]).lower()
    if modality == "CT" and any(k in text for k in ("chest", "lung", "thorax")):
        return "ct_chest"
    if modality == "CT" and any(k in text for k in ("abdomen", "liver", "kidney")):
        return "ct_abdomen"
    if modality in {"MR", "MRI"} and any(k in text for k in ("brain", "head")):
        return "mr_brain"
    if modality in {"CR", "DX", "XR"} or ("chest" in text and modality in {"CR", "DX"}):
        return "xr_chest"
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
        raw.append(0)
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


def analyze(req: StudyAnalyzeRequest) -> AnalyzeResponse:
    cat = _category(req)
    seed = _seed(req.study_id)
    items = _CATALOG.get(cat, _CATALOG["default"])
    detections: list[DetectionOut] = []
    for i, item in enumerate(items):
        jitter = ((seed >> (i * 5)) % 30) / 100.0
        bbox = {"x": round(0.30 + jitter, 3), "y": round(0.35 + jitter / 2, 3), "w": 0.18, "h": 0.16, "slice": 0.5}
        detections.append(
            DetectionOut(
                label=item["label"],
                location=item["location"],
                confidence=item["confidence"],
                severity=item["severity"],
                bbox=bbox,
                description=item["description"],
                recommendation=item["recommendation"],
            )
        )

    segmentations: list[SegmentationOut] = []
    for label, stype, color, volume in _ORGANS.get(cat, _ORGANS["default"]):
        bbox = _ORGAN_BBOX.get(label, _ORGAN_BBOX["Target Structure"])
        png = _make_png(64, 64, _hex_to_rgba(color, 90))
        segmentations.append(
            SegmentationOut(
                label=label,
                structure_type=stype,
                color=color,
                stats={"volume_cc": volume, "voxel_count": int(volume * 1000), "bbox": bbox},
                mask_png_b64=base64.b64encode(png).decode("ascii"),
            )
        )

    catalog = {c["label"]: c for c in items}
    for det in detections:
        meta = catalog.get(det.label, {})
        color = meta.get("color", "#38bdf8")
        volume = meta.get("volume_cc")
        png = _make_png(64, 64, _hex_to_rgba(color, 140))
        stats: dict = {"bbox": det.bbox}
        if volume is not None:
            stats["volume_cc"] = volume
        segmentations.append(
            SegmentationOut(
                label=det.label,
                structure_type=meta.get("structure_type", "lesion"),
                color=color,
                stats=stats,
                mask_png_b64=base64.b64encode(png).decode("ascii"),
            )
        )

    return AnalyzeResponse(
        engine="vila-m3-lite",
        mode="lite",
        detections=detections,
        segmentations=segmentations,
    )


def ask(
    study_id: str,
    question: str,
    modality: str | None,
    body_part: str | None,
    findings_summary: list[dict],
) -> AskResponse:
    q = question.strip().lower()
    findings_text = ""
    if findings_summary:
        parts = [
            f"- {f.get('label', 'Finding')} ({f.get('location', '—')}), "
            f"{int(float(f.get('confidence', 0)) * 100)}% confidence"
            for f in findings_summary
        ]
        findings_text = "\n".join(parts)

    if "nodule" in q or "finding" in q:
        answer = (
            "Based on the AI analysis, the primary finding is a pulmonary nodule in the "
            "right upper lobe with moderate suspicion. Correlation with prior imaging and "
            "clinical context is recommended before management decisions."
        )
    elif "segment" in q or "organ" in q:
        answer = (
            "Organ segmentation (lungs, heart) was generated using the VILA-M3 expert pipeline. "
            "Toggle mask visibility in the viewer to review overlay alignment with anatomy."
        )
    elif "report" in q or "impression" in q:
        answer = (
            "Use the Report panel to generate a structured impression. "
            "The narrative incorporates detected findings and volume estimates."
        )
    else:
        answer = (
            f"VILA-M3 lite mode: I received your question about this "
            f"{modality or 'imaging'} study ({body_part or 'unspecified region'}). "
            "In production GPU mode, the full vision-language model reasons over slices "
            "and expert model outputs (VISTA3D, TorchXRayVision)."
        )

    if findings_text:
        answer += f"\n\nCurrent findings:\n{findings_text}"

    return AskResponse(answer=answer, engine="vila-m3-lite", mode="lite")


def report_narrative(
    study_id: str,
    patient_name: str | None,
    modality: str | None,
    body_part: str | None,
    description: str | None,
    findings: list[dict],
) -> ReportNarrativeResponse:
    patient = patient_name or "the patient"
    mod = modality or "imaging"
    region = body_part or "the examined region"

    if findings:
        lines = []
        for f in findings:
            conf = int(float(f.get("confidence", 0)) * 100)
            vol = f.get("volume_cc")
            vol_txt = f", estimated volume {vol:.1f} cc" if vol else ""
            lines.append(
                f"{f.get('label', 'Finding')} in {f.get('location', '—')} "
                f"({conf}% confidence{vol_txt}). {f.get('description', '')}"
            )
        findings_block = " ".join(lines)
        impression = (
            f"AI-assisted review identifies {len(findings)} notable finding(s). "
            f"Primary concern: {findings[0].get('label', 'abnormality')} "
            f"({findings[0].get('severity', 'moderate')} severity)."
        )
    else:
        findings_block = "No discrete abnormalities flagged by the automated pipeline."
        impression = "No acute AI-flagged abnormality. Clinical correlation advised."

    narrative = (
        f"EXAMINATION: {mod} of {region}.\n"
        f"CLINICAL CONTEXT: {description or 'Not provided'}.\n\n"
        f"FINDINGS: Automated analysis for {patient} demonstrates the following. "
        f"{findings_block}\n\n"
        f"Generated by VILA-M3 agent framework (lite mode when GPU checkpoint unavailable)."
    )
    return ReportNarrativeResponse(
        narrative=narrative,
        impression=impression,
        engine="vila-m3-lite",
        mode="lite",
    )

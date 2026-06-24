"""Bridge VILA-M3 free-text + expert outputs into Lumira analyze API schema."""

from __future__ import annotations

import base64
import re

from expert_parse import (
    ParsedFinding,
    bbox_for_finding,
    parse_structured_findings,
    structured_description,
    volume_for_finding,
)
from lite_engine import analyze as lite_analyze
from mask_contours import segmentations_from_expert
from schemas import AnalyzeResponse, DetectionOut, SegmentationOut, StudyAnalyzeRequest

_HIGH = re.compile(r"\b(malignant|high.?risk|urgent|critical)\b", re.I)
_MOD = re.compile(r"\b(nodule|lesion|mass|opacity|abnormal|moderate)\b", re.I)

_STRUCTURE = {
    "lung": "organ",
    "heart": "organ",
    "liver": "organ",
    "kidney": "organ",
    "brain": "organ",
    "tumor": "tumor",
    "nodule": "lesion",
    "lesion": "lesion",
}


def _structure_type(label: str) -> str:
    low = label.lower()
    for key, st in _STRUCTURE.items():
        if key in low:
            return st
    return "lesion"


def _recommendation_for(finding: ParsedFinding) -> str:
    if finding.severity == "high":
        return "Urgent radiologist review and correlation with clinical context recommended."
    if finding.size_cm and finding.size_cm >= 2.0:
        return "Short-interval follow-up imaging recommended; correlate with prior studies."
    return "Radiologist review recommended."


def _parsed_to_detection(
    finding: ParsedFinding,
    expert_seg_dicts: list[dict],
) -> DetectionOut:
    vol = volume_for_finding(finding)
    return DetectionOut(
        label=finding.label,
        location=finding.location,
        confidence=round(finding.confidence, 3),
        severity=finding.severity,
        bbox=bbox_for_finding(finding, expert_seg_dicts),
        description=structured_description(finding),
        recommendation=_recommendation_for(finding),
        size_cm=finding.size_cm,
        size_mm=finding.size_mm,
        volume_cc=vol,
    )


def vila_to_analyze_response(
    req: StudyAnalyzeRequest,
    vila_answer: str,
    expert_notes: list[str] | None = None,
    expert_images: list[str] | None = None,
    *,
    z_mm: float = 0.0,
) -> AnalyzeResponse:
    """Merge VILA narrative + expert segmentations into structured detections."""
    base = lite_analyze(req)
    notes = "\n".join(filter(None, [vila_answer, *(expert_notes or [])])).strip()

    expert_seg_dicts = segmentations_from_expert(
        "\n".join(expert_notes or []), list(expert_images or []), z_mm=z_mm
    )
    parsed = parse_structured_findings(vila_answer, expert_notes)

    if parsed:
        detections = [_parsed_to_detection(p, expert_seg_dicts) for p in parsed]
    else:
        detections = []
        for d in base.detections:
            item = d.copy(deep=True) if hasattr(d, "copy") else d.model_copy()
            if notes:
                item.description = f"{structured_description_from_lite(item, notes)}"
            detections.append(item)

        if not detections and notes:
            sev = "high" if _HIGH.search(notes) else ("moderate" if _MOD.search(notes) else "low")
            fallback = parse_structured_findings(notes, None)
            if fallback:
                detections = [_parsed_to_detection(p, expert_seg_dicts) for p in fallback]
            else:
                detections.append(
                    DetectionOut(
                        label="VILA-M3 Finding",
                        location="See narrative",
                        confidence=0.75,
                        severity=sev,
                        bbox={"x": 0.35, "y": 0.35, "w": 0.2, "h": 0.18, "slice": 0.5},
                        description=notes[:2000],
                        recommendation="Radiologist review of VILA-M3 output recommended.",
                    )
                )

    segmentations = list(base.segmentations)
    existing = {s.label for s in segmentations}
    for item in expert_seg_dicts:
        label = item["label"]
        if label in existing:
            continue
        mask_b64 = None
        if expert_images:
            try:
                with open(expert_images[0], "rb") as f:
                    mask_b64 = base64.b64encode(f.read()).decode("ascii")
            except OSError:
                mask_b64 = None
        vol = None
        for det in detections:
            if det.label.lower() in label.lower() or label.lower() in det.label.lower():
                vol = det.volume_cc
                break
        segmentations.append(
            SegmentationOut(
                label=label,
                structure_type=_structure_type(label),
                color=item.get("color", "#38bdf8"),
                stats={
                    "volume_cc": vol,
                    "bbox": item.get("bbox", {}),
                    "source": "vista3d",
                },
                mask_png_b64=mask_b64,
                contours=item.get("contours", []),
            )
        )
        existing.add(label)

    return AnalyzeResponse(
        engine="vila-m3",
        mode="vila",
        detections=detections,
        segmentations=segmentations,
    )


def structured_description_from_lite(item: DetectionOut, notes: str) -> str:
    """Enrich lite detection with parsed size/location/confidence when present."""
    parsed = parse_structured_findings(notes, None)
    if parsed:
        p = parsed[0]
        return structured_description(p)
    base_desc = item.description or ""
    return f"{base_desc}\n\nVILA-M3: {notes[:800]}" if notes else base_desc


def vila_report_from_answer(
    study_id: str,
    patient_name: str | None,
    modality: str | None,
    body_part: str | None,
    description: str | None,
    findings: list[dict],
    vila_answer: str,
) -> tuple[str, str]:
    from lite_engine import report_narrative as lite_report

    lite = lite_report(study_id, patient_name, modality, body_part, description, findings)
    structured = parse_structured_findings(vila_answer, None)
    if structured:
        bullets = []
        for f in structured:
            size = f"{f.size_cm} cm" if f.size_cm else (f"{f.size_mm} mm" if f.size_mm else "—")
            bullets.append(
                f"- {f.label} at {f.location}: size {size}, "
                f"confidence {int(f.confidence * 100)}%"
            )
        narrative = lite.narrative + "\n\n--- STRUCTURED VILA-M3 FINDINGS ---\n" + "\n".join(bullets)
    else:
        narrative = f"{lite.narrative}\n\n--- VILA-M3 CLINICAL REASONING ---\n{vila_answer.strip()}"
    impression = lite.impression
    if structured:
        first = structured[0]
        impression = (
            f"{impression} VILA-M3: {first.label} in {first.location} "
            f"({int(first.confidence * 100)}% confidence)."
        )
    elif vila_answer.strip():
        first = vila_answer.strip().split("\n")[0][:240]
        impression = f"{impression} VILA-M3: {first}"
    return narrative, impression

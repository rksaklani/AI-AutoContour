"""Parse VILA-M3 and expert-model narrative into structured findings."""

from __future__ import annotations

import re
from dataclasses import dataclass

_LABEL_RE = re.compile(
    r"\b("
    r"hepatic\s+tumor|liver\s+(?:tumor|lesion|mass)|lung\s+(?:tumor|nodule|mass)|"
    r"brain\s+tumor|pulmonary\s+nodule|renal\s+(?:mass|lesion)|"
    r"tumor|nodule|lesion|mass|opacity|metastasis|neoplasm"
    r")\b",
    re.I,
)
_SIZE_CM = re.compile(
    r"(?:size|diameter|measuring|measures|approximately|~)\s*[:\s]*"
    r"(\d+(?:\.\d+)?)\s*(?:cm|centimeter)s?\b",
    re.I,
)
_SIZE_MM = re.compile(
    r"(?:size|diameter|measuring|measures)\s*[:\s]*(\d+(?:\.\d+)?)\s*mm\b",
    re.I,
)
_VOLUME_CC = re.compile(
    r"(?:volume|volumetric)\s*[:\s]*(\d+(?:\.\d+)?)\s*(?:cc|cm³|cm3)\b",
    re.I,
)
_CONF_PCT = re.compile(r"confidence\s*[:\s]*(\d+(?:\.\d+)?)\s*%", re.I)
_CONF_FLOAT = re.compile(r"confidence\s*[:\s]*(0\.\d+|\d+\.\d+)\b", re.I)
_INLINE_CONF = re.compile(r"\b(\d{1,3})\s*%\s*confidence\b", re.I)
_LOCATION_KV = re.compile(
    r"location\s*[:\s]+(.+?)(?:\n|$|\.(?:\s|$))",
    re.I,
)
_LOCATION_IN = re.compile(
    r"\b(?:in|within|at)\s+(?:the\s+)?"
    r"((?:right|left|bilateral)\s+)?"
    r"((?:upper|middle|lower|anterior|posterior)\s+)?"
    r"(?:hepatic\s+)?(?:segment\s+[IVXLC\d]+|"
    r"(?:right|left)\s+(?:upper|middle|lower)\s+lobe|"
    r"right\s+upper\s+lobe|right\s+lower\s+lobe|left\s+upper\s+lobe|"
    r"frontal\s+lobe|temporal\s+lobe|parietal\s+lobe|"
    r"hepatic\s+(?:segment\s+)?[IVXLC\d]+|"
    r"right\s+hepatic\s+lobe|left\s+hepatic\s+lobe|"
    r"right\s+lower\s+zone|left\s+lower\s+zone)",
    re.I,
)
_SEVERITY_HIGH = re.compile(r"\b(malignant|high.?risk|urgent|critical|suspicious for)\b", re.I)
_SEVERITY_MOD = re.compile(r"\b(moderate|indeterminate|follow-?up)\b", re.I)

_BLOCK_SPLIT = re.compile(r"\n\s*(?:[-*•]|\d+\.)\s+")


@dataclass
class ParsedFinding:
    label: str
    location: str
    confidence: float
    size_cm: float | None = None
    size_mm: float | None = None
    volume_cc: float | None = None
    severity: str = "moderate"
    description: str = ""
    source_text: str = ""


def _normalize_confidence(raw: float) -> float:
    if raw > 1.0:
        return min(raw / 100.0, 1.0)
    return min(max(raw, 0.0), 1.0)


def _title_label(raw: str) -> str:
    words = raw.strip().split()
    return " ".join(w.capitalize() if w.isalpha() else w for w in words)


def _severity_for(text: str) -> str:
    if _SEVERITY_HIGH.search(text):
        return "high"
    if _SEVERITY_MOD.search(text):
        return "moderate"
    return "low"


def _extract_from_block(block: str) -> ParsedFinding | None:
    block = block.strip()
    if len(block) < 12:
        return None

    label_match = _LABEL_RE.search(block)
    if not label_match and not _SIZE_CM.search(block) and not _CONF_PCT.search(block):
        return None

    label = _title_label(label_match.group(1)) if label_match else "Finding"

    location = "See image"
    loc_kv = _LOCATION_KV.search(block)
    if loc_kv:
        location = loc_kv.group(1).strip().rstrip(".,;")
    else:
        loc_in = _LOCATION_IN.search(block)
        if loc_in:
            location = loc_in.group(0).strip()
            if location.lower().startswith(("in ", "at ", "within ")):
                location = location.split(" ", 1)[1].strip()

    size_cm = None
    m_cm = _SIZE_CM.search(block)
    if m_cm:
        size_cm = float(m_cm.group(1))
    size_mm = None
    m_mm = _SIZE_MM.search(block)
    if m_mm:
        size_mm = float(m_mm.group(1))
        if size_cm is None:
            size_cm = round(size_mm / 10.0, 2)

    volume_cc = None
    m_vol = _VOLUME_CC.search(block)
    if m_vol:
        volume_cc = float(m_vol.group(1))

    confidence = 0.75
    for pat in (_CONF_PCT, _CONF_FLOAT, _INLINE_CONF):
        m = pat.search(block)
        if m:
            confidence = _normalize_confidence(float(m.group(1)))
            break

    return ParsedFinding(
        label=label,
        location=location,
        confidence=confidence,
        size_cm=size_cm,
        size_mm=size_mm,
        volume_cc=volume_cc,
        severity=_severity_for(block),
        description=block[:500],
        source_text=block,
    )


def _blocks_from_text(text: str) -> list[str]:
    if not text:
        return []
    parts = _BLOCK_SPLIT.split(text)
    blocks = [p.strip() for p in parts if p.strip()]
    if not blocks and text.strip():
        blocks = [text.strip()]
    return blocks


def parse_structured_findings(
    vila_answer: str,
    expert_notes: list[str] | None = None,
) -> list[ParsedFinding]:
    """Extract structured tumor/lesion findings from VILA and expert narratives."""
    combined = "\n".join(filter(None, [vila_answer, *(expert_notes or [])])).strip()
    if not combined:
        return []

    findings: list[ParsedFinding] = []
    seen: set[tuple[str, str]] = set()

    for block in _blocks_from_text(combined):
        item = _extract_from_block(block)
        if item is None:
            continue
        key = (item.label.lower(), item.location.lower())
        if key in seen:
            continue
        seen.add(key)
        findings.append(item)

    if not findings:
        item = _extract_from_block(combined)
        if item:
            findings.append(item)

    return findings[:8]


def _estimate_volume_cc(size_cm: float | None) -> float | None:
    if size_cm is None or size_cm <= 0:
        return None
    radius = size_cm / 2.0
    return round((4.0 / 3.0) * 3.14159 * (radius**3), 2)


def structured_description(f: ParsedFinding) -> str:
    lines = [f.description or f"Detected {f.label}."]
    if f.size_cm is not None:
        lines.append(f"Size: {f.size_cm} cm")
    elif f.size_mm is not None:
        lines.append(f"Size: {f.size_mm} mm")
    if f.volume_cc is not None:
        lines.append(f"Volume: {f.volume_cc} cc")
    lines.append(f"Location: {f.location}")
    lines.append(f"Confidence: {int(f.confidence * 100)}%")
    return "\n".join(lines)


def bbox_for_finding(
    finding: ParsedFinding,
    segmentations: list[dict],
) -> dict:
    """Pick bbox from expert segmentations when label/location overlaps."""
    fl = finding.label.lower()
    for seg in segmentations:
        sl = str(seg.get("label", "")).lower()
        if fl in sl or sl in fl or any(tok in sl for tok in fl.split() if len(tok) > 3):
            bbox = seg.get("bbox")
            if bbox:
                return dict(bbox)
    return {"x": 0.35, "y": 0.35, "w": 0.2, "h": 0.18, "slice": 0.5}


def volume_for_finding(finding: ParsedFinding) -> float | None:
    if finding.volume_cc is not None:
        return finding.volume_cc
    return _estimate_volume_cc(finding.size_cm)

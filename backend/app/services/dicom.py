"""DICOM validation and metadata extraction (pydicom)."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime

import pydicom
from pydicom.errors import InvalidDicomError

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DicomMeta:
    valid: bool
    error: str | None = None
    study_instance_uid: str | None = None
    series_instance_uid: str | None = None
    sop_instance_uid: str | None = None
    patient_name: str = ""
    patient_id: str = ""
    patient_sex: str = ""
    patient_age: str = ""
    modality: str = ""
    body_part: str = ""
    description: str = ""
    series_number: int | None = None
    instance_number: int | None = None
    study_date: datetime | None = None
    extra: dict = field(default_factory=dict)


def _parse_dicom_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d")
    except (ValueError, TypeError):
        return None


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def extract_tags(data: bytes, max_value_len: int = 160) -> list[dict]:
    """Extract a flat list of human-readable DICOM tags from raw bytes.

    Reads top-level data elements (excluding pixel data) for a DICOM tag browser.
    Never raises; returns an empty list on failure.
    """
    try:
        ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)
    except Exception:  # noqa: BLE001 - defensive
        return []

    tags: list[dict] = []
    for elem in ds:
        if elem.tag == 0x7FE00010:  # PixelData
            continue
        try:
            if elem.VR == "SQ":
                value = f"<sequence: {len(elem.value)} item(s)>"
            else:
                value = str(elem.value)
            if len(value) > max_value_len:
                value = value[:max_value_len] + "…"
        except Exception:  # noqa: BLE001 - defensive
            value = "<unreadable>"
        tags.append(
            {
                "tag": f"({elem.tag.group:04X},{elem.tag.element:04X})",
                "name": str(getattr(elem, "name", None) or elem.keyword or "Unknown"),
                "vr": str(getattr(elem, "VR", "")),
                "value": value,
            }
        )
    return tags


def parse_dicom(data: bytes) -> DicomMeta:
    """Validate bytes as DICOM and extract metadata. Never raises."""
    try:
        ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=False)
    except (InvalidDicomError, Exception) as exc:  # noqa: BLE001 - defensive
        return DicomMeta(valid=False, error=f"Not a valid DICOM file: {exc}")

    def g(tag: str, default: str = "") -> str:
        return str(getattr(ds, tag, default) or default)

    return DicomMeta(
        valid=True,
        study_instance_uid=g("StudyInstanceUID") or None,
        series_instance_uid=g("SeriesInstanceUID") or None,
        sop_instance_uid=g("SOPInstanceUID") or None,
        patient_name=g("PatientName"),
        patient_id=g("PatientID"),
        patient_sex=g("PatientSex"),
        patient_age=g("PatientAge"),
        modality=g("Modality"),
        body_part=g("BodyPartExamined"),
        description=g("StudyDescription") or g("SeriesDescription"),
        series_number=_as_int(getattr(ds, "SeriesNumber", None)),
        instance_number=_as_int(getattr(ds, "InstanceNumber", None)),
        study_date=_parse_dicom_date(getattr(ds, "StudyDate", None)),
        extra={
            "Rows": _as_int(getattr(ds, "Rows", None)),
            "Columns": _as_int(getattr(ds, "Columns", None)),
            "Manufacturer": g("Manufacturer"),
        },
    )

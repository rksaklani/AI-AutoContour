"""Build viewer overlay payloads (RTSTRUCT contours + mask bboxes)."""

from __future__ import annotations

import io

import pydicom
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.models.segmentation import Segmentation
from app.models.study import Instance, Study
from app.services import rtstruct as rtstruct_service
from app.services import storage

_IMAGE_MODALITIES = {"CT", "MR", "MRI", "PT", "PET", "US", "CR", "DX", "NM"}

# Fallback normalized bboxes when older pipeline runs did not persist stats.bbox.
_DEFAULT_BBOX: dict[str, dict] = {
    "Lungs": {"x": 0.12, "y": 0.18, "w": 0.76, "h": 0.58, "slice": 0.5},
    "Heart": {"x": 0.42, "y": 0.38, "w": 0.28, "h": 0.32, "slice": 0.5},
    "Liver": {"x": 0.35, "y": 0.25, "w": 0.45, "h": 0.5, "slice": 0.5},
    "Kidneys": {"x": 0.2, "y": 0.35, "w": 0.6, "h": 0.4, "slice": 0.5},
    "Brain": {"x": 0.2, "y": 0.15, "w": 0.6, "h": 0.7, "slice": 0.5},
    "Lung Nodule": {"x": 0.35, "y": 0.35, "w": 0.18, "h": 0.16, "slice": 0.5},
}


def collect_slice_z_positions(study: Study) -> list[float]:
    """Sorted unique axial slice Z positions (mm) from image series instances."""
    zs: set[float] = set()
    for series in study.series:
        mod = (series.modality or "").upper()
        if mod not in _IMAGE_MODALITIES:
            continue
        instances = sorted(series.instances, key=lambda i: (i.instance_number or 0))
        for inst in instances:
            try:
                data = storage.get_object(inst.object_key)
                ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)
                ipp = getattr(ds, "ImagePositionPatient", None)
                if ipp is not None and len(ipp) >= 3:
                    zs.add(round(float(ipp[2]), 2))
            except Exception:  # noqa: BLE001
                continue
    return sorted(zs)


def _reference_geometry(study: Study):
    image_instances: list[Instance] = []
    for series in study.series:
        mod = (series.modality or "").upper()
        if mod in _IMAGE_MODALITIES:
            image_instances.extend(series.instances)
    if not image_instances:
        return None
    ref = image_instances[len(image_instances) // 2]
    try:
        return rtstruct_service.reference_geometry_from_image(storage.get_object(ref.object_key))
    except Exception:  # noqa: BLE001
        return None


def _parse_rtstruct_rois(study: Study):
    rt_instances: list[Instance] = []
    for series in study.series:
        if (series.modality or "").upper() == "RTSTRUCT":
            rt_instances.extend(series.instances)
    if not rt_instances:
        return None
    geometry = _reference_geometry(study)
    for inst in rt_instances:
        try:
            rois = rtstruct_service.parse_rtstruct(storage.get_object(inst.object_key), geometry)
        except Exception:  # noqa: BLE001
            continue
        if rois:
            return rois
    return None


def latest_segmentations(segs: list[Segmentation]) -> list[Segmentation]:
    """Keep the newest row per label (handles duplicate rows from older re-runs)."""
    by_label: dict[str, Segmentation] = {}
    for s in sorted(segs, key=lambda x: x.created_at, reverse=True):
        if s.label not in by_label:
            by_label[s.label] = s
    return list(by_label.values())


def latest_findings(findings: list[Finding]) -> list[Finding]:
    """Keep the newest row per label+location pair."""
    by_key: dict[tuple[str, str], Finding] = {}
    for f in sorted(findings, key=lambda x: x.created_at, reverse=True):
        key = (f.label, f.location or "")
        if key not in by_key:
            by_key[key] = f
    return list(by_key.values())


def build_study_overlay(db: Session, study: Study) -> dict:
    """Merge DB segmentations with RTSTRUCT contours / mask URLs for the viewer."""
    segs = latest_segmentations(
        list(db.scalars(select(Segmentation).where(Segmentation.study_id == study.id)).all())
    )
    seg_by_label = {s.label: s for s in segs}
    findings = db.scalars(select(Finding).where(Finding.study_id == study.id)).all()
    finding_bbox_by_label = {f.label: f.bbox for f in findings if f.bbox}

    rt_rois = _parse_rtstruct_rois(study)
    slice_z_mm = collect_slice_z_positions(study)

    rois: list[dict] = []
    seen_labels: set[str] = set()

    if rt_rois:
        for roi in rt_rois:
            seg = seg_by_label.get(roi.label)
            seen_labels.add(roi.label)
            rois.append(
                {
                    "segmentation_id": str(seg.id) if seg else None,
                    "label": roi.label,
                    "color": roi.color,
                    "structure_type": roi.structure_type,
                    "contours": [
                        {"z_mm": c.z_mm, "points": c.points} for c in roi.contours
                    ],
                    "bbox": roi.bbox,
                    "mask_url": None,
                }
            )

    for seg in segs:
        if seg.label in seen_labels:
            continue
        mask_url = (
            storage.presigned_get_url(seg.mask_object_key) if seg.mask_object_key else None
        )
        bbox = (seg.stats or {}).get("bbox") or finding_bbox_by_label.get(seg.label)
        if not bbox:
            bbox = _DEFAULT_BBOX.get(seg.label, {})
        stored_contours = (seg.stats or {}).get("contours") or []
        rois.append(
            {
                "segmentation_id": str(seg.id),
                "label": seg.label,
                "color": seg.color,
                "structure_type": seg.structure_type,
                "contours": stored_contours,
                "bbox": bbox,
                "mask_url": mask_url,
            }
        )

    return {"slice_z_mm": slice_z_mm, "rois": rois}

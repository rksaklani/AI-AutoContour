"""AI pipeline tasks.

The pipeline runs as a sequence of stages. Each stage updates the ``processing_jobs`` row
and publishes a progress event to Redis (``job:{job_id}``) which the API relays over a
WebSocket. ``run_pipeline_sync`` contains the orchestration and is also used directly by
the smoke test (no broker required); ``run_pipeline`` is the Celery entrypoint.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai import get_engine
from app.ai.engine import StudyContext
from app.core.logging import get_logger
from app.core.redis_client import publish_progress
from app.db.session import SessionLocal
from app.models.annotation import Annotation
from app.models.finding import Finding
from app.models.job import (
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_RUNNING,
    ProcessingJob,
)
from app.models.segmentation import Segmentation
from app.models.study import STUDY_ANALYZED, STUDY_ERROR, STUDY_PROCESSING, Study
from app.services import rtstruct as rtstruct_service
from app.services import storage
from app.workers.celery_app import celery_app

# Modalities that carry image pixel data (used as the RTSTRUCT spatial reference).
_IMAGE_MODALITIES = {"CT", "MR", "MRI", "PT", "PET", "US", "CR", "DX", "NM"}

logger = get_logger(__name__)

# (stage, label, target progress on completion)
_PIPELINE = [
    ("validate", "Validating study", 10),
    ("extract_metadata", "Extracting metadata", 20),
    ("store", "Confirming storage", 30),
    ("detect", "Detecting abnormalities", 55),
    ("segment", "Segmenting structures", 75),
    ("annotate", "Placing annotations", 85),
    ("findings", "Generating findings", 95),
    ("report", "Finalizing", 100),
]


def _set_stage(db: Session, job: ProcessingJob, stage: str, progress: int, status: str) -> None:
    job.stage = stage
    job.status = status
    job.progress = progress
    db.commit()
    publish_progress(
        str(job.id),
        {
            "job_id": str(job.id),
            "study_id": str(job.study_id),
            "stage": stage,
            "progress": progress,
            "status": status,
        },
    )


def _clear_prior_analysis(db: Session, study_id: uuid.UUID) -> None:
    """Remove prior AI segmentations, findings, and auto-annotations before re-analysis."""
    db.execute(
        delete(Annotation).where(
            Annotation.study_id == study_id,
            Annotation.ai_generated.is_(True),
        )
    )
    db.execute(delete(Finding).where(Finding.study_id == study_id))
    db.execute(delete(Segmentation).where(Segmentation.study_id == study_id))
    db.commit()


def _build_study_context(study: Study) -> StudyContext:
    """Study metadata + presigned DICOM URLs for volume / VLM engines."""
    series_instances: list[dict] = []
    for series in study.series:
        mod = (series.modality or "").upper()
        if mod not in _IMAGE_MODALITIES:
            continue
        instances = sorted(series.instances, key=lambda i: (i.instance_number or 0))
        for inst in instances:
            series_instances.append(
                {
                    "series_id": str(series.id),
                    "instance_id": str(inst.id),
                    "modality": mod,
                    "object_key": inst.object_key,
                    "url": storage.presigned_get_url(inst.object_key),
                    "instance_number": inst.instance_number,
                }
            )
    return StudyContext(
        study_id=str(study.id),
        modality=study.modality,
        body_part=study.body_part,
        description=study.description,
        instance_count=sum(s.instance_count for s in study.series),
        series_instances=series_instances,
    )


def run_pipeline_sync(job_id: str | uuid.UUID) -> dict:
    db = SessionLocal()
    try:
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == _uuid(job_id)))
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        study = db.scalar(select(Study).where(Study.id == job.study_id))
        if study is None:
            raise ValueError("Study not found")

        study.status = STUDY_PROCESSING
        db.commit()

        # Re-analysis replaces prior AI output (segmentations, findings, annotations).
        _clear_prior_analysis(db, study.id)

        ctx = _build_study_context(study)
        engine = get_engine()
        detections = []
        seg_by_label: dict[str, Segmentation] = {}

        # If the study ships DICOM RT Structure Sets, derive real segmentations + findings
        # from their contours instead of the synthetic stub engine.
        rt_rois = _load_rtstruct_rois(db, study)

        for stage, _label, target in _PIPELINE:
            _set_stage(db, job, stage, target, JOB_RUNNING)

            if stage == "detect":
                detections = [] if rt_rois is not None else engine.detect(ctx)

            elif stage == "segment":
                if rt_rois is not None:
                    for roi in rt_rois:
                        seg = Segmentation(
                            study_id=study.id,
                            label=roi.label,
                            structure_type=roi.structure_type,
                            mask_object_key=None,
                            color=roi.color,
                            stats={
                                "volume_cc": roi.volume_cc,
                                "num_contours": roi.num_contours,
                                "source": "rtstruct",
                                "is_target": roi.is_target,
                                "bbox": roi.bbox,
                            },
                        )
                        db.add(seg)
                        db.flush()
                        seg_by_label[roi.label] = seg
                else:
                    results = engine.segment(ctx, detections)
                    for res in results:
                        mask_key = None
                        if res.get("mask_png"):
                            mask_key = f"studies/{study.id}/masks/{_slug(res['label'])}.png"
                            storage.put_object(mask_key, res["mask_png"], "image/png")
                        seg = Segmentation(
                            study_id=study.id,
                            label=res["label"],
                            structure_type=res["structure_type"],
                            mask_object_key=mask_key,
                            color=res["color"],
                            stats=res["stats"],
                        )
                        db.add(seg)
                        db.flush()
                        seg_by_label[res["label"]] = seg
                db.commit()

            elif stage == "findings":
                if rt_rois is not None:
                    _findings_from_rtstruct(db, study, rt_rois, seg_by_label)
                else:
                    for det in detections:
                        seg = seg_by_label.get(det["label"])
                        finding = Finding(
                            study_id=study.id,
                            segmentation_id=seg.id if seg else None,
                            label=det["label"],
                            location=det["location"],
                            confidence=det["confidence"],
                            volume_cc=(
                                det.get("volume_cc")
                                or (seg.stats.get("volume_cc") if seg else None)
                            ),
                            severity=det["severity"],
                            bbox=det["bbox"],
                            description=det["description"],
                            recommendation=det["recommendation"],
                        )
                        db.add(finding)
                        db.flush()
                        # Auto-annotation (bounding box) for each finding.
                        db.add(
                            Annotation(
                                study_id=study.id,
                                finding_id=finding.id,
                                kind="bbox",
                                geometry=det["bbox"],
                                text=f"{det['label']} ({int(det['confidence'] * 100)}%)",
                                ai_generated=True,
                            )
                        )
                db.commit()

        study.status = STUDY_ANALYZED
        _set_stage(db, job, "done", 100, JOB_COMPLETED)
        db.commit()
        logger.info("Pipeline complete for study %s (%d findings)", study.id, len(detections))
        return {"job_id": str(job.id), "findings": len(detections)}

    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed")
        db.rollback()
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == _uuid(job_id)))
        if job:
            job.status = JOB_FAILED
            job.error = str(exc)
            study = db.scalar(select(Study).where(Study.id == job.study_id))
            if study:
                study.status = STUDY_ERROR
            db.commit()
            publish_progress(
                str(job.id),
                {
                    "job_id": str(job.id),
                    "stage": job.stage,
                    "progress": job.progress,
                    "status": JOB_FAILED,
                    "error": str(exc),
                },
            )
        raise
    finally:
        db.close()


@celery_app.task(name="ai_autocontour.run_pipeline", bind=True, max_retries=0)
def run_pipeline(self, job_id: str) -> dict:  # noqa: ANN001
    return run_pipeline_sync(job_id)


def _load_rtstruct_rois(db: Session, study: Study):
    """Return parsed RTSTRUCT ROIs if the study contains an RT Structure Set, else None."""
    rt_instances = []
    image_instances = []
    for series in study.series:
        mod = (series.modality or "").upper()
        for inst in series.instances:
            if mod == "RTSTRUCT":
                rt_instances.append(inst)
            elif mod in _IMAGE_MODALITIES:
                image_instances.append(inst)

    if not rt_instances:
        return None

    geometry = None
    if image_instances:
        ref = image_instances[len(image_instances) // 2]
        try:
            geometry = rtstruct_service.reference_geometry_from_image(
                storage.get_object(ref.object_key)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load RTSTRUCT reference image: %s", exc)

    for inst in rt_instances:
        try:
            rois = rtstruct_service.parse_rtstruct(storage.get_object(inst.object_key), geometry)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse RTSTRUCT %s: %s", inst.id, exc)
            continue
        if rois:
            logger.info("RTSTRUCT %s parsed into %d ROIs", inst.id, len(rois))
            return rois
    return None


def _findings_from_rtstruct(db: Session, study: Study, rt_rois, seg_by_label) -> None:
    """Create findings for delineated target volumes (CTV/PTV/GTV) from an RT Structure Set."""
    targets = [r for r in rt_rois if r.is_target]
    # If no explicit targets, surface the largest organ structures so the panel isn't empty.
    if not targets:
        targets = sorted(
            [r for r in rt_rois if r.volume_cc],
            key=lambda r: r.volume_cc or 0,
            reverse=True,
        )[:3]

    for roi in targets:
        seg = seg_by_label.get(roi.label)
        finding = Finding(
            study_id=study.id,
            segmentation_id=seg.id if seg else None,
            label=roi.label,
            location="Delineated target volume" if roi.is_target else "Delineated structure",
            confidence=1.0,
            volume_cc=roi.volume_cc,
            severity="high" if roi.is_target else "moderate",
            bbox=roi.bbox,
            description=(
                f"{roi.label} contoured in the RT Structure Set"
                + (
                    f" ({roi.volume_cc} cc across {roi.num_contours} slices)."
                    if roi.volume_cc
                    else "."
                )
            ),
            recommendation=(
                "Confirm target coverage and organ-at-risk constraints."
                if roi.is_target
                else "Radiologist review of delineated structure recommended."
            ),
        )
        db.add(finding)
        db.flush()
        db.add(
            Annotation(
                study_id=study.id,
                finding_id=finding.id,
                kind="bbox",
                geometry=roi.bbox,
                text=roi.label,
                ai_generated=True,
            )
        )


def _uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")

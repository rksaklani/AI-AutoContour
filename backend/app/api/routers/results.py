"""Findings, segmentations and annotation CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routers.studies import _get_owned_study
from app.db.session import get_db
from app.models.annotation import Annotation
from app.models.finding import Finding
from app.models.segmentation import Segmentation
from app.models.user import User
from app.schemas.results import (
    AnnotationCreate,
    AnnotationOut,
    AnnotationUpdate,
    FindingOut,
    SegmentationOut,
    StudyOverlayOut,
)
from app.services import storage
from app.services.overlay import build_study_overlay, latest_findings, latest_segmentations

router = APIRouter(tags=["results"])


@router.get("/studies/{study_id}/findings", response_model=list[FindingOut])
def list_findings(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FindingOut]:
    _get_owned_study(study_id, db, user)
    findings = latest_findings(
        list(
            db.scalars(
                select(Finding)
                .where(Finding.study_id == study_id)
                .order_by(Finding.confidence.desc())
            ).all()
        )
    )
    return [FindingOut.model_validate(f) for f in findings]


@router.get("/studies/{study_id}/segmentations", response_model=list[SegmentationOut])
def list_segmentations(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SegmentationOut]:
    _get_owned_study(study_id, db, user)
    segs = latest_segmentations(
        list(db.scalars(select(Segmentation).where(Segmentation.study_id == study_id)).all())
    )
    out: list[SegmentationOut] = []
    for s in segs:
        item = SegmentationOut.model_validate(s)
        if s.mask_object_key:
            item.mask_url = storage.presigned_get_url(s.mask_object_key)
        out.append(item)
    return out


@router.get("/studies/{study_id}/overlay", response_model=StudyOverlayOut)
def get_study_overlay(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StudyOverlayOut:
    """RTSTRUCT contours + mask bounding boxes for viewer overlays."""
    study = _get_owned_study(study_id, db, user)
    payload = build_study_overlay(db, study)
    return StudyOverlayOut.model_validate(payload)


@router.get("/studies/{study_id}/annotations", response_model=list[AnnotationOut])
def list_annotations(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AnnotationOut]:
    _get_owned_study(study_id, db, user)
    anns = db.scalars(select(Annotation).where(Annotation.study_id == study_id)).all()
    return [AnnotationOut.model_validate(a) for a in anns]


@router.post(
    "/studies/{study_id}/annotations",
    response_model=AnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(
    study_id: uuid.UUID,
    payload: AnnotationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnnotationOut:
    _get_owned_study(study_id, db, user)
    ann = Annotation(
        study_id=study_id,
        finding_id=payload.finding_id,
        created_by=user.id,
        kind=payload.kind,
        geometry=payload.geometry,
        text=payload.text,
        ai_generated=False,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return AnnotationOut.model_validate(ann)


@router.put("/annotations/{annotation_id}", response_model=AnnotationOut)
def update_annotation(
    annotation_id: uuid.UUID,
    payload: AnnotationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnnotationOut:
    ann = db.scalar(select(Annotation).where(Annotation.id == annotation_id))
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Annotation not found")
    _get_owned_study(ann.study_id, db, user)
    if payload.kind is not None:
        ann.kind = payload.kind
    if payload.geometry is not None:
        ann.geometry = payload.geometry
    if payload.text is not None:
        ann.text = payload.text
    db.commit()
    db.refresh(ann)
    return AnnotationOut.model_validate(ann)


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
    annotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    ann = db.scalar(select(Annotation).where(Annotation.id == annotation_id))
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Annotation not found")
    _get_owned_study(ann.study_id, db, user)
    db.delete(ann)
    db.commit()

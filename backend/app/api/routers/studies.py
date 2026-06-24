"""Study CRUD + DICOM upload."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.study import Instance, Series, Study
from app.models.user import User
from app.schemas.study import (
    InstanceOut,
    SeriesOut,
    StudyCreate,
    StudyListItem,
    StudyOut,
    UploadResult,
)
from app.services import storage
from app.services.dicom import extract_tags, parse_dicom

router = APIRouter(prefix="/studies", tags=["studies"])


def _get_owned_study(study_id: uuid.UUID, db: Session, user: User) -> Study:
    study = db.scalar(select(Study).where(Study.id == study_id))
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Study not found")
    role = user.role.name if user.role else None
    if study.owner_id != user.id and role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your study")
    return study


def _study_out(study: Study) -> StudyOut:
    return StudyOut(
        id=study.id,
        patient_name=study.patient_name,
        patient_id=study.patient_id,
        patient_sex=study.patient_sex,
        patient_age=study.patient_age,
        modality=study.modality,
        body_part=study.body_part,
        description=study.description,
        status=study.status,
        study_date=study.study_date,
        created_at=study.created_at,
        series=[
            SeriesOut(
                id=s.id,
                series_instance_uid=s.series_instance_uid,
                modality=s.modality,
                series_number=s.series_number,
                description=s.description,
                instance_count=s.instance_count,
                instances=[
                    InstanceOut(
                        id=i.id,
                        sop_instance_uid=i.sop_instance_uid,
                        instance_number=i.instance_number,
                        object_key=i.object_key,
                        url=storage.presigned_get_url(i.object_key),
                    )
                    for i in sorted(s.instances, key=lambda x: (x.instance_number or 0))
                ],
            )
            for s in study.series
        ],
    )


@router.get("", response_model=list[StudyListItem])
def list_studies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[StudyListItem]:
    role = user.role.name if user.role else None
    stmt = select(Study).order_by(Study.created_at.desc())
    if role != "admin":
        stmt = stmt.where(Study.owner_id == user.id)
    return [StudyListItem.model_validate(s) for s in db.scalars(stmt).all()]


@router.post("", response_model=StudyOut, status_code=status.HTTP_201_CREATED)
def create_study(
    payload: StudyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StudyOut:
    study = Study(
        owner_id=user.id,
        patient_name=payload.patient_name,
        patient_id=payload.patient_id,
        modality=payload.modality,
        body_part=payload.body_part,
        description=payload.description,
    )
    db.add(study)
    db.commit()
    db.refresh(study)
    return _study_out(study)


@router.get("/{study_id}", response_model=StudyOut)
def get_study(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StudyOut:
    return _study_out(_get_owned_study(study_id, db, user))


@router.get("/{study_id}/instances/{instance_id}/metadata")
def get_instance_metadata(
    study_id: uuid.UUID,
    instance_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Return the DICOM tags of a single instance for the tag browser."""
    _get_owned_study(study_id, db, user)
    instance = db.scalar(select(Instance).where(Instance.id == instance_id))
    if instance is None or instance.series.study_id != study_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instance not found")
    try:
        data = storage.get_object(instance.object_key)
    except Exception as exc:  # noqa: BLE001 - defensive
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instance file unavailable") from exc
    return extract_tags(data)


@router.delete("/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    study = _get_owned_study(study_id, db, user)
    storage.delete_prefix(f"studies/{study.id}/")
    db.delete(study)
    db.commit()


@router.post("/{study_id}/upload", response_model=UploadResult)
async def upload_dicom(
    study_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadResult:
    study = _get_owned_study(study_id, db, user)
    accepted = 0
    rejected = 0
    messages: list[str] = []

    # Cache series by SeriesInstanceUID for this upload batch.
    series_cache: dict[str, Series] = {s.series_instance_uid or str(s.id): s for s in study.series}

    for upload in files:
        data = await upload.read()
        meta = parse_dicom(data)
        if not meta.valid:
            rejected += 1
            messages.append(f"{upload.filename}: {meta.error}")
            continue

        # Populate study-level metadata from the first valid instance.
        if not study.modality and meta.modality:
            study.modality = meta.modality
        if not study.patient_name and meta.patient_name:
            study.patient_name = meta.patient_name
        if not study.patient_id and meta.patient_id:
            study.patient_id = meta.patient_id
        if not study.patient_sex and meta.patient_sex:
            study.patient_sex = meta.patient_sex
        if not study.patient_age and meta.patient_age:
            study.patient_age = meta.patient_age
        if not study.body_part and meta.body_part:
            study.body_part = meta.body_part
        if not study.description and meta.description:
            study.description = meta.description
        if not study.study_instance_uid and meta.study_instance_uid:
            study.study_instance_uid = meta.study_instance_uid
        if not study.study_date and meta.study_date:
            study.study_date = meta.study_date

        series_key = meta.series_instance_uid or "default"
        series = series_cache.get(series_key)
        if series is None:
            series = Series(
                study_id=study.id,
                series_instance_uid=meta.series_instance_uid,
                modality=meta.modality,
                series_number=meta.series_number,
                description=meta.description,
                instance_count=0,
            )
            db.add(series)
            db.flush()
            series_cache[series_key] = series

        instance_id = uuid.uuid4()
        object_key = f"studies/{study.id}/raw/{instance_id}.dcm"
        storage.put_object(object_key, data, "application/dicom")

        instance = Instance(
            id=instance_id,
            series_id=series.id,
            sop_instance_uid=meta.sop_instance_uid,
            instance_number=meta.instance_number,
            object_key=object_key,
            dicom_metadata=meta.extra,
        )
        db.add(instance)
        series.instance_count += 1
        accepted += 1

    db.commit()
    return UploadResult(
        study_id=study.id, accepted=accepted, rejected=rejected, messages=messages
    )

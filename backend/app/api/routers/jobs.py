"""Pipeline trigger + job status."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routers.studies import _get_owned_study
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.job import JOB_QUEUED, ProcessingJob
from app.models.study import STUDY_PROCESSING
from app.models.user import User
from app.schemas.results import JobOut

logger = get_logger(__name__)
router = APIRouter(tags=["pipeline"])


@router.post(
    "/studies/{study_id}/analyze",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def analyze(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    study = _get_owned_study(study_id, db, user)
    if not study.series:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Study has no images to analyze")

    job = ProcessingJob(study_id=study.id, status=JOB_QUEUED, stage="validate", progress=0)
    db.add(job)
    study.status = STUDY_PROCESSING
    db.commit()
    db.refresh(job)

    # Dispatch to Celery. If no broker is reachable, fall back to inline execution so the
    # scaffold still works in minimal environments.
    from app.workers.tasks import run_pipeline, run_pipeline_sync

    try:
        run_pipeline.delay(str(job.id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Celery dispatch failed (%s); running inline", exc)
        run_pipeline_sync(str(job.id))
        db.refresh(job)

    return JobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),  # noqa: ARG001
) -> JobOut:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return JobOut.model_validate(job)


@router.get("/studies/{study_id}/jobs", response_model=list[JobOut])
def list_jobs(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[JobOut]:
    _get_owned_study(study_id, db, user)
    jobs = db.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.study_id == study_id)
        .order_by(ProcessingJob.created_at.desc())
    ).all()
    return [JobOut.model_validate(j) for j in jobs]

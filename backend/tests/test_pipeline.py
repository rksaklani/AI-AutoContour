"""Smoke test for the AI pipeline using the stub engine."""

from __future__ import annotations

import uuid

from app.models.job import JOB_COMPLETED, ProcessingJob
from app.models.study import STUDY_ANALYZED, Instance, Series, Study
from app.models.user import User


def _make_study(session) -> Study:
    db = session()
    user = User(email=f"{uuid.uuid4()}@test.dev", hashed_password="x", full_name="T")
    db.add(user)
    db.flush()
    study = Study(
        owner_id=user.id,
        patient_name="Jane Doe",
        modality="CT",
        body_part="CHEST",
        description="CT chest with contrast",
    )
    db.add(study)
    db.flush()
    series = Series(study_id=study.id, modality="CT", instance_count=1)
    db.add(series)
    db.flush()
    db.add(Instance(series_id=series.id, object_key="k.dcm", dicom_metadata={}))
    db.commit()
    sid = study.id
    db.close()
    return sid


def test_pipeline_produces_findings(db_session, monkeypatch):
    monkeypatch.setattr("app.workers.tasks.SessionLocal", db_session)
    from app.workers import tasks

    study_id = _make_study(db_session)

    db = db_session()
    job = ProcessingJob(study_id=study_id)
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    result = tasks.run_pipeline_sync(job_id)
    assert result["findings"] >= 1

    db = db_session()
    job = db.get(ProcessingJob, job_id)
    study = db.get(Study, study_id)
    assert job.status == JOB_COMPLETED
    assert job.progress == 100
    assert study.status == STUDY_ANALYZED
    assert len(study.findings) >= 1
    assert len(study.segmentations) >= 1
    # CT chest should produce a Lung Nodule finding from the stub catalog.
    labels = {f.label for f in study.findings}
    assert "Lung Nodule" in labels
    # Each finding should have an AI-generated annotation.
    assert any(a.ai_generated for a in study.annotations)
    db.close()

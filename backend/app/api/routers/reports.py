"""Report generation + download."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routers.studies import _get_owned_study
from app.db.session import get_db
from app.models.report import REPORT_READY, Report
from app.models.study import STUDY_REPORTED, Study
from app.models.user import User
from app.schemas.results import ReportOut
from app.services import reports as report_service
from app.services import storage

router = APIRouter(tags=["reports"])

_CONTENT_TYPES = {
    "html": "text/html",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _report_out(report: Report) -> ReportOut:
    formats = [
        fmt
        for fmt, key in (
            ("html", report.html_object_key),
            ("pdf", report.pdf_object_key),
            ("docx", report.docx_object_key),
        )
        if key
    ]
    return ReportOut(
        id=report.id,
        study_id=report.study_id,
        status=report.status,
        summary=report.summary,
        created_at=report.created_at,
        formats=formats,
    )


@router.post(
    "/studies/{study_id}/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_report(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportOut:
    study: Study = _get_owned_study(study_id, db, user)
    keys = report_service.generate_and_store(study)
    report = Report(
        study_id=study.id,
        status=REPORT_READY,
        html_object_key=keys.get("html"),
        pdf_object_key=keys.get("pdf"),
        docx_object_key=keys.get("docx"),
        summary={
            "findings": len(study.findings),
            "segmentations": len(study.segmentations),
            "formats": list(keys.keys()),
        },
    )
    db.add(report)
    study.status = STUDY_REPORTED
    db.commit()
    db.refresh(report)
    return _report_out(report)


@router.get("/studies/{study_id}/reports", response_model=list[ReportOut])
def list_reports(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReportOut]:
    _get_owned_study(study_id, db, user)
    reports = db.scalars(
        select(Report).where(Report.study_id == study_id).order_by(Report.created_at.desc())
    ).all()
    return [_report_out(r) for r in reports]


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportOut:
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    _get_owned_study(report.study_id, db, user)
    return _report_out(report)


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: uuid.UUID,
    format: str = Query("pdf", pattern="^(pdf|docx|html)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    _get_owned_study(report.study_id, db, user)

    key = {
        "html": report.html_object_key,
        "pdf": report.pdf_object_key,
        "docx": report.docx_object_key,
    }[format]
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{format} not available")

    data = storage.get_object(key)
    return Response(
        content=data,
        media_type=_CONTENT_TYPES[format],
        headers={
            "Content-Disposition": f'attachment; filename="ai-autocontour-report-{report_id}.{format}"'
        },
    )

"""VILA-M3 AI assistant endpoints (VQA, status)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai import get_engine, get_vila_engine
from app.ai.vila_m3_client import VilaM3Client, VilaM3ClientError
from app.api.deps import get_current_user
from app.api.routers.studies import _get_owned_study
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import AiStatusOut, AskRequest, AskResponse
from app.services import storage

router = APIRouter(tags=["ai"])

_IMAGE_MODALITIES = {"CT", "MR", "MRI", "PT", "PET", "US", "CR", "DX", "NM"}


@router.get("/ai/status", response_model=AiStatusOut)
def ai_status(user: User = Depends(get_current_user)) -> AiStatusOut:  # noqa: ARG001
    engine = get_engine()
    out = AiStatusOut(engine=engine.name, sidecar_reachable=False)
    if settings.AI_ENGINE.lower().strip() != "vila_m3":
        return out
    try:
        health = VilaM3Client().health()
        out.sidecar_reachable = True
        out.sidecar_mode = health.get("mode")
        out.gpu_available = health.get("gpu_available")
        out.vila_loaded = health.get("vila_loaded")
    except VilaM3ClientError:
        pass
    return out


def _study_series_instances(study) -> list[dict]:
    """Presigned DICOM URLs for VILA-M3 image-grounded Q&A."""
    out: list[dict] = []
    for series in study.series:
        mod = (series.modality or "").upper()
        if mod not in _IMAGE_MODALITIES:
            continue
        instances = sorted(series.instances, key=lambda i: (i.instance_number or 0))
        for inst in instances:
            out.append(
                {
                    "series_id": str(series.id),
                    "instance_id": str(inst.id),
                    "modality": mod,
                    "object_key": inst.object_key,
                    "url": storage.presigned_get_url(inst.object_key),
                    "instance_number": inst.instance_number,
                }
            )
    return out


@router.post("/studies/{study_id}/ask", response_model=AskResponse)
def ask_study(
    study_id: uuid.UUID,
    payload: AskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AskResponse:
    study = _get_owned_study(study_id, db, user)
    vila = get_vila_engine()
    if vila is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI assistant requires AI_ENGINE=vila_m3",
        )

    findings_summary = [
        {
            "label": f.label,
            "location": f.location,
            "confidence": f.confidence,
            "severity": f.severity,
            "volume_cc": f.volume_cc,
            "description": f.description,
        }
        for f in study.findings
    ]
    answer = vila.ask(
        str(study.id),
        payload.question,
        modality=study.modality,
        body_part=study.body_part,
        description=study.description,
        findings_summary=findings_summary,
        series_instances=_study_series_instances(study),
    )
    return AskResponse(answer=answer, engine=vila.name, mode=getattr(vila, "_last_mode", None))

"""VILA-M3 GPU sidecar for Lumira.

Exposes analyze / ask / report endpoints. Runs in lite mode by default (no GPU).
Set VILA_M3_MODE=vila and mount MONAI checkpoints for full inference.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from schemas import (
    AnalyzeResponse,
    AskRequest,
    AskResponse,
    HealthResponse,
    ReportNarrativeRequest,
    ReportNarrativeResponse,
    StudyAnalyzeRequest,
)

import runtime

app = FastAPI(title="Lumira VILA-M3 Sidecar", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    runtime.startup()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(**runtime.health())


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(req: StudyAnalyzeRequest) -> AnalyzeResponse:
    return runtime.analyze(req)


@app.post("/v1/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    return runtime.ask(
        req.study_id,
        req.question,
        req.modality,
        req.body_part,
        req.description,
        req.findings_summary,
        [s.model_dump() for s in req.series_instances],
    )


@app.post("/v1/report/narrative", response_model=ReportNarrativeResponse)
def report_narrative(req: ReportNarrativeRequest) -> ReportNarrativeResponse:
    return runtime.report_narrative(
        req.study_id,
        req.patient_name,
        req.modality,
        req.body_part,
        req.description,
        req.findings,
        [s.model_dump() for s in req.series_instances],
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("VILA_M3_PORT", "8100"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

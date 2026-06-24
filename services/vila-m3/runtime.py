"""VILA-M3 runtime — lite fallback or full GPU MONAI session."""

from __future__ import annotations

import logging
import os
import tempfile

from expert_bridge import vila_report_from_answer, vila_to_analyze_response
from expert_parse import parse_structured_findings
from lite_engine import analyze as lite_analyze
from lite_engine import ask as lite_ask
from lite_engine import report_narrative as lite_report_narrative
from schemas import (
    AnalyzeResponse,
    AskResponse,
    ReportNarrativeResponse,
    StudyAnalyzeRequest,
)

logger = logging.getLogger(__name__)

_MODE = os.getenv("VILA_M3_MODE", "lite").lower()
_SESSION = None
_VILA_LOADED = False
_GPU_AVAILABLE = False
_LOAD_ERROR: str | None = None


def _probe_gpu() -> bool:
    try:
        import torch  # noqa: PLC0415

        return torch.cuda.is_available()
    except Exception:  # noqa: BLE001
        return False


def _resolve_model_path() -> tuple[str, str]:
    local = os.getenv("VILA_M3_MODEL_PATH", "").strip()
    hf_id = os.getenv("VILA_M3_MODEL_ID", "MONAI/Llama3-VILA-M3-8B").strip()
    source = os.getenv("VILA_M3_SOURCE", "local").lower()
    if source == "huggingface":
        return hf_id, "huggingface"
    if local:
        return local, "local"
    return hf_id, "huggingface"


def _try_load_vila() -> bool:
    global _SESSION, _VILA_LOADED, _GPU_AVAILABLE, _LOAD_ERROR  # noqa: PLW0603

    if _MODE != "vila":
        _LOAD_ERROR = "VILA_M3_MODE is not 'vila'"
        return False

    _GPU_AVAILABLE = _probe_gpu()
    if not _GPU_AVAILABLE:
        _LOAD_ERROR = "CUDA GPU not available"
        logger.warning("VILA_M3_MODE=vila but no CUDA GPU — falling back to lite")
        return False

    model_path, source = _resolve_model_path()
    if source == "local" and not os.path.isdir(model_path):
        _LOAD_ERROR = f"Checkpoint directory missing: {model_path}"
        logger.warning("%s — falling back to lite", _LOAD_ERROR)
        return False

    try:
        from vila_session import VilaM3Session

        conv_mode = os.getenv("VILA_M3_CONV_MODE", "llama_3")
        logger.info("Loading VILA-M3 from %s (source=%s)", model_path, source)
        _SESSION = VilaM3Session(model_path, source=source, conv_mode=conv_mode)
        _VILA_LOADED = True
        _LOAD_ERROR = None
        return True
    except Exception as exc:  # noqa: BLE001
        _LOAD_ERROR = str(exc)
        logger.exception("Failed to load VILA-M3")
        _VILA_LOADED = False
        _SESSION = None
        return False


def startup() -> None:
    _try_load_vila()


def health() -> dict:
    return {
        "status": "ok",
        "engine": "vila-m3",
        "mode": "vila" if _VILA_LOADED else "lite",
        "gpu_available": _GPU_AVAILABLE or _probe_gpu(),
        "vila_loaded": _VILA_LOADED,
        "load_error": _LOAD_ERROR,
        "model_path": os.getenv("VILA_M3_MODEL_PATH", ""),
    }


def _study_image(req: StudyAnalyzeRequest) -> tuple[str | None, str, float]:
    from volume_io import assemble_nifti_from_series, prepare_study_image

    work = tempfile.mkdtemp(prefix="lumira-study-")
    nifti = assemble_nifti_from_series(req.series_instances, work)
    if nifti:
        logger.info("Assembled NIfTI volume for experts: %s", nifti)
    return prepare_study_image(req.series_instances, work_dir=work)


def _vila_on_image(
    image_path: str,
    modality: str,
    prompt: str,
    *,
    use_model_cards: bool = True,
) -> tuple[str, list[str], list[str]]:
    assert _SESSION is not None
    return _SESSION.run_agent(
        image_path, prompt, modality=modality, use_model_cards=use_model_cards
    )


def _vila_text_only(prompt: str, max_tokens: int = 512) -> str:
    assert _SESSION is not None
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    return _SESSION._generate_local(  # noqa: SLF001
        _SESSION._squash_expert_messages(messages),  # noqa: SLF001
        system_prompt=_SESSION._sys_prompt,  # noqa: SLF001
        max_tokens=max_tokens,
    )


def analyze(req: StudyAnalyzeRequest) -> AnalyzeResponse:
    if _VILA_LOADED and _SESSION is not None:
        try:
            image_path, modality, z_mm = _study_image(req)
            if not image_path:
                raise ValueError("No renderable DICOM instance")
            answer, expert_notes, expert_images = _vila_on_image(
                image_path, modality, _SESSION.analyze_study_prompt()
            )
            return vila_to_analyze_response(
                req,
                answer,
                expert_notes,
                expert_images,
                z_mm=z_mm,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("VILA analyze failed, using lite: %s", exc)
    return lite_analyze(req)


def ask(
    study_id: str,
    question: str,
    modality: str | None,
    body_part: str | None,
    description: str | None,
    findings_summary: list[dict],
    series_instances: list[dict] | None = None,
) -> AskResponse:
    if _VILA_LOADED and _SESSION is not None:
        try:
            req = StudyAnalyzeRequest(
                study_id=study_id,
                modality=modality,
                body_part=body_part,
                description=description,
                series_instances=series_instances or [],
            )
            image_path, mod, _z = _study_image(req)
            qa_prompt = _SESSION.qa_prompt(
                question,
                modality=mod,
                body_part=body_part,
                description=description,
                findings_summary=findings_summary,
            )
            if image_path:
                answer, expert_notes, _imgs = _vila_on_image(
                    image_path,
                    mod,
                    qa_prompt,
                    use_model_cards=True,
                )
                if expert_notes:
                    structured = parse_structured_findings(answer, expert_notes)
                    if structured:
                        answer += "\n\nStructured findings:"
                        for f in structured:
                            size = (
                                f"{f.size_cm} cm"
                                if f.size_cm
                                else (f"{f.size_mm} mm" if f.size_mm else "not measured")
                            )
                            answer += (
                                f"\n- {f.label} at {f.location}: "
                                f"size {size}, confidence {int(f.confidence * 100)}%"
                            )
                    else:
                        answer += "\n\nExpert model output:\n" + "\n".join(expert_notes)
            else:
                answer = _vila_text_only(qa_prompt, max_tokens=768)
            return AskResponse(answer=answer, engine="vila-m3", mode="vila")
        except Exception as exc:  # noqa: BLE001
            logger.exception("VILA ask failed: %s", exc)
    return lite_ask(study_id, question, modality, body_part, findings_summary)


def report_narrative(
    study_id: str,
    patient_name: str | None,
    modality: str | None,
    body_part: str | None,
    description: str | None,
    findings: list[dict],
    series_instances: list[dict] | None = None,
) -> ReportNarrativeResponse:
    if _VILA_LOADED and _SESSION is not None:
        try:
            req = StudyAnalyzeRequest(
                study_id=study_id,
                modality=modality,
                body_part=body_part,
                description=description,
                series_instances=series_instances or [],
            )
            image_path, mod, _z = _study_image(req)
            prompt = (
                f"Patient: {patient_name or 'unknown'}. "
                f"Write a radiology findings paragraph and one-line impression.\n"
            )
            for f in findings:
                prompt += (
                    f"- {f.get('label')} ({f.get('location')}): {f.get('description', '')}\n"
                )

            if image_path:
                answer, expert_notes, _imgs = _vila_on_image(
                    image_path,
                    mod,
                    prompt,
                    use_model_cards=True,
                )
            else:
                answer = _vila_text_only(prompt, max_tokens=768)
                expert_notes = []

            narrative, impression = vila_report_from_answer(
                study_id, patient_name, modality, body_part, description, findings, answer
            )
            if expert_notes:
                narrative += "\n\nExpert model output:\n" + "\n".join(expert_notes)
            return ReportNarrativeResponse(
                narrative=narrative,
                impression=impression,
                engine="vila-m3",
                mode="vila",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("VILA report failed: %s", exc)
    return lite_report_narrative(
        study_id, patient_name, modality, body_part, description, findings
    )

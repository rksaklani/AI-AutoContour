"""Tests for VILA-M3 engine + HTTP client."""

from __future__ import annotations

import base64

from app.ai.engine import StudyContext
from app.ai.vila_m3_client import VilaM3Client, parse_analyze_response
from app.ai.vila_m3_engine import VilaM3Engine


def test_parse_analyze_response_structured_fields():
    data = {
        "detections": [
            {
                "label": "Liver Lesion",
                "location": "Segment VIII",
                "confidence": 0.94,
                "severity": "moderate",
                "bbox": {"x": 0.3, "y": 0.3, "w": 0.1, "h": 0.1},
                "description": "hepatic lesion",
                "recommendation": "follow-up",
                "size_cm": 2.4,
                "volume_cc": 7.2,
            }
        ],
        "segmentations": [],
    }
    dets, _ = parse_analyze_response(data)
    assert dets[0]["size_cm"] == 2.4
    assert dets[0]["volume_cc"] == 7.2


def test_parse_analyze_response():
    data = {
        "detections": [
            {
                "label": "Lung Nodule",
                "location": "RUL",
                "confidence": 0.9,
                "severity": "moderate",
                "bbox": {"x": 0.3, "y": 0.3, "w": 0.1, "h": 0.1},
                "description": "nodule",
                "recommendation": "follow-up",
            }
        ],
        "segmentations": [
            {
                "label": "Lungs",
                "structure_type": "organ",
                "color": "#60a5fa",
                "stats": {"volume_cc": 100},
                "mask_png_b64": base64.b64encode(b"png").decode(),
            }
        ],
    }
    dets, segs = parse_analyze_response(data)
    assert dets[0]["label"] == "Lung Nodule"
    assert segs[0]["mask_png"] == b"png"


def test_vila_m3_engine_uses_sidecar(monkeypatch):
    payload = {
        "engine": "vila-m3-lite",
        "mode": "lite",
        "detections": [
            {
                "label": "Lung Nodule",
                "location": "Right Upper Lobe",
                "confidence": 0.92,
                "severity": "moderate",
                "bbox": {"x": 0.3, "y": 0.35, "w": 0.18, "h": 0.16, "slice": 0.5},
                "description": "nodule",
                "recommendation": "follow-up",
            }
        ],
        "segmentations": [],
    }

    monkeypatch.setattr(VilaM3Client, "analyze", lambda self, ctx: payload)

    engine = VilaM3Engine()
    ctx: StudyContext = {
        "study_id": "abc",
        "modality": "CT",
        "body_part": "CHEST",
        "instance_count": 1,
        "series_instances": [],
    }
    detections = engine.detect(ctx)
    assert detections[0]["label"] == "Lung Nodule"
    segs = engine.segment(ctx, detections)
    assert segs == []


def test_vila_m3_client_health(monkeypatch):
    monkeypatch.setattr(
        VilaM3Client,
        "health",
        lambda self: {"status": "ok", "mode": "lite", "gpu_available": False, "vila_loaded": False},
    )
    health = VilaM3Client(base_url="http://test").health()
    assert health["mode"] == "lite"

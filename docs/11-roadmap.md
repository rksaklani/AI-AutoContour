# 11. Development Roadmap

## Phase 0 — Scaffold (this iteration) ✅
- Monorepo, docker-compose stack, docs.
- Auth + RBAC, study upload, DICOM validation/metadata, MinIO storage.
- Celery pipeline with **stub** AI engine (detect/segment/annotate/findings).
- 2D viewer (Cornerstone3D MPR) + findings panel + report generation (HTML/PDF/DOCX).
- WebSocket job progress. CI.

## Phase 1 — Real AI (single modality)
- Implement `AIEngine` with TotalSegmentator (CT organ segmentation).
- GPU worker pool; model registry; NIfTI mask round-trip.
- Mask overlays in the viewer as labelmaps.
- Validate findings against ground truth; confidence calibration.

## Phase 2 — Multi-modality + detection
- nnU-Net task models (lung nodule, brain tumor, liver lesion).
- MONAI classification/detection bundles; per-modality engine router.
- Severity scoring + structured recommendations.

## Phase 3 — Full viewer
- vtk.js volume rendering wired (transfer functions, cropping, clipping, presets).
- Advanced segmentation editing (3D brush, interpolation, smart scissors).
- Measurement persistence + comparison studies (prior/current).

## Phase 4 — Enterprise & interop
- DICOMWeb (QIDO/WADO/STOW-RS); PACS integration.
- Real-time multi-user collaboration (CRDT/Yjs over WS) on annotations.
- Reporting templates (structured reporting / SR), sign-off workflow.

## Phase 5 — Scale & compliance
- Kubernetes + Helm, autoscaling, observability stack.
- HIPAA/GDPR hardening, audit completeness, pen-test.
- Mobile/companion app (React Native) reusing the API.

## Cross-cutting (ongoing)
- Test coverage, performance budgets, accessibility, i18n, model monitoring/drift.

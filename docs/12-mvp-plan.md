# 12. MVP Plan

## MVP goal

A radiologist can upload a study, get AI-assisted findings with on-image annotations, edit
them, and export a report — end to end, in the browser.

## In scope (MVP = Phase 0 + Phase 1)

1. **Auth**: email/password login, RBAC (admin/radiologist/technician/viewer).
2. **Upload**: DICOM multipart upload; validation + metadata extraction; MinIO storage.
3. **Viewer**: 2D MPR (axial/coronal/sagittal), window/level, zoom/pan, measurements.
4. **AI**: one real model (TotalSegmentator CT) behind the `AIEngine` protocol; findings +
   segmentation + auto-annotations.
5. **Findings panel**: list with label/location/confidence/volume; click-to-locate.
6. **Annotation editing**: adjust/add/remove annotations; persisted.
7. **Reports**: generate + download PDF/DOCX/HTML with findings + measurements + snapshot.
8. **Progress**: live pipeline status via WebSocket.

## Out of scope (post-MVP)
- Full 3D volume rendering interactions.
- Multi-modality detection models.
- PACS/DICOMWeb, real-time collaboration, mobile.

## MVP acceptance criteria
- `docker compose up` boots the full stack cleanly.
- Upload -> analyze -> findings -> annotate -> report works without manual DB steps.
- Pipeline progress is visible live.
- Reports download in all three formats.
- CI green (typecheck, lint, tests incl. pipeline smoke test).

## What iteration 1 delivers toward the MVP
Everything except the *real* model: the stub `AIEngine` satisfies criteria 4-8 with
realistic synthetic output, so the MVP is feature-complete and only needs the model swap
in Phase 1.

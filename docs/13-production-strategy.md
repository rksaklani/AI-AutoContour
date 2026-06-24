# 13. Production-Ready Implementation Strategy

## Principles
- **Contract-first**: stable interfaces (`AIEngine`, REST/WS schemas) so internals evolve
  without breaking consumers.
- **Stateless services, stateful infra**: scale compute freely; data in Postgres/S3/Redis.
- **Everything observable**: logs, metrics, traces, audit.
- **Secure by default**: least privilege, encryption, no PHI in logs.

## Reliability
- Health/readiness probes; graceful shutdown (drain WS + finish in-flight tasks).
- Idempotent pipeline stages keyed by job id; retriable tasks with backoff.
- Dead-letter handling for failed inference; per-stage timeouts.
- Backups: Postgres PITR, S3 versioning + replication.

## Performance & cost
- Presigned URLs for pixel data (no API proxying).
- GPU autoscaling on queue depth (KEDA); batch inference.
- Client-side volume caching; progressive slice loading.
- Object-storage lifecycle tiers for cold studies.

## Security & compliance (HIPAA / GDPR)
- TLS in transit; AES-256 at rest (DB + bucket).
- RBAC + per-resource authorization checks.
- Full audit trail of PHI access (`audit_log`).
- Data retention + right-to-erasure workflows; BAA-ready infra.
- Secrets via a manager (not env files) in prod; image + dependency scanning.
- **Regulatory note**: clinical use requires regulatory clearance (e.g. FDA/CE) and
  validated models; the current stub is explicitly non-diagnostic.

## Interoperability
- DICOMWeb: QIDO-RS (query), WADO-RS (retrieve), STOW-RS (store) under `/dicom-web`.
- HL7/FHIR ImagingStudy + DiagnosticReport resources for EHR integration.
- PACS connectivity via DIMSE gateway or DICOMWeb proxy.

## ML lifecycle
- Model registry + versioning; per-modality engine router.
- Offline eval harness vs. labeled datasets; confidence calibration.
- Production monitoring: drift, input distribution, latency, failure rate.
- Human-in-the-loop: radiologist edits feed back as training signal.

## Quality engineering
- Unit + integration + e2e tests; pipeline smoke tests in CI.
- Load testing for API + worker throughput.
- Accessibility (WCAG), i18n, error budgets / SLOs.

## Rollout
- Phased per [11-roadmap.md](11-roadmap.md); canary deploys; feature flags for new models.
- Migration jobs gated in CD; reversible via Helm rollback.

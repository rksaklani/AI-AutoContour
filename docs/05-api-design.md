# 5. API Design

REST + WebSocket, JSON over HTTP, JWT bearer auth. FastAPI serves interactive docs at
`/docs` (Swagger) and `/redoc`. All collection endpoints are paginated and scoped to the
authenticated user's permissions.

## Conventions

- Base path: `/api/v1`
- Auth: `Authorization: Bearer <access_token>`
- IDs: UUID strings
- Errors: `{ "detail": "message" }` with appropriate HTTP status
- Timestamps: ISO-8601 UTC

## Endpoints

### Auth
| Method | Path | Body | Returns |
|--------|------|------|---------|
| POST | `/auth/register` | email, password, full_name | user |
| POST | `/auth/login` | email, password | access + refresh tokens |
| POST | `/auth/refresh` | refresh_token | new tokens |
| GET | `/auth/me` | — | current user |

### Studies & images
| Method | Path | Notes |
|--------|------|-------|
| GET | `/studies` | list (paginated, filter by modality/status) |
| POST | `/studies` | create study shell |
| GET | `/studies/{id}` | study + series + instances |
| DELETE | `/studies/{id}` | remove study + objects |
| POST | `/studies/{id}/upload` | multipart DICOM upload (1..N files) |
| GET | `/studies/{id}/series/{sid}/instances` | instance list with presigned URLs |

### Pipeline
| Method | Path | Notes |
|--------|------|-------|
| POST | `/studies/{id}/analyze` | enqueue pipeline, returns job |
| GET | `/jobs/{id}` | job status/stage/progress |
| GET | `/studies/{id}/jobs` | job history |

### Results
| Method | Path | Notes |
|--------|------|-------|
| GET | `/studies/{id}/findings` | AI findings |
| GET | `/studies/{id}/segmentations` | segmentation list + mask URLs |
| GET | `/studies/{id}/annotations` | annotations |
| POST | `/studies/{id}/annotations` | create (manual) |
| PUT | `/annotations/{id}` | edit geometry/text |
| DELETE | `/annotations/{id}` | remove |

### Reports
| Method | Path | Notes |
|--------|------|-------|
| POST | `/studies/{id}/reports` | generate (HTML+PDF+DOCX) |
| GET | `/studies/{id}/reports` | list |
| GET | `/reports/{id}` | metadata |
| GET | `/reports/{id}/download?format=pdf\|docx\|html` | stream artifact |

### Realtime
| Protocol | Path | Notes |
|----------|------|-------|
| WS | `/ws/jobs/{id}` | live pipeline progress (Redis pub/sub relay) |

### Health
| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | liveness |
| GET | `/health/ready` | readiness (DB + Redis + S3) |

## Example: analyze flow

```http
POST /api/v1/studies/{id}/analyze
-> 202 { "id": "job-uuid", "status": "queued", "stage": "validate", "progress": 0 }

WS  /ws/jobs/{job-uuid}
<- { "stage": "detect", "progress": 50, "status": "running" }
<- { "stage": "done",  "progress": 100, "status": "completed" }
```

## Versioning & future

- `/api/v1` prefix allows additive v2.
- DICOMWeb (QIDO/WADO/STOW-RS) endpoints planned under `/dicom-web` for PACS interop
  (see [13-production-strategy.md](13-production-strategy.md)).

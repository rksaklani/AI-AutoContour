# 4. Database Schema

PostgreSQL, modeled with SQLAlchemy 2.0 (typed `Mapped[]`) and migrated with Alembic.
Primary keys are UUIDs. Timestamps are timezone-aware. The DICOM hierarchy
(Study -> Series -> Instance) is modeled explicitly.

## ER diagram

```mermaid
erDiagram
  ROLES ||--o{ USERS : has
  USERS ||--o{ STUDIES : owns
  STUDIES ||--o{ SERIES : contains
  SERIES ||--o{ INSTANCES : contains
  STUDIES ||--o{ PROCESSING_JOBS : triggers
  STUDIES ||--o{ FINDINGS : produces
  STUDIES ||--o{ SEGMENTATIONS : produces
  STUDIES ||--o{ ANNOTATIONS : has
  FINDINGS ||--o{ ANNOTATIONS : linked
  FINDINGS ||--o| SEGMENTATIONS : may_have
  STUDIES ||--o{ REPORTS : generates
  USERS ||--o{ AUDIT_LOG : acts

  ROLES {
    uuid id PK
    string name UK
    string description
  }
  USERS {
    uuid id PK
    string email UK
    string hashed_password
    string full_name
    uuid role_id FK
    bool is_active
    datetime created_at
  }
  STUDIES {
    uuid id PK
    uuid owner_id FK
    string study_instance_uid UK
    string patient_id
    string patient_name
    string modality
    string description
    string status
    datetime study_date
    datetime created_at
  }
  SERIES {
    uuid id PK
    uuid study_id FK
    string series_instance_uid UK
    string modality
    int series_number
    string description
    int instance_count
  }
  INSTANCES {
    uuid id PK
    uuid series_id FK
    string sop_instance_uid UK
    int instance_number
    string object_key
    json metadata
  }
  PROCESSING_JOBS {
    uuid id PK
    uuid study_id FK
    string status
    string stage
    int progress
    string error
    datetime created_at
    datetime updated_at
  }
  FINDINGS {
    uuid id PK
    uuid study_id FK
    uuid segmentation_id FK
    string label
    string location
    float confidence
    float volume_cc
    string severity
    json bbox
    string description
    string recommendation
  }
  SEGMENTATIONS {
    uuid id PK
    uuid study_id FK
    string label
    string structure_type
    string mask_object_key
    json stats
  }
  ANNOTATIONS {
    uuid id PK
    uuid study_id FK
    uuid finding_id FK
    uuid created_by FK
    string kind
    json geometry
    string text
    bool ai_generated
  }
  REPORTS {
    uuid id PK
    uuid study_id FK
    string status
    string pdf_object_key
    string docx_object_key
    string html_object_key
    json summary
    datetime created_at
  }
  AUDIT_LOG {
    uuid id PK
    uuid user_id FK
    string action
    string entity_type
    string entity_id
    json detail
    datetime created_at
  }
```

## Key tables

- **studies / series / instances** — mirror DICOM. `object_key` on instances points to the
  raw `.dcm` in MinIO; series carries modality + counts for fast listing.
- **processing_jobs** — single source of truth for pipeline progress. `stage` is one of
  `validate | extract_metadata | store | detect | segment | annotate | findings | report |
  done | failed`; `progress` is 0-100.
- **findings** — structured AI output: label, anatomical `location`, `confidence` (0-1),
  `volume_cc`, `severity`, `bbox` (image coords), free-text `description` + `recommendation`.
- **segmentations** — one row per segmented structure; `mask_object_key` references the
  derived mask (NIfTI/PNG) in MinIO; `stats` holds volume/voxel data.
- **annotations** — user-editable geometry (`kind`: text/bbox/polygon/brush). `ai_generated`
  distinguishes auto-annotations from manual edits; `finding_id` links back to a finding.
- **reports** — generated artifacts; one row produces 3 formats.

## Status enums

- `studies.status`: `uploaded | processing | analyzed | reported | error`
- `processing_jobs.status`: `queued | running | completed | failed`
- `reports.status`: `pending | generating | ready | failed`

## Migrations

Alembic autogenerate; the initial migration creates all tables + the role/admin seed runs
on startup (`app/db/seed.py`). Object data never lives in Postgres — only keys.

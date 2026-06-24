# AI-AutoContour — AI-Powered Medical Imaging Platform

AI-AutoContour is an enterprise-grade, AI-assisted diagnostic medical imaging platform. It goes
beyond a traditional DICOM viewer: users upload medical imaging studies (CT, MRI, PET,
X-Ray, Ultrasound), the platform validates and stores them, runs an AI pipeline to detect
abnormalities and segment structures, auto-annotates findings, and generates structured
radiology reports — all inside a modern, dark-themed web workspace.

> Iteration 1 (this repository) is the **runnable scaffold**: the full architecture is
> wired together and boots with `docker compose up`. The AI layer is **stubbed behind a
> real interface contract** (`AIEngine` protocol) so production models (MONAI, nnU-Net,
> TotalSegmentator) drop in later with **zero API changes**.

---

## Architecture at a glance

```
Browser (React + Cornerstone3D + vtk.js)
        |  HTTPS / WSS
   Nginx reverse proxy
        |
   FastAPI  ──────────────┐
     | enqueue (Redis)     │ reads/writes
     v                     v
  Celery worker        PostgreSQL
     |  AIEngine (stub)
     v
   MinIO / S3  (DICOM, masks, reports)
```

See [`docs/`](docs/) for the full set of deliverables:

| # | Deliverable | Doc |
|---|-------------|-----|
| 1 | Folder structure | [docs/01-architecture.md](docs/01-architecture.md) |
| 2 | Frontend architecture | [docs/02-frontend.md](docs/02-frontend.md) |
| 3 | Backend architecture | [docs/03-backend.md](docs/03-backend.md) |
| 4 | Database schema | [docs/04-database-schema.md](docs/04-database-schema.md) |
| 5 | API design | [docs/05-api-design.md](docs/05-api-design.md) |
| 6 | AI pipeline architecture | [docs/06-ai-pipeline.md](docs/06-ai-pipeline.md) |
| 7 | Viewer architecture | [docs/07-viewer.md](docs/07-viewer.md) |
| 8 | Deployment architecture | [docs/08-deployment.md](docs/08-deployment.md) |
| 9 | Docker setup | [docs/09-docker.md](docs/09-docker.md) |
| 10 | CI/CD pipeline | [docs/10-cicd.md](docs/10-cicd.md) |
| 11 | Development roadmap | [docs/11-roadmap.md](docs/11-roadmap.md) |
| 12 | MVP plan | [docs/12-mvp-plan.md](docs/12-mvp-plan.md) |
| 13 | Production strategy | [docs/13-production-strategy.md](docs/13-production-strategy.md) |

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Then open:

| Service | URL | Notes |
|---------|-----|-------|
| Web app | http://localhost:5173 | AI-AutoContour UI |
| API docs | http://localhost:8000/docs | FastAPI / OpenAPI |
| MinIO console | http://localhost:9001 | user/pass from `.env` |
| Flower (Celery) | http://localhost:5555 | task monitoring |
| Adminer (DB) | http://localhost:8080 | Postgres UI |

Default seeded login: `admin@ai-autocontour.dev` / `admin12345` (see `backend/app/db/seed.py`).

### Try the flow
1. Log in.
2. Create a study and upload DICOM file(s) (any `.dcm`; non-DICOM is rejected by validation).
3. Click **Analyze** — watch live pipeline progress over WebSocket.
4. Review AI findings + auto-annotations in the viewer.
5. Generate and download a report (PDF / DOCX / HTML).

---

## Local development (without Docker)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload          # API
celery -A app.workers.celery_app worker -l info   # worker (separate shell)
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

You still need Postgres, Redis and MinIO running (use `docker compose up postgres redis minio`).

---

## Tech stack

- **Frontend:** React, TypeScript, Vite, TailwindCSS, Zustand, React Query, Cornerstone3D, vtk.js
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Celery, Redis, PostgreSQL, MinIO/S3
- **AI layer:** PyTorch, MONAI, nnU-Net, TotalSegmentator, OpenCV, SimpleITK *(interfaces defined; stub implementation ships in iteration 1)*

## Repository layout

See [docs/01-architecture.md](docs/01-architecture.md). Top level:

```
frontend/   React + Vite SPA
backend/    FastAPI app + Celery worker (shared package)
docs/        Architecture & deliverable documentation
infra/       Dockerfiles, nginx config, init scripts
docker-compose.yml
```

## License

Proprietary — internal scaffold. Not for clinical use. AI-AutoContour is not a medical device and
its AI output (currently stubbed) must not be used for diagnosis.

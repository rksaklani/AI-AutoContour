#!/usr/bin/env bash
# Backend API entrypoint: wait for deps, migrate, seed, then launch uvicorn.
set -euo pipefail

echo "[entrypoint] Running database migrations..."
alembic upgrade head

echo "[entrypoint] Seeding default roles + admin user..."
python -m app.db.seed

echo "[entrypoint] Starting API on ${API_HOST:-0.0.0.0}:${API_PORT:-8000}"
exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"

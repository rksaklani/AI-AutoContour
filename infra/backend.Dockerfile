# Backend image: serves both the FastAPI API and the Celery worker (different commands).
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System libraries:
#  - libpq for psycopg
#  - WeasyPrint needs pango/cairo/gdk-pixbuf for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# App source + dependencies (editable install reads pyproject.toml).
COPY backend/ ./
RUN pip install --upgrade pip && pip install -e .

# Entrypoint runs migrations + seed then launches uvicorn.
COPY infra/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
CMD ["/entrypoint.sh"]

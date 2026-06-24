"""Test fixtures: SQLite DB + stubbed storage/redis so tests need no external services."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("AI_ENGINE", "stub")

import app.models  # noqa: F401,E402
from app.db.base import Base  # noqa: E402


@pytest.fixture()
def db_session(tmp_path):
    db_url = f"sqlite:///{tmp_path/'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def _stub_externals(monkeypatch):
    """In-memory object store + no-op redis publish for all tests."""
    store: dict[str, bytes] = {}

    def put_object(key, data, content_type="application/octet-stream"):
        store[key] = data
        return key

    def get_object(key):
        return store[key]

    monkeypatch.setattr("app.services.storage.put_object", put_object)
    monkeypatch.setattr("app.services.storage.get_object", get_object)
    monkeypatch.setattr("app.services.storage.ensure_bucket", lambda: None)
    monkeypatch.setattr("app.services.storage.delete_prefix", lambda prefix: None)
    monkeypatch.setattr(
        "app.services.storage.presigned_get_url", lambda key, expires=3600: f"memory://{key}"
    )
    monkeypatch.setattr("app.core.redis_client.publish_progress", lambda *a, **k: None)
    monkeypatch.setattr("app.workers.tasks.publish_progress", lambda *a, **k: None)

    from app.ai import get_engine

    get_engine.cache_clear()
    yield
    get_engine.cache_clear()
    return store

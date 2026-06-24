"""API tests using FastAPI TestClient against a SQLite-backed app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.user import Role, User


@pytest.fixture()
def client(db_session, monkeypatch):
    # Seed a role + user directly.
    db = db_session()
    role = Role(name="radiologist", description="t")
    db.add(role)
    db.flush()
    user = User(
        email="doc@test.dev",
        hashed_password="x",
        full_name="Doc",
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    def override_get_db():
        s = db_session()
        try:
            yield s
        finally:
            s.close()

    def override_user():
        s = db_session()
        try:
            yield s.get(User, user_id)
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health():
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"


def test_create_and_list_study(client):
    resp = client.post(
        "/api/v1/studies",
        json={"patient_name": "Jane", "modality": "CT", "body_part": "CHEST"},
    )
    assert resp.status_code == 201, resp.text
    study = resp.json()
    assert study["patient_name"] == "Jane"

    listing = client.get("/api/v1/studies")
    assert listing.status_code == 200
    assert len(listing.json()) >= 1

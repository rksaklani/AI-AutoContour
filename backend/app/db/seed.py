"""Seed default roles and the first admin user.

Idempotent: safe to run on every startup.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User

logger = get_logger(__name__)

DEFAULT_ROLES = {
    "admin": "Full administrative access",
    "radiologist": "Reads studies, edits findings, signs reports",
    "technician": "Uploads studies, runs analysis",
    "viewer": "Read-only access",
}


def seed_roles(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for name, desc in DEFAULT_ROLES.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, description=desc)
            db.add(role)
            db.flush()
        roles[name] = role
    return roles


def seed_admin(db: Session, roles: dict[str, Role]) -> None:
    existing = db.scalar(select(User).where(User.email == settings.FIRST_ADMIN_EMAIL))
    if existing:
        return
    admin = User(
        email=settings.FIRST_ADMIN_EMAIL,
        hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
        full_name="AI-AutoContour Admin",
        is_active=True,
        role_id=roles["admin"].id,
    )
    db.add(admin)
    logger.info("Seeded admin user %s", settings.FIRST_ADMIN_EMAIL)


def run_seed() -> None:
    db = SessionLocal()
    try:
        roles = seed_roles(db)
        seed_admin(db, roles)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()

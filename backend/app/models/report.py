"""Generated reports (HTML / PDF / DOCX)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, uuid_pk

REPORT_PENDING = "pending"
REPORT_GENERATING = "generating"
REPORT_READY = "ready"
REPORT_FAILED = "failed"


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = uuid_pk()
    study_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("studies.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default=REPORT_PENDING)
    html_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pdf_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    docx_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)

    study: Mapped[Study] = relationship(back_populates="reports")  # noqa: F821

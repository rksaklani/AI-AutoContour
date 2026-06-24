"""Segmentation masks produced by the AI engine."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, uuid_pk


class Segmentation(Base, TimestampMixin):
    __tablename__ = "segmentations"

    id: Mapped[uuid.UUID] = uuid_pk()
    study_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("studies.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(128))
    # structure_type: organ | tumor | lesion | bone | vessel
    structure_type: Mapped[str] = mapped_column(String(32), default="organ")
    mask_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    color: Mapped[str] = mapped_column(String(16), default="#38bdf8")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)

    study: Mapped[Study] = relationship(back_populates="segmentations")  # noqa: F821
    findings: Mapped[list[Finding]] = relationship(  # noqa: F821
        back_populates="segmentation"
    )

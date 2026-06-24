"""Structured AI findings."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, uuid_pk


class Finding(Base, TimestampMixin):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = uuid_pk()
    study_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("studies.id", ondelete="CASCADE"), index=True
    )
    segmentation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("segmentations.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(128))
    location: Mapped[str] = mapped_column(String(255), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    volume_cc: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="moderate")  # low|moderate|high
    bbox: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")

    study: Mapped[Study] = relationship(back_populates="findings")  # noqa: F821
    segmentation: Mapped[Segmentation | None] = relationship(  # noqa: F821
        back_populates="findings"
    )
    annotations: Mapped[list[Annotation]] = relationship(  # noqa: F821
        back_populates="finding"
    )

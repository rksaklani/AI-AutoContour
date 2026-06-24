"""User-editable and AI-generated annotations."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, uuid_pk

# kinds: text | bbox | polygon | brush | length | angle | roi
ANNOTATION_KINDS = ["text", "bbox", "polygon", "brush", "length", "angle", "roi"]


class Annotation(Base, TimestampMixin):
    __tablename__ = "annotations"

    id: Mapped[uuid.UUID] = uuid_pk()
    study_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("studies.id", ondelete="CASCADE"), index=True
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), default="text")
    geometry: Mapped[dict] = mapped_column(JSON, default=dict)
    text: Mapped[str] = mapped_column(Text, default="")
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    study: Mapped[Study] = relationship(back_populates="annotations")  # noqa: F821
    finding: Mapped[Finding | None] = relationship(back_populates="annotations")  # noqa: F821

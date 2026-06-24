"""Processing job tracking the AI pipeline."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

# Job status
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"

# Pipeline stages (ordered)
STAGES = [
    "validate",
    "extract_metadata",
    "store",
    "detect",
    "segment",
    "annotate",
    "findings",
    "report",
    "done",
]


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    study_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("studies.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default=JOB_QUEUED, index=True)
    stage: Mapped[str] = mapped_column(String(32), default="validate")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    study: Mapped[Study] = relationship(back_populates="jobs")  # noqa: F821

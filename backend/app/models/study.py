"""DICOM hierarchy: Study -> Series -> Instance."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, uuid_pk

# Study lifecycle status values.
STUDY_UPLOADED = "uploaded"
STUDY_PROCESSING = "processing"
STUDY_ANALYZED = "analyzed"
STUDY_REPORTED = "reported"
STUDY_ERROR = "error"


class Study(Base, TimestampMixin):
    __tablename__ = "studies"

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)

    study_instance_uid: Mapped[str | None] = mapped_column(String(255), index=True)
    patient_id: Mapped[str] = mapped_column(String(255), default="")
    patient_name: Mapped[str] = mapped_column(String(255), default="")
    patient_sex: Mapped[str] = mapped_column(String(16), default="")
    patient_age: Mapped[str] = mapped_column(String(16), default="")
    modality: Mapped[str] = mapped_column(String(32), default="", index=True)
    body_part: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default=STUDY_UPLOADED, index=True)
    study_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="studies")  # noqa: F821
    series: Mapped[list[Series]] = relationship(
        back_populates="study", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[ProcessingJob]] = relationship(  # noqa: F821
        back_populates="study", cascade="all, delete-orphan"
    )
    findings: Mapped[list[Finding]] = relationship(  # noqa: F821
        back_populates="study", cascade="all, delete-orphan"
    )
    segmentations: Mapped[list[Segmentation]] = relationship(  # noqa: F821
        back_populates="study", cascade="all, delete-orphan"
    )
    annotations: Mapped[list[Annotation]] = relationship(  # noqa: F821
        back_populates="study", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(  # noqa: F821
        back_populates="study", cascade="all, delete-orphan"
    )


class Series(Base, TimestampMixin):
    __tablename__ = "series"

    id: Mapped[uuid.UUID] = uuid_pk()
    study_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("studies.id", ondelete="CASCADE"), index=True
    )
    series_instance_uid: Mapped[str | None] = mapped_column(String(255), index=True)
    modality: Mapped[str] = mapped_column(String(32), default="")
    series_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(String(512), default="")
    instance_count: Mapped[int] = mapped_column(Integer, default=0)

    study: Mapped[Study] = relationship(back_populates="series")
    instances: Mapped[list[Instance]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class Instance(Base, TimestampMixin):
    __tablename__ = "instances"

    id: Mapped[uuid.UUID] = uuid_pk()
    series_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    sop_instance_uid: Mapped[str | None] = mapped_column(String(255), index=True)
    instance_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_key: Mapped[str] = mapped_column(String(1024))
    dicom_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    series: Mapped[Series] = relationship(back_populates="instances")

"""Study / series / instance schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StudyCreate(BaseModel):
    patient_name: str = ""
    patient_id: str = ""
    modality: str = ""
    body_part: str = ""
    description: str = ""


class InstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sop_instance_uid: str | None = None
    instance_number: int | None = None
    object_key: str
    url: str | None = None


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    series_instance_uid: str | None = None
    modality: str
    series_number: int | None = None
    description: str
    instance_count: int
    instances: list[InstanceOut] = []


class StudyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_name: str
    patient_id: str
    patient_sex: str
    patient_age: str
    modality: str
    body_part: str
    description: str
    status: str
    study_date: datetime | None = None
    created_at: datetime
    series: list[SeriesOut] = []


class StudyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_name: str
    modality: str
    body_part: str
    description: str
    status: str
    created_at: datetime


class UploadResult(BaseModel):
    study_id: uuid.UUID
    accepted: int
    rejected: int
    messages: list[str] = []

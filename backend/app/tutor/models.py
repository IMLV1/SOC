from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.http_models import Meta, StrictModel
from app.input_validation import InputModel


class TutorInput(InputModel):
    lesson_id: UUID
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question required")
        return value.strip()


class TutorSource(StrictModel):
    document_id: str
    title: str
    excerpt: str
    section_ids: list[str]


class TutorResult(StrictModel):
    answer: str
    sources: list[TutorSource]


class TutorView(StrictModel):
    id: UUID
    lesson_id: UUID
    question: str
    status: Literal["queued", "running", "succeeded", "needs_review", "unavailable", "withdrawn"]
    result: TutorResult | None
    error_code: str | None
    created_at: datetime


class TutorEnvelope(StrictModel):
    data: TutorView
    meta: Meta


class TutorHistory(StrictModel):
    data: list[TutorView]
    meta: Meta


class TutorAvailability(StrictModel):
    available: bool
    reason: str | None
    mode: Literal["dify"] = "dify"
    daily_budget_usd: str


class AvailabilityEnvelope(StrictModel):
    data: TutorAvailability
    meta: Meta

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.http_models import Meta, StrictModel


class StepView(StrictModel):
    id: str
    title: str
    target: str
    explanation: str
    limitation: str


class LessonView(StrictModel):
    id: UUID
    level_id: UUID
    version: int
    title: str
    steps: list[StepView]


class LessonSummary(StrictModel):
    id: UUID
    version: int
    title: str


class LevelView(StrictModel):
    id: UUID
    ordinal: int
    title: str
    lessons: list[LessonSummary]


class PathData(StrictModel):
    levels: list[LevelView]


class PathEnvelope(StrictModel):
    data: PathData
    meta: Meta


class LessonEnvelope(StrictModel):
    data: LessonView
    meta: Meta


class ProgressView(StrictModel):
    lesson_id: UUID
    lesson_version: int
    completed_steps: list[str]
    completed_at: datetime | None
    version: int


class MePathData(StrictModel):
    lessons: list[ProgressView]
    next_action: Literal["continue_lesson", "review_lesson_exam_unavailable"]


class MePathEnvelope(StrictModel):
    data: MePathData
    meta: Meta


class ProgressEnvelope(StrictModel):
    data: ProgressView
    meta: Meta


class ProgressInput(StrictModel):
    expected_version: int = Field(ge=0)

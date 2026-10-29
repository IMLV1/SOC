from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt

from app.http_models import Meta, StrictModel
from app.input_validation import InputModel


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


class LevelStatus(StrictModel):
    level_id: UUID
    unlocked: bool
    all_lessons_completed: bool
    exam_case_count: int = Field(ge=0)
    passed_case_count: int = Field(ge=0)


class MePathData(StrictModel):
    lessons: list[ProgressView]
    next_action: Literal["continue_lesson", "review_lesson_exam_unavailable"]
    level_statuses: list[LevelStatus] = Field(default_factory=list)


class MePathEnvelope(StrictModel):
    data: MePathData
    meta: Meta


class ProgressEnvelope(StrictModel):
    data: ProgressView
    meta: Meta


class ProgressInput(InputModel):
    expected_version: StrictInt = Field(ge=0)

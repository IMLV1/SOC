from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt, field_validator

from app.http_models import Meta, StrictModel
from app.input_validation import InputModel
from app.investigation.models import Disposition, Severity
from app.tutor.models import TutorResult


class PracticeAnswer(InputModel):
    evidence_ids: list[UUID] = Field(min_length=1, max_length=50)
    severity: Severity
    disposition: Disposition
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A reason is required")
        return value.strip()

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate evidence")
        return value


class PracticeDraft(InputModel):
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=50)
    severity: Severity = "medium"
    disposition: Disposition = "undetermined"
    reason: str = Field(default="", max_length=2000)


class DraftInput(InputModel):
    expected_version: StrictInt = Field(ge=0)
    answer: PracticeDraft


class PracticeSummary(StrictModel):
    id: UUID
    stable_key: str
    level_id: UUID
    level: int
    category: str
    title: str
    version: int
    available: bool


class PracticeCatalog(StrictModel):
    data: list[PracticeSummary]
    meta: Meta


class PracticeEvent(StrictModel):
    id: UUID
    time: datetime
    source: str
    asset: str
    username: str
    src_ip: str
    request: dict[str, object] | None
    response: dict[str, object] | None
    log: dict[str, object]


class PracticeCase(PracticeSummary):
    prompt: str
    events: list[PracticeEvent]
    draft: PracticeDraft | None = None
    draft_version: int = 0
    draft_saved_at: datetime | None = None


class CaseEnvelope(StrictModel):
    data: PracticeCase
    meta: Meta


class PracticeFeedback(StrictModel):
    mode: Literal["deterministic"]
    classification_correct: bool
    evidence_correct: bool
    expected_severity: Severity
    expected_disposition: Disposition
    explanation: str
    limitation: str
    reason_review_status: Literal["unavailable"]
    reason_review_message: str
    is_exam_result: Literal[False]


class AnswerView(StrictModel):
    id: UUID
    case_id: UUID
    case_version: int
    answer: PracticeAnswer
    feedback: PracticeFeedback
    created_at: datetime


class AnswerEnvelope(StrictModel):
    data: AnswerView
    meta: Meta


class HistoryEnvelope(StrictModel):
    data: list[AnswerView]
    meta: Meta


class PracticeAIInput(InputModel):
    answer_id: UUID
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question required")
        return value.strip()


class PracticeAIView(StrictModel):
    id: UUID
    case_id: UUID
    answer_id: UUID
    question: str
    status: Literal["queued", "running", "succeeded", "needs_review", "unavailable", "withdrawn"]
    result: TutorResult | None
    error_code: str | None
    created_at: datetime


class PracticeAIEnvelope(StrictModel):
    data: PracticeAIView
    meta: Meta


class PracticeAIHistory(StrictModel):
    data: list[PracticeAIView]
    meta: Meta


class WrittenAnswer(InputModel):
    question_id: UUID
    answer: str = Field(min_length=1, max_length=2000)

    @field_validator("answer")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Answer required")
        return value.strip()


class WrittenInput(InputModel):
    answers: list[WrittenAnswer] = Field(min_length=10, max_length=10)


class WrittenQuestion(StrictModel):
    id: UUID
    ordinal: int
    version: int
    prompt: str
    category: str


class QuestionsEnvelope(StrictModel):
    data: list[WrittenQuestion]
    meta: Meta


class WrittenView(StrictModel):
    id: UUID
    level_id: UUID
    status: Literal["needs_review"]
    answers: list[WrittenAnswer]
    questions: list[WrittenQuestion]
    created_at: datetime


class WrittenEnvelope(StrictModel):
    data: WrittenView
    meta: Meta


class WrittenHistory(StrictModel):
    data: list[WrittenView]
    meta: Meta

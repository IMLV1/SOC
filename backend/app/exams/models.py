from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt

from app.auth.models import Strict
from app.grading.exam_policy import ExamSubmission
from app.http_models import Meta
from app.input_validation import InputModel, NonBlankText


class StartAttemptInput(InputModel):
    expected_progress_version: StrictInt = Field(ge=1)


class SubmitInput(ExamSubmission):
    pass


class ReviewInput(InputModel):
    expected_version: StrictInt = Field(ge=1)
    criterion_scores: dict[str, StrictInt | None]
    reason: NonBlankText = Field(min_length=1, max_length=2000)


class ExamEvent(Strict):
    id: UUID
    run_id: UUID
    release_seq: int
    event_time: datetime
    ingested_at: datetime
    source: str
    asset_id: str | None
    username: str | None
    src_ip: str | None
    request: dict[str, object] | None
    response: dict[str, object] | None
    log: dict[str, object]


class AttemptView(Strict):
    id: UUID
    run_id: UUID
    level_id: UUID
    status: Literal[
        "in_progress", "submitted", "needs_review", "passed", "failed", "expired", "reset"
    ]
    version: int
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None


class AttemptData(AttemptView):
    events: list[ExamEvent]
    answer: dict[str, object] | None = None


class AttemptEnvelope(Strict):
    data: AttemptData
    meta: Meta


class ResultCriterion(Strict):
    key: str
    score: int
    maximum: int
    feedback: str


class ResultData(Strict):
    attempt_id: UUID
    status: Literal["submitted", "needs_review", "passed", "failed", "expired", "reset"]
    score: int | None = None
    maximum: int = 8
    criteria: list[ResultCriterion] = Field(default_factory=list)


class ResultEnvelope(Strict):
    data: ResultData
    meta: Meta


class InstructorAttemptData(Strict):
    attempt: AttemptView
    events: list[ExamEvent]
    answer: dict[str, object]
    private_truth: dict[str, object]


class InstructorAttemptEnvelope(Strict):
    data: InstructorAttemptData
    meta: Meta

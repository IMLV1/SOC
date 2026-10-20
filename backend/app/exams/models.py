from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt

from app.auth.models import Strict
from app.http_models import Meta
from app.investigation.models import Disposition, Severity


class StartAttemptInput(Strict):
    expected_progress_version: int = Field(ge=1)


class SubmitInput(Strict):
    expected_version: int = Field(ge=1)
    evidence_event_ids: list[UUID] = Field(min_length=1, max_length=50)
    severity: Severity
    disposition: Disposition
    reason: str = Field(min_length=1, max_length=2000)


class ReviewInput(Strict):
    expected_version: int = Field(ge=1)
    criterion_scores: dict[str, StrictInt | None]
    reason: str = Field(min_length=1, max_length=2000)


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
    status: Literal["in_progress", "submitted", "needs_review", "passed", "failed", "expired"]
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
    status: Literal["submitted", "needs_review", "passed", "failed", "expired"]
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

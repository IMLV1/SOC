from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt, field_validator

from app.auth.models import AuthMeta, PageMeta, Strict
from app.input_validation import InputModel, NonBlankText

Severity = Literal["low", "medium", "high", "critical"]
TicketStatus = Literal["open", "investigating", "resolved", "closed"]
Disposition = Literal["true_positive", "false_positive", "undetermined"]


def unique_ids(value: list[UUID]) -> list[UUID]:
    if len(value) != len(set(value)):
        raise ValueError("Duplicate evidence")
    return value


class TicketCreate(InputModel):
    title: NonBlankText = Field(min_length=1, max_length=120)
    severity: Severity
    evidence_ids: list[UUID] = Field(min_length=1, max_length=50)
    reason: NonBlankText = Field(min_length=1, max_length=2000)

    @field_validator("evidence_ids")
    @classmethod
    def distinct(cls, value: list[UUID]) -> list[UUID]:
        return unique_ids(value)


class TicketPatch(InputModel):
    expected_version: StrictInt = Field(ge=1)
    reason: NonBlankText = Field(min_length=1, max_length=2000)
    title: NonBlankText | None = Field(default=None, min_length=1, max_length=120)
    severity: Severity | None = None
    status: TicketStatus | None = None
    disposition: Disposition | None = None


class InstructorTicketPatch(InputModel):
    expected_version: StrictInt = Field(ge=1)
    reason: NonBlankText = Field(min_length=1, max_length=2000)
    severity: Severity | None = None
    status: TicketStatus | None = None


class DeleteInput(InputModel):
    expected_version: StrictInt = Field(ge=1)
    reason: NonBlankText = Field(min_length=1, max_length=2000)


class AssessmentView(Strict):
    id: UUID
    revision: int
    author_user_id: UUID
    disposition: Disposition
    reason: str
    created_at: datetime


class TicketView(Strict):
    id: UUID
    run_id: UUID
    origin: Literal["automatic", "manual"]
    correlation_key: str | None
    title: str
    severity: Severity
    human_severity_override: bool
    status: TicketStatus
    version: int
    evidence_ids: list[UUID]
    latest_assessment: AssessmentView | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TicketEnvelope(Strict):
    data: TicketView
    meta: AuthMeta


class TicketList(Strict):
    data: list[TicketView]
    meta: PageMeta


class TicketTimelineEntry(Strict):
    id: UUID
    kind: Literal["event", "audit", "assessment"]
    occurred_at: datetime
    action: str
    event_id: UUID | None


class TicketTimelineList(Strict):
    data: list[TicketTimelineEntry]
    meta: PageMeta


class NoteCreate(InputModel):
    body: NonBlankText = Field(min_length=1, max_length=2000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("evidence_ids")
    @classmethod
    def distinct(cls, value: list[UUID]) -> list[UUID]:
        return unique_ids(value)


class NotePatch(NoteCreate):
    expected_version: StrictInt = Field(ge=1)
    reason: NonBlankText = Field(min_length=1, max_length=2000)


class NoteView(Strict):
    id: UUID
    ticket_id: UUID
    owner_user_id: UUID
    body: str
    version: int
    evidence_ids: list[UUID]
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NoteVersionView(Strict):
    version: int
    body: str
    change_kind: Literal["create", "edit", "delete", "restore"]
    reason: str | None
    actor_user_id: UUID
    evidence_ids: list[UUID]
    created_at: datetime


class NoteEnvelope(Strict):
    data: NoteView
    meta: AuthMeta


class NoteList(Strict):
    data: list[NoteView]
    meta: PageMeta


class VersionList(Strict):
    data: list[NoteVersionView]
    meta: PageMeta


class AssessmentList(Strict):
    data: list[AssessmentView]
    meta: PageMeta

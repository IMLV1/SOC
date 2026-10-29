from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, StrictInt

from app.auth.models import AuthMeta, PageMeta, Strict
from app.input_validation import InputModel


class RunView(Strict):
    id: UUID
    status: Literal[
        "created", "running", "paused", "reviewing", "completing", "completed", "failed"
    ]
    version: int
    elapsed_ms: int
    duration_ms: int
    server_time: datetime
    expires_at: datetime
    seed: int
    analysis_mode: Literal["mock", "real"]


class RunEnvelope(Strict):
    data: RunView
    meta: AuthMeta


class FinishView(RunView):
    evaluation_url: str


class FinishEnvelope(Strict):
    data: FinishView
    meta: AuthMeta


class RunList(Strict):
    data: list[RunView]
    meta: PageMeta


class VersionInput(InputModel):
    expected_version: StrictInt = Field(ge=1)


class EventView(Strict):
    id: UUID
    run_id: UUID
    release_seq: int
    event_time: datetime
    ingested_at: datetime
    source: str
    asset_id: str | None
    username: str | None
    src_ip: str | None
    request: dict[str, Any] | None
    response: dict[str, Any] | None
    log: dict[str, Any]


class EventPageMeta(PageMeta):
    pass


class EventList(Strict):
    data: list[EventView]
    meta: EventPageMeta


class EventEnvelope(Strict):
    data: EventView
    meta: AuthMeta


class AlertView(Strict):
    id: UUID
    run_id: UUID
    severity: Literal["low", "medium", "high", "critical"]
    detector_type: Literal["rule", "anomaly"]
    detector_version: str
    correlation_key: str
    explanation: str
    evidence_ids: list[UUID]
    ticket_id: UUID | None
    created_at: datetime


class AlertList(Strict):
    data: list[AlertView]
    meta: EventPageMeta


class AlertEnvelope(Strict):
    data: AlertView
    meta: AuthMeta

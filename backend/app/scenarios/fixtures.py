"""Strict server-only fixture format; schedules never enter public serializers."""

import hashlib
import json
from pathlib import Path
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.auth.models import Strict


def content_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class RequestData(Strict):
    method: Literal["GET", "POST"]
    path: str = Field(pattern=r"^/", max_length=200)


class ResponseData(Strict):
    status: int = Field(ge=100, le=599)
    bytes_sent: int = Field(default=0, ge=0)


class LogData(Strict):
    event_type: str
    session_id: str | None = None
    records_read: int | None = Field(default=None, ge=0)
    change_ref: str | None = None
    scope: str | None = None
    baseline_reads_per_minute: int | None = Field(default=None, ge=0)


class FixtureEvent(Strict):
    key: str = Field(pattern=r"^e[0-9]{3}$")
    release_offset_ms: int = Field(ge=0)
    event_offset_ms: int = Field(ge=0)
    source: Literal["authentication", "web", "file_access", "change_management", "baseline"]
    asset_id: str
    username: str
    src_ip: str = Field(pattern=r"^(192\.0\.2\.|198\.51\.100\.|203\.0\.113\.)[0-9]{1,3}$")
    request: RequestData
    response: ResponseData
    log: LogData


class EventFixture(Strict):
    schema_version: Literal[1]
    purpose: Literal["training", "exam"]
    scenario_id: UUID
    duration_ms: int = Field(gt=0)
    events: list[FixtureEvent] = Field(min_length=1)

    @model_validator(mode="after")
    def schedule(self) -> Self:
        keys = [event.key for event in self.events]
        offsets = [event.release_offset_ms for event in self.events]
        if len(set(keys)) != len(keys) or offsets != sorted(offsets):
            raise ValueError("Invalid fixture sequence")
        if any(
            event.event_offset_ms > event.release_offset_ms
            or event.release_offset_ms > self.duration_ms
            for event in self.events
        ):
            raise ValueError("Invalid fixture time")
        return self


def load_fixture(path: Path, purpose: Literal["training", "exam"]) -> EventFixture:
    fixture = EventFixture.model_validate_json(path.read_text(encoding="utf-8"))
    if fixture.purpose != purpose:
        raise ValueError("Fixture purpose mismatch")
    return fixture


def load_training_fixture(path: Path) -> EventFixture:
    return load_fixture(path, "training")

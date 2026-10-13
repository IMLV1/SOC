"""Closed projections to adopt before any exam route is approved.

This module grants no access. Future handlers must authorize owner/assignment,
validate released evidence and enforce submit gates before calling a projection.
Unknown surfaces (including results until D-04) fail closed, even after completion.
"""

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.auth.models import Strict


class ExamProjectionDenied(ValueError):
    def __init__(self) -> None:
        super().__init__("Exam projection unavailable")


class BlindRun(Strict):
    id: UUID
    mode: Literal["exam"] = "exam"
    status: Literal[
        "created", "running", "paused", "reviewing", "completing", "completed", "failed"
    ]
    version: int = Field(ge=1)
    elapsed_ms: int = Field(ge=0)


class BlindAlert(Strict):
    id: UUID
    run_id: UUID
    evidence_ids: list[UUID]


class BlindTicket(BlindAlert):
    title: Literal["Investigation"] = "Investigation"
    status: Literal["open", "investigating", "resolved", "closed"]
    version: int = Field(ge=1)


def project_exam(surface: str, source: Mapping[str, object]) -> Strict:
    # Construct only from explicit scalars/IDs; never pass nested training DTOs.
    try:
        if surface == "run":
            return BlindRun.model_validate(
                {key: source[key] for key in ("id", "status", "version", "elapsed_ms")}
            )
        if surface == "alert":
            return BlindAlert.model_validate(
                {key: source[key] for key in ("id", "run_id", "evidence_ids")}
            )
        if surface == "ticket":
            return BlindTicket.model_validate(
                {key: source[key] for key in ("id", "run_id", "evidence_ids", "status", "version")}
            )
    except (KeyError, ValueError, TypeError):
        raise ExamProjectionDenied() from None
    raise ExamProjectionDenied()

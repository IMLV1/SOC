"""Policy primitives for server-admitted, immutable exam attempts."""

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.auth.models import Strict
from app.investigation.models import Disposition, Severity

AttemptStatus = Literal["in_progress", "submitted", "needs_review", "passed", "failed", "expired"]
ACTIVE_STATUSES = frozenset({"in_progress", "submitted", "needs_review"})
MAX_ATTEMPTS_PER_WINDOW = 9
MAX_ATTEMPTS_PER_CASE_PER_WINDOW = 3
ATTEMPT_WINDOW = timedelta(hours=24)
FAILED_COOLDOWN = timedelta(hours=1)
MAX_EVIDENCE = 50


class ExamSubmission(Strict):
    expected_version: int = Field(ge=1)
    evidence_event_ids: list[UUID] = Field(min_length=1, max_length=MAX_EVIDENCE)
    severity: Severity
    disposition: Disposition
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("evidence_event_ids")
    @classmethod
    def unique_evidence(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate evidence event")
        return value


class AdmissionDecision:
    def __init__(self, allowed: bool, code: str | None = None) -> None:
        self.allowed = allowed
        self.code = code


def check_admission(
    *,
    active_statuses: Iterable[str],
    started_at: Iterable[datetime],
    last_failed_at: datetime | None,
    now: datetime,
) -> AdmissionDecision:
    """Check the delegated D-02 limits against DB-derived timestamps/statuses."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now_utc = now.astimezone(UTC)
    if any(status in ACTIVE_STATUSES for status in active_statuses):
        return AdmissionDecision(False, "EXAM_ATTEMPT_ACTIVE")
    start_values = list(started_at)
    if any(value.tzinfo is None or value.utcoffset() is None for value in start_values):
        raise ValueError("started_at must contain timezone-aware timestamps")
    starts = [value.astimezone(UTC) for value in start_values]
    if (
        sum(now_utc - ATTEMPT_WINDOW < value <= now_utc for value in starts)
        >= MAX_ATTEMPTS_PER_WINDOW
    ):
        return AdmissionDecision(False, "EXAM_ATTEMPT_QUOTA_EXCEEDED")
    if last_failed_at is not None:
        if last_failed_at.tzinfo is None or last_failed_at.utcoffset() is None:
            raise ValueError("last_failed_at must be timezone-aware")
        if now_utc < last_failed_at.astimezone(UTC) + FAILED_COOLDOWN:
            return AdmissionDecision(False, "EXAM_COOLDOWN_ACTIVE")
    return AdmissionDecision(True)


def validate_submission_evidence(
    submitted_ids: Iterable[UUID], released_ids: Iterable[UUID]
) -> list[UUID]:
    """Accept evidence only from the immutable released set of this attempt."""
    submitted = list(submitted_ids)
    released = set(released_ids)
    if not submitted or len(submitted) > MAX_EVIDENCE or len(set(submitted)) != len(submitted):
        raise ValueError("Invalid evidence selection")
    if not set(submitted) <= released:
        raise ValueError("Evidence must reference released events from this attempt")
    return submitted


def learner_result(source: Mapping[str, object]) -> dict[str, object]:
    """Build a learner allowlist; unknown/private result fields never pass through."""
    allowed = ("attempt_id", "status", "score", "maximum", "criteria", "submitted_at")
    result = {key: source[key] for key in allowed if key in source}
    if "attempt_id" not in result or "status" not in result:
        raise ValueError("Incomplete learner result")
    if result["status"] not in {"submitted", "needs_review", "passed", "failed", "expired"}:
        raise ValueError("Invalid learner result")
    criteria = result.get("criteria")
    if criteria is not None:
        if not isinstance(criteria, list):
            raise ValueError("Invalid criteria projection")
        result["criteria"] = [
            {key: item[key] for key in ("key", "score", "maximum", "feedback") if key in item}
            for item in criteria
            if isinstance(item, Mapping)
        ]
    return result

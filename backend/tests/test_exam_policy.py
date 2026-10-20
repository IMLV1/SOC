from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.grading.exam_policy import (
    ExamSubmission,
    check_admission,
    learner_result,
    validate_submission_evidence,
)


def test_exam_admission_enforces_active_attempt_daily_cap_and_cooldown():
    now = datetime(2026, 10, 18, 12, tzinfo=UTC)
    active = check_admission(
        active_statuses=["needs_review"], started_at=[], last_failed_at=None, now=now
    )
    assert active.code == "EXAM_ATTEMPT_ACTIVE"

    capped = check_admission(
        active_statuses=[],
        started_at=[now - timedelta(hours=index) for index in range(1, 10)],
        last_failed_at=None,
        now=now,
    )
    assert capped.code == "EXAM_ATTEMPT_QUOTA_EXCEEDED"

    cooldown = check_admission(
        active_statuses=[], started_at=[], last_failed_at=now - timedelta(minutes=30), now=now
    )
    assert cooldown.code == "EXAM_COOLDOWN_ACTIVE"

    allowed = check_admission(
        active_statuses=["passed"],
        started_at=[now - timedelta(hours=25)],
        last_failed_at=now - timedelta(hours=2),
        now=now,
    )
    assert allowed.allowed


def test_exam_level_window_allows_three_cases_with_three_attempts_each():
    now = datetime(2026, 10, 18, 12, tzinfo=UTC)
    allowed = check_admission(
        active_statuses=[],
        started_at=[now - timedelta(hours=index) for index in range(1, 9)],
        last_failed_at=None,
        now=now,
    )
    capped = check_admission(
        active_statuses=[],
        started_at=[now - timedelta(hours=index) for index in range(1, 10)],
        last_failed_at=None,
        now=now,
    )
    assert allowed.allowed
    assert capped.code == "EXAM_ATTEMPT_QUOTA_EXCEEDED"


def test_admission_rejects_naive_database_timestamps():
    now = datetime(2026, 10, 18, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        check_admission(
            active_statuses=[], started_at=[datetime(2026, 10, 18)], last_failed_at=None, now=now
        )


def test_submission_requires_unique_nonempty_evidence_and_strict_answer_fields():
    evidence_id = uuid4()
    body = ExamSubmission.model_validate(
        {
            "expected_version": 1,
            "evidence_event_ids": [str(evidence_id)],
            "severity": "high",
            "disposition": "true_positive",
            "reason": "เหตุการณ์สัมพันธ์กันตามลำดับเวลา",
        }
    )
    assert body.evidence_event_ids == [evidence_id]
    with pytest.raises(ValidationError):
        ExamSubmission.model_validate(
            {
                "expected_version": 1,
                "evidence_event_ids": [str(evidence_id), str(evidence_id)],
                "severity": "high",
                "disposition": "true_positive",
                "reason": "เหตุผล",
            }
        )
    with pytest.raises(ValidationError):
        ExamSubmission.model_validate(
            {
                "expected_version": 1,
                "evidence_event_ids": [str(evidence_id)],
                "severity": "high",
                "disposition": "true_positive",
                "reason": "เหตุผล",
                "passed": True,
            }
        )


def test_submission_evidence_is_limited_to_this_attempt_released_event_ids():
    allowed, forbidden = uuid4(), uuid4()
    assert validate_submission_evidence([allowed], [allowed, forbidden]) == [allowed]
    with pytest.raises(ValueError, match="released events"):
        validate_submission_evidence([forbidden], [allowed])


def test_learner_result_uses_allowlist_and_redacts_private_feedback_sources():
    safe = learner_result(
        {
            "attempt_id": "a",
            "status": "passed",
            "score": 6,
            "maximum": 8,
            "criteria": [
                {"key": "evidence", "score": 2, "maximum": 2, "feedback": "ดี", "expected": "e001"}
            ],
            "answer_key": "private",
            "model_rationale": "private",
        }
    )
    assert safe == {
        "attempt_id": "a",
        "status": "passed",
        "score": 6,
        "maximum": 8,
        "criteria": [{"key": "evidence", "score": 2, "maximum": 2, "feedback": "ดี"}],
    }

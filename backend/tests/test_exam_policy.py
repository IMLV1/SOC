from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.grading.exam_policy import (
    ExamSubmission,
    check_admission,
    learner_result,
    validate_submission_evidence,
)


def test_exam_admission_allows_unlimited_retakes_but_only_one_active_attempt():
    active = check_admission(active_statuses=["needs_review"])
    assert active.code == "EXAM_ATTEMPT_ACTIVE"

    allowed = check_admission(active_statuses=["failed"] * 100)
    assert allowed.allowed


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

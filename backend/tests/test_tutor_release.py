from uuid import uuid4

import pytest

from app.tutor.release import reviewed_policy


def review():
    return {
        "status": "approved_for_lesson_tutor",
        "workflow_id": str(uuid4()),
        "document_id": str(uuid4()),
        "chunk_hashes": {"SOC-003": "a" * 64},
        "execution_mode": "published_latest_with_response_version_check",
        "cost_basis": "groq_free_full_text_no_rerank",
        "call_bound_usd": "0.001000",
        "observed_at": "2026-10-28",
    }


def test_review_requires_explicit_execution_and_cost_approval():
    assert reviewed_policy(review())["bound"] > 0
    for field, value in (
        ("status", "candidate_not_activated"),
        ("execution_mode", "unchecked_latest"),
        ("cost_basis", "unknown"),
        ("call_bound_usd", "0"),
        ("chunk_hashes", {}),
        ("chunk_hashes", {"SOC-003": "not-a-hash"}),
    ):
        with pytest.raises(ValueError):
            reviewed_policy(review() | {field: value})


def test_grade_requires_separate_approval_for_the_same_workflow():
    with pytest.raises(ValueError):
        reviewed_policy(review(), enable_grade=True)
    combined = review() | {
        "status": "approved_for_tutor_and_grade",
        "grade_mode_verified": True,
        "grade_call_bound_usd": "0.010000",
    }
    assert reviewed_policy(combined, enable_grade=True)["grade"] is True
    assert reviewed_policy(combined, enable_grade=True)["grade_bound"] > 0
    with pytest.raises(ValueError):
        reviewed_policy(combined | {"grade_mode_verified": False}, enable_grade=True)
    with pytest.raises(ValueError):
        reviewed_policy(combined | {"grade_call_bound_usd": "0"}, enable_grade=True)
    with pytest.raises(ValueError):
        without_grade_bound = {
            key: value for key, value in combined.items() if key != "grade_call_bound_usd"
        }
        reviewed_policy(without_grade_bound, enable_grade=True)
    with pytest.raises(ValueError):
        reviewed_policy(combined | {"grade_call_bound_usd": "NaN"}, enable_grade=True)

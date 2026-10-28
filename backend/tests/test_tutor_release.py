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
        ("call_bound_usd", "0.26"),
        ("chunk_hashes", {}),
        ("chunk_hashes", {"SOC-003": "not-a-hash"}),
    ):
        with pytest.raises(ValueError):
            reviewed_policy(review() | {field: value})

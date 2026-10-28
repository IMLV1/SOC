import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.service import AuthError
from app.learning.catalog import LESSON, LEVELS
from app.learning.models import ProgressInput
from app.learning.progress import apply_progress
from app.main import app


def test_published_training_lesson_has_five_ordered_steps_without_exam_material():
    assert len(LESSON["steps"]) == 5
    assert [step["id"] for step in LESSON["steps"]] == [
        "method_path",
        "response",
        "account_ip",
        "timeline",
        "evidence_limits",
    ]
    serialized = str(LESSON).lower()
    for private_term in (
        "answer_key",
        "ground_truth",
        "rubric",
        "passed",
        "initial_severity",
    ):
        assert private_term not in serialized
    assert LEVELS[0]["ordinal"] == 1


def test_learning_catalog_requires_configured_database_not_a_static_fallback():
    with TestClient(app) as client:
        response = client.get("/api/v1/learning-path")
    assert response.status_code == 503
    serialized = response.text.lower()
    for field in ("explanation", "limitation", "ground_truth", "answer_key"):
        assert field not in serialized


def test_progress_mutation_accepts_only_expected_version():
    assert ProgressInput.model_validate({"expected_version": 0}).expected_version == 0
    with pytest.raises(ValidationError):
        ProgressInput.model_validate({"expected_version": 0, "passed": True})
    with pytest.raises(ValidationError):
        ProgressInput.model_validate({"expected_version": -1})


def test_progress_requires_order_and_rejects_stale_new_operations():
    steps = [step["id"] for step in LESSON["steps"]]
    with pytest.raises(AuthError) as order_error:
        apply_progress(
            [],
            completed=False,
            current_version=0,
            expected_version=0,
            step_id=steps[1],
            allowed_steps=steps,
        )
    assert order_error.value.code == "STEP_ORDER_INVALID"
    with pytest.raises(AuthError) as stale_error:
        apply_progress(
            [],
            completed=False,
            current_version=1,
            expected_version=0,
            step_id=steps[0],
            allowed_steps=steps,
        )
    assert stale_error.value.code == "VERSION_CONFLICT"


def test_progress_replay_is_idempotent_and_completion_requires_all_steps():
    steps = [step["id"] for step in LESSON["steps"]]
    assert apply_progress(
        [steps[0]],
        completed=False,
        current_version=1,
        expected_version=0,
        step_id=steps[0],
        allowed_steps=steps,
    ) == ([steps[0]], False)
    with pytest.raises(AuthError) as incomplete_error:
        apply_progress(
            [steps[0]],
            completed=False,
            current_version=1,
            expected_version=1,
            step_id=None,
            allowed_steps=steps,
        )
    assert incomplete_error.value.code == "LESSON_INCOMPLETE"

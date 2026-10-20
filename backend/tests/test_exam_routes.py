from app.exams.models import AttemptData, StartAttemptInput
from app.exams.routes import router
from app.main import app


def test_exam_routes_are_registered_but_remain_draft_in_openapi() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/v1/learning/levels/{level_id}/attempts" in paths
    assert "/api/v1/exam/attempts/active" in paths
    assert "/api/v1/exam/attempts/{attempt_id}/submit" in paths
    assert "/api/v1/admin/exam-attempts/{attempt_id}/review" in paths
    assert not any("exam" in path for path in app.openapi()["paths"])


def test_exam_start_rejects_client_selected_case_and_role() -> None:
    try:
        StartAttemptInput.model_validate(
            {"expected_progress_version": 1, "case_id": "client-choice", "role": "instructor"}
        )
    except ValueError:
        return
    raise AssertionError("Exam admission must reject client-controlled case and role fields")


def test_learner_attempt_projection_has_no_truth_or_case_identity() -> None:
    assert set(AttemptData.model_fields) == {
        "id",
        "run_id",
        "level_id",
        "status",
        "version",
        "started_at",
        "expires_at",
        "submitted_at",
        "events",
        "answer",
    }

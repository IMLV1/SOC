"""Offline validation only: these content fixtures never seed account state."""

import json
from pathlib import Path
from uuid import UUID

from app.learning.catalog import LESSON
from app.learning.models import LessonView

CURRICULUM = Path(__file__).resolve().parents[1] / "fixtures/learning/curriculum-v1.json"


def load_curriculum():
    # Detect duplicate object keys instead of silently keeping the last value.
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, f"Duplicate JSON key: {key}"
            result[key] = value
        return result

    return json.loads(CURRICULUM.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)


def test_curriculum_covers_three_ordered_levels_with_valid_lesson_content():
    curriculum = load_curriculum()
    assert curriculum["schema_version"] == 1
    assert curriculum["purpose"] == "training"
    assert curriculum["content_status"] == "draft_for_testing"
    levels = curriculum["levels"]
    assert [level["ordinal"] for level in levels] == [1, 2, 3]
    assert [level["title"] for level in levels] == ["เริ่มต้น", "กลาง", "ชำนาญ"]
    assert len({UUID(level["id"]) for level in levels}) == 3
    lesson_ids = set()
    for level in levels:
        assert level["objective"].strip()
        assert len(level["lessons"]) == 3
        for raw_lesson in level["lessons"]:
            lesson = LessonView.model_validate(raw_lesson)
            assert lesson.level_id == UUID(level["id"])
            assert lesson.id not in lesson_ids
            lesson_ids.add(lesson.id)
            assert lesson.version == 1
            assert len(lesson.steps) == 5
            assert len({step.id for step in lesson.steps}) == len(lesson.steps)
            for step in lesson.steps:
                for value in (step.id, step.title, step.target, step.explanation, step.limitation):
                    assert value.strip()
    assert len(lesson_ids) == 9


def test_existing_published_starter_lesson_is_preserved_verbatim():
    starter = load_curriculum()["levels"][0]["lessons"][0]
    assert starter == LESSON


def test_training_content_contains_no_exam_bank_or_authoritative_account_state():
    forbidden_keys = {
        "answer_key",
        "ground_truth",
        "expected_evidence_keys",
        "expected_severity",
        "expected_disposition",
        "criterion_guidance",
        "score",
        "passed",
        "unlocked",
        "owner_user_id",
        "password",
        "api_key",
    }

    def check(value):
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for nested in value.values():
                check(nested)
        elif isinstance(value, list):
            for nested in value:
                check(nested)

    curriculum = load_curriculum()
    check(curriculum)
    serialized = json.dumps(curriculum)
    assert "624f6eda-9044-48ea-8ee8-91fdf1e500" not in serialized
    assert "sess-38f2" not in serialized


def test_higher_levels_teach_limitations_and_human_review_not_automatic_passing():
    levels = load_curriculum()["levels"]
    middle_steps = {step["id"] for lesson in levels[1]["lessons"] for step in lesson["steps"]}
    advanced_steps = {step["id"] for lesson in levels[2]["lessons"] for step in lesson["steps"]}
    assert {"session_link", "change_record", "scope_mismatch", "ai_status"} <= middle_steps
    assert {
        "baseline_scope",
        "independent_evidence",
        "safe_unknown",
        "safe_untrusted_text",
        "evidence_vs_knowledge",
        "check_citations",
        "review_feedback",
    } <= advanced_steps

from app.grading.rubric import FOUNDATIONS_RUBRIC, RUBRIC_VERSION, score_rubric


def test_rubric_pass_requires_threshold_and_every_critical_criterion():
    passed = score_rubric({"evidence": 2, "analysis": 2, "classification": 1, "reasoning": 1})
    assert (passed.status, passed.score, passed.rubric_version) == (
        "passed",
        6,
        RUBRIC_VERSION,
    )

    critical_miss = score_rubric(
        {"evidence": 0, "analysis": 2, "classification": 2, "reasoning": 2}
    )
    assert critical_miss.status == "failed"
    assert critical_miss.score == 6


def test_incomplete_or_unrecognized_grading_is_needs_review():
    incomplete = score_rubric({"evidence": 2, "analysis": None, "classification": 2})
    extra = score_rubric(
        {"evidence": 2, "analysis": 2, "classification": 2, "reasoning": 2, "passed": 1}
    )
    invalid = score_rubric({"evidence": True, "analysis": 2, "classification": 2, "reasoning": 2})
    for grade in (incomplete, extra, invalid):
        assert grade.status == "needs_review"
        assert grade.score is None


def test_rubric_policy_is_versioned_and_private_decision_stays_out_of_payload():
    assert FOUNDATIONS_RUBRIC.version == "soc-foundations-v1"
    assert FOUNDATIONS_RUBRIC.pass_score == 6
    assert len(FOUNDATIONS_RUBRIC.criteria) == 4

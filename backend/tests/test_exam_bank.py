from app.exams.seed import load_bank


def test_exam_bank_is_separate_and_truth_is_not_in_blind_fixtures():
    bank = load_bank()
    assert len(bank) == 3
    for case, fixture, truth in bank:
        assert case.purpose == fixture.purpose == "exam"
        assert case.title == "Investigation case"
        assert set(truth.expected_evidence_keys) <= {event.key for event in fixture.events}
        assert truth.criterion_guidance
        assert "ground-truth" not in str(case.model_dump()).lower()
        assert "expected_evidence" not in str(fixture.model_dump()).lower()

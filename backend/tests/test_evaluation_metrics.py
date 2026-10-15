from uuid import uuid4

import pytest

from app.evaluation.metrics import Candidate, Incident, metrics


def test_duplicates_deleted_and_undetermined_do_not_change_denominator():
    threat, benign = uuid4(), uuid4()
    incidents = [
        Incident("a", True, frozenset([threat])),
        Incident("b", False, frozenset([benign])),
    ]
    candidates = [
        Candidate(frozenset([threat]), "undetermined", True),
        Candidate(frozenset([threat])),
        Candidate(frozenset([benign]), "false_positive"),
    ]
    result = metrics(incidents, candidates, frozenset([threat, benign]))
    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 1, 0, 0)
    assert result["precision"] == 0.5 and result["recall"] == 1
    assert result["undetermined_groups"] == 1


def test_zero_denominators_are_null_and_truncation_preserves_groups():
    event = uuid4()
    result = metrics([Incident("a", False, frozenset([event]))], [], frozenset())
    assert result["precision"] is None and result["recall"] is None
    assert result["tn"] == 1 and result["incomplete_groups"] == 1


def test_out_of_snapshot_candidate_and_duplicate_group_are_rejected():
    event = uuid4()
    incident = Incident("a", True, frozenset([event]))
    with pytest.raises(ValueError, match="snapshot"):
        metrics([incident], [Candidate(frozenset([event]))], frozenset())
    with pytest.raises(ValueError, match="Duplicate"):
        metrics([incident, incident], [], frozenset([event]))

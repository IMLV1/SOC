"""Human-review gating must not convert drafts or missing claims into acceptance."""

from copy import deepcopy

import pytest

from app.knowledge.review import assess, packet


def fixture_report():
    return {
        "cases": [{"query": "authentication", "language": lang} for lang in ("en", "th")],
        "context_catalog": [
            {
                "retrieval_item_id": "source-1",
                "document_title": "auth",
                "excerpt": "A session is not proof of data access.",
            }
        ],
        "records": [
            {
                "split": "held-v1",
                "index": i,
                "language": lang,
                "arm": arm,
                "operation": f"{i}:{arm}",
                "status": "succeeded",
                "retrieved": ["auth"],
                "result": {
                    "claims": [
                        {
                            "text": "A session is not proof of data access.",
                            "knowledge_refs": ["source-1"],
                            "evidence_refs": [],
                        }
                    ]
                },
            }
            for i, lang in enumerate(("en", "th"))
            for arm in ("no_rag", "rag")
        ],
    }


def completed_fixture_review(report):
    review = packet(report)
    review.update(reviewer="test-reviewer", independent_of_implementation=True)
    for label in review["labels"]:
        label.update(
            approved=True,
            answerable=True,
            relevant_source_ids=["source-1"],
            expected_evidence_ids=[],
            forbidden_claims=["successful data access"],
            reason="test relevance decision",
        )
    for claim in review["claims"]:
        claim.update(supported=True, reason="test support decision")
    return review


def test_review_requires_independent_labels_and_keeps_unsupported_claims_in_denominator():
    report = fixture_report()
    draft = packet(report)
    assert assess(report, draft)["status"] == "pending_review"
    review = completed_fixture_review(report)
    assert assess(report, review)["status"] == "passed"
    next(c for c in review["claims"] if c["language"] == "th" and c["arm"] == "rag")[
        "supported"
    ] = False
    result = assess(report, review)
    assert result["status"] == "failed"
    assert result["metrics"]["th"]["grounding"]["rag"]["supported_rate"] == 0
    review["claims"][0]["supported"] = None
    assert assess(report, review)["status"] == "pending_review"


def test_review_rejects_stale_artifact_changed_context_and_omitted_sample():
    report = fixture_report()
    review = completed_fixture_review(report)
    for mutate in (
        lambda r: r.update(artifact_sha256="other"),
        lambda r: r["sources"][0].update(excerpt="changed"),
        lambda r: r["claims"].pop(),
        lambda r: r["claims"][0]["claim"].update(text="changed"),
        lambda r: r["labels"][0].update(relevant_source_ids=["cross-release"]),
        lambda r: r["labels"][0].update(relevant_source_ids=["source-1", "source-1"]),
        lambda r: r["labels"][1].update(index=0),
    ):
        changed = deepcopy(review)
        mutate(changed)
        with pytest.raises(ValueError):
            assess(report, changed)


def test_retrieval_review_uses_human_chunk_labels_and_requires_full_sample():
    from app.knowledge.review import assess_retrieval, retrieval_packet

    report = {
        "context_catalog": [{"chunk_id": "chunk-1", "body": "approved context"}],
        "records": [
            {"id": lang, "language": lang, "query": "query", "retrieved": [{"chunk_id": "chunk-1"}]}
            for lang in ("en", "th")
        ],
    }
    review = retrieval_packet(report)
    assert assess_retrieval(report, review)["status"] == "pending_review"
    review.update(reviewer="test-reviewer", independent_of_implementation=True)
    for label in review["labels"]:
        label.update(
            approved=True,
            answerable=True,
            relevant_chunk_ids=["chunk-1"],
            expected_evidence_ids=[],
            forbidden_claims=["invented event"],
            reason="test",
        )
    assert assess_retrieval(report, review)["status"] == "passed"
    changed = deepcopy(review)
    changed["labels"][0]["relevant_chunk_ids"] = ["other-release"]
    with pytest.raises(ValueError, match="Unknown"):
        assess_retrieval(report, changed)
    changed = deepcopy(review)
    changed["labels"].pop()
    with pytest.raises(ValueError, match="omitted"):
        assess_retrieval(report, changed)
    report["records"][1]["retrieved"] = []
    changed = retrieval_packet(report)
    changed.update(reviewer="test-reviewer", independent_of_implementation=True)
    for label in changed["labels"]:
        label.update(
            approved=True,
            answerable=True,
            relevant_chunk_ids=["chunk-1"],
            expected_evidence_ids=[],
            forbidden_claims=["invented event"],
            reason="test",
        )
    result = assess_retrieval(report, changed)
    assert result["status"] == "failed" and result["metrics"]["th"]["recall_at_5"] == 0


def test_bilingual_calibration_and_fresh_heldout_are_disjoint():
    import json
    from pathlib import Path

    from rag_benchmark import HELD

    root = Path(__file__).parent
    calibration = json.loads((root / "knowledge_calibration_v2.json").read_text(encoding="utf-8"))
    heldout = json.loads((root / "knowledge_heldout_v2.json").read_text(encoding="utf-8"))
    calibration_queries = {c["query"].casefold().strip() for c in calibration["calibration"]}
    old_queries = {c["query"].casefold().strip() for c in HELD}
    queries = [c["query"].casefold().strip() for c in heldout["cases"]]
    assert len(queries) == len(set(queries)) == 50
    assert not set(queries).intersection(calibration_queries | old_queries)
    assert not calibration_queries.intersection(old_queries)
    for lang in ("en", "th"):
        cases = [c for c in heldout["cases"] if c["language"] == lang]
        assert len(cases) == 25 and sum(c["expected"] is None for c in cases) == 5
        assert all(c["human_reviewed"] is False for c in cases)

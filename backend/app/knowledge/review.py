"""Offline human review packet. No provider calls and no automatic human scores."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def fingerprint(report: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def packet(report: dict[str, Any]) -> dict[str, Any]:
    labels = [
        {
            "index": i,
            "language": case["language"],
            "query": case["query"],
            "approved": False,
            "relevant_source_ids": None,
            "answerable": None,
            "expected_evidence_ids": None,
            "forbidden_claims": None,
            "reason": "",
        }
        for i, case in enumerate(report["cases"])
    ]
    records = [r for r in report["records"] if r["split"] == "held-v1"]
    claims = []
    for language in ("en", "th"):
        for arm in ("no_rag", "rag"):
            candidates = [
                r
                for r in records
                if r["language"] == language
                and r["arm"] == arm
                and r["status"] == "succeeded"
                and (r.get("result") or {}).get("claims")
            ]
            # Fixed sample before review; no picking only favorable claims.
            selected = sorted(
                candidates, key=lambda r: hashlib.sha256(r["operation"].encode()).hexdigest()
            )[:10]
            for record in selected:
                for index, claim in enumerate(record["result"]["claims"]):
                    claims.append(
                        {
                            "operation": record["operation"],
                            "claim_index": index,
                            "language": language,
                            "arm": arm,
                            "claim": claim,
                            "supported": None,
                            "reason": "",
                        }
                    )
    evidence = report.get("evidence_catalog", [])
    if report.get("benchmark_schema") == "question-v1-before-omission-metadata":
        # Exact synthetic event frozen in tests/rag_benchmark.py, not model output.
        evidence = [
            {
                "id": str(uuid5(NAMESPACE_URL, "rag14:blocked-event")),
                "source": "web",
                "request": {"method": "GET", "path": "/restricted"},
                "response": {"status": 403},
                "log": {"event_type": "request_policy_denied"},
            }
        ]
    return {
        "evidence_context": evidence,
        "artifact_sha256": fingerprint(report),
        "reviewer": "",
        "independent_of_implementation": False,
        "source_id_kind": "frozen retrieval item ID; historical pilot lacks original chunk IDs",
        "sources": report["context_catalog"],
        "labels": labels,
        "claims": claims,
    }


def assess(report: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    expected = packet(report)
    if review.get("artifact_sha256") != expected["artifact_sha256"]:
        raise ValueError("Review artifact hash mismatch")
    if review.get("sources") != expected["sources"]:
        raise ValueError("Review source context changed")
    if review.get("evidence_context") != expected["evidence_context"]:
        raise ValueError("Review event context changed")
    labels, claims = review.get("labels", []), review.get("claims", [])
    if len(labels) != len(expected["labels"]) or len(claims) != len(expected["claims"]):
        raise ValueError("Review omitted cases or sampled claims")
    known_sources = {c["retrieval_item_id"] for c in expected["sources"]}
    pending = not (
        str(review.get("reviewer", "")).strip()
        and review.get("independent_of_implementation") is True
    )
    for label, original in zip(labels, expected["labels"], strict=True):
        if any(label.get(k) != original[k] for k in ("index", "language", "query")):
            raise ValueError("Review case identity changed")
        relevant = label.get("relevant_source_ids")
        if relevant is not None and (
            not isinstance(relevant, list)
            or not set(relevant) <= known_sources
            or len(relevant) != len(set(relevant))
        ):
            raise ValueError("Unknown or duplicate relevance source")
        if label.get("approved") is not True or type(label.get("answerable")) is not bool:
            pending = True
        elif relevant is None or bool(relevant) != label["answerable"]:
            raise ValueError("Answerability/relevance disagreement")
        if label.get("expected_evidence_ids") is None or label.get("forbidden_claims") is None:
            pending = True
        if not str(label.get("reason", "")).strip():
            pending = True
    for claim, original in zip(claims, expected["claims"], strict=True):
        if any(
            claim.get(k) != original[k]
            for k in ("operation", "claim_index", "language", "arm", "claim")
        ):
            raise ValueError("Sampled claim identity changed")
        if type(claim.get("supported")) is not bool or not str(claim.get("reason", "")).strip():
            pending = True
    metrics: dict[str, Any] = {}
    source_by_key = {c["document_title"]: c["retrieval_item_id"] for c in expected["sources"]}
    for language in ("en", "th"):
        reviewed = [
            label
            for label in labels
            if label["language"] == language
            and label.get("approved") is True
            and label.get("answerable") is True
            and label.get("relevant_source_ids")
        ]
        recalls, reciprocal = [], []
        for label in reviewed:
            record = next(
                (
                    r
                    for r in report["records"]
                    if r["split"] == "held-v1"
                    and r["index"] == label["index"]
                    and r["arm"] == "rag"
                ),
                None,
            )
            if record is None:
                raise ValueError("Missing retrieval outcome")
            retrieved = [source_by_key[key] for key in record["retrieved"][:5]]
            relevant = set(label["relevant_source_ids"])
            recalls.append(len(relevant.intersection(retrieved)) / len(relevant))
            reciprocal.append(
                next(
                    (1 / rank for rank, source in enumerate(retrieved, 1) if source in relevant), 0
                )
            )
        grounded = {}
        for arm in ("no_rag", "rag"):
            sample = [
                c
                for c in claims
                if c["language"] == language
                and c["arm"] == arm
                and type(c.get("supported")) is bool
            ]
            grounded[arm] = {
                "sample_count": len(sample),
                "supported_rate": sum(c["supported"] for c in sample) / len(sample)
                if sample
                else None,
            }
        metrics[language] = {
            "reviewed_answerable_queries": len(reviewed),
            "recall_at_5": sum(recalls) / len(recalls) if recalls else None,
            "mrr": sum(reciprocal) / len(reciprocal) if reciprocal else None,
            "grounding": grounded,
        }
    passes = not pending and all(
        m["recall_at_5"] is not None
        and m["recall_at_5"] >= 0.85
        and m["grounding"]["rag"]["supported_rate"] is not None
        and m["grounding"]["rag"]["supported_rate"] >= 0.9
        for m in metrics.values()
    )
    return {
        "status": "pending_review" if pending else "passed" if passes else "failed",
        "artifact_sha256": expected["artifact_sha256"],
        "metrics": metrics,
        "scope": "human relevance/grounding only; not budget, leakage or CI acceptance",
    }


def retrieval_packet(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_sha256": fingerprint(report),
        "reviewer": "",
        "independent_of_implementation": False,
        "sources": report["context_catalog"],
        "labels": [
            {
                "id": r["id"],
                "query": r["query"],
                "language": r["language"],
                "approved": False,
                "answerable": None,
                "relevant_chunk_ids": None,
                "expected_evidence_ids": None,
                "forbidden_claims": None,
                "reason": "",
            }
            for r in report["records"]
        ],
    }


def assess_retrieval(report: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    expected = retrieval_packet(report)
    if review.get("artifact_sha256") != expected["artifact_sha256"]:
        raise ValueError("Review artifact hash mismatch")
    if review.get("sources") != expected["sources"]:
        raise ValueError("Review source context changed")
    labels = review.get("labels", [])
    if len(labels) != len(expected["labels"]):
        raise ValueError("Review omitted cases")
    known = {str(c["chunk_id"]) for c in expected["sources"]}
    pending = not (
        str(review.get("reviewer", "")).strip()
        and review.get("independent_of_implementation") is True
    )
    metrics = {}
    for label, original in zip(labels, expected["labels"], strict=True):
        if any(label.get(k) != original[k] for k in ("id", "language", "query")):
            raise ValueError("Review case identity changed")
        relevant = label.get("relevant_chunk_ids")
        if relevant is not None and (
            not isinstance(relevant, list)
            or not set(relevant) <= known
            or len(relevant) != len(set(relevant))
        ):
            raise ValueError("Unknown or duplicate relevance chunk")
        if label.get("approved") is not True or type(label.get("answerable")) is not bool:
            pending = True
        elif relevant is None or bool(relevant) != label["answerable"]:
            raise ValueError("Answerability/relevance disagreement")
        if (
            label.get("expected_evidence_ids") is None
            or label.get("forbidden_claims") is None
            or not str(label.get("reason", "")).strip()
        ):
            pending = True
    for language in ("en", "th"):
        recalls, reciprocal = [], []
        for label, record in zip(labels, report["records"], strict=True):
            relevant = label.get("relevant_chunk_ids")
            if label["language"] != language or label.get("approved") is not True or not relevant:
                continue
            retrieved = [r["chunk_id"] for r in record["retrieved"][:5]]
            recalls.append(len(set(relevant).intersection(retrieved)) / len(relevant))
            reciprocal.append(next((1 / i for i, c in enumerate(retrieved, 1) if c in relevant), 0))
        metrics[language] = {
            "sample_count": len(recalls),
            "recall_at_5": sum(recalls) / len(recalls) if recalls else None,
            "mrr": sum(reciprocal) / len(reciprocal) if reciprocal else None,
        }
    passed = not pending and all(
        m["recall_at_5"] is not None and m["recall_at_5"] >= 0.85 for m in metrics.values()
    )
    return {
        "status": "pending_review" if pending else "passed" if passed else "failed",
        "artifact_sha256": expected["artifact_sha256"],
        "metrics": metrics,
        "scope": "retrieval relevance only, not answer grounding or full step acceptance",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["packet", "assess", "retrieval-packet", "assess-retrieval"]
    )
    parser.add_argument("artifact", type=Path)
    parser.add_argument("review", type=Path)
    args = parser.parse_args()
    report = json.loads(args.artifact.read_text(encoding="utf-8"))
    if args.command in {"packet", "retrieval-packet"}:
        if args.review.exists():
            raise ValueError("Refusing to overwrite an existing review")
        args.review.write_text(
            json.dumps(
                retrieval_packet(report) if args.command == "retrieval-packet" else packet(report),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("Review packet created; no review decisions supplied.")
        return 0
    review = json.loads(args.review.read_text(encoding="utf-8"))
    result = (
        assess_retrieval(report, review)
        if args.command == "assess-retrieval"
        else assess(report, review)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2 if result["status"] == "pending_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())

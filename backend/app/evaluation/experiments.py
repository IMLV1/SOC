"""Deterministic detector comparison over one frozen event/truth dataset."""

from typing import Any
from uuid import UUID

from app.detection.policy import (
    evaluate_pinned,
)
from app.detection.policy_v1 import evaluate as evaluate_v1
from app.evaluation.metrics import Candidate, Incident, metrics


def compare(
    events: list[dict[str, Any]], truths: list[dict[str, Any]], versions: dict[str, str]
) -> dict[str, Any]:
    """Run both shipped detectors; C remains unavailable until its provider is approved."""
    released = frozenset(UUID(str(row["id"])) for row in events)
    incidents: list[Incident] = []
    for truth in truths:
        keys = set(truth["expected_evidence_keys"])
        refs = frozenset(
            UUID(str(row["id"]))
            for row in events
            if row["scenario_instance_id"] == truth["scenario_instance_id"]
            and row["fixture_event_key"] in keys
        )
        incidents.append(
            Incident(
                f"{truth['scenario_instance_id']}:{truth['incident_key']}",
                bool(truth["threat_label"]),
                refs or frozenset({UUID(int=0)}),
            )
        )

    output: dict[str, Any] = {}
    for arm, findings in (
        ("A", evaluate_v1(events)),
        (
            "B",
            evaluate_pinned(
                events,
                versions["rule_version"],
                versions["baseline_version"],
                versions["correlation_version"],
            ),
        ),
    ):
        candidates = [Candidate(frozenset(f.evidence_ids)) for f in findings]
        arm_metrics = (
            metrics(incidents, candidates, released)
            if incidents
            else {
                "unit": "incident_group",
                "tp": 0,
                "fp": 0,
                "fn": 0,
                "tn": 0,
                "precision": None,
                "recall": None,
                "precision_null_reason": "NO_POSITIVE_CANDIDATES",
                "recall_null_reason": "NO_THREAT_GROUPS",
                "incomplete_groups": 0,
                "undetermined_groups": 0,
                "unmatched_candidates": len(candidates),
            }
        )
        output[arm] = {
            "status": "completed",
            "metrics": arm_metrics,
            "findings": [
                {
                    "detector_type": f.detector_type,
                    "version": f.detector_version,
                    "correlation_key": f.correlation_key,
                    "title": f.title,
                    "severity": f.severity,
                    "explanation": f.explanation,
                    "evidence_ids": [str(v) for v in f.evidence_ids],
                }
                for f in findings
            ],
        }
    output["C"] = {
        "status": "unavailable",
        "metrics": None,
        "findings": [],
        "error_code": "REAL_EXPERIMENT_PROVIDER_NOT_APPROVED",
    }
    return output

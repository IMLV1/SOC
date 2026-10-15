"""Incident-group metrics from frozen, scoped evidence; never count requests as incidents."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Incident:
    key: str
    threat: bool
    evidence: frozenset[UUID]


@dataclass(frozen=True)
class Candidate:
    evidence: frozenset[UUID]
    disposition: str | None = None
    deleted: bool = False


def metrics(
    incidents: list[Incident], candidates: list[Candidate], released: frozenset[UUID]
) -> dict[str, object]:
    if len({item.key for item in incidents}) != len(incidents):
        raise ValueError("Duplicate incident group")
    if any(not item.evidence for item in incidents):
        raise ValueError("Incident evidence required")
    if any(not item.evidence or not item.evidence <= released for item in candidates):
        raise ValueError("Candidate evidence outside frozen snapshot")
    tp = fp = fn = tn = incomplete = undetermined = 0
    for incident in incidents:
        if not incident.evidence <= released:
            incomplete += 1
        # A candidate is positive even when deleted or classified undetermined.
        # Duplicate revisions and overlapping tickets cannot multiply a group.
        matched = [item for item in candidates if item.evidence & incident.evidence]
        positive = bool(matched)
        if incident.threat:
            tp += positive
            fn += not positive
        else:
            fp += positive
            tn += not positive
        undetermined += any(item.disposition == "undetermined" for item in matched)
    return {
        "unit": "incident_group",
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "precision_null_reason": None if tp + fp else "NO_POSITIVE_CANDIDATES",
        "recall_null_reason": None if tp + fn else "NO_THREAT_GROUPS",
        "incomplete_groups": incomplete,
        "undetermined_groups": undetermined,
        "unmatched_candidates": sum(
            not any(item.evidence & incident.evidence for incident in incidents)
            for item in candidates
        ),
    }

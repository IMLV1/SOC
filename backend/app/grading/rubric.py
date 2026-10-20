"""Deterministic rubric policy, separate from provider-generated suggestions."""

from dataclasses import dataclass
from typing import Literal

RUBRIC_VERSION = "soc-foundations-v1"
MAX_SCORE_PER_CRITERION = 2
PASS_SCORE = 6


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str
    critical: bool


@dataclass(frozen=True)
class Rubric:
    version: str
    criteria: tuple[Criterion, ...]
    pass_score: int


@dataclass(frozen=True)
class Grade:
    status: Literal["passed", "failed", "needs_review"]
    score: int | None
    maximum: int
    rubric_version: str
    source: Literal["deterministic"]


FOUNDATIONS_RUBRIC = Rubric(
    version=RUBRIC_VERSION,
    criteria=(
        Criterion("evidence", "Evidence selection and linkage", critical=True),
        Criterion("analysis", "Conclusion supported by evidence", critical=True),
        Criterion("classification", "Severity and disposition", critical=False),
        Criterion("reasoning", "Clear, evidence-linked reasoning", critical=False),
    ),
    pass_score=PASS_SCORE,
)


def score_rubric(scores: dict[str, int | None], rubric: Rubric = FOUNDATIONS_RUBRIC) -> Grade:
    """Score a complete criterion map; missing/invalid values must be reviewed.

    This function does not inspect private case truth or learner prose. Its caller
    must validate evidence references and obtain authorized criterion results.
    AI suggestions are never a trusted input to this deterministic policy.
    """
    expected = {criterion.key for criterion in rubric.criteria}
    maximum = len(rubric.criteria) * MAX_SCORE_PER_CRITERION
    if set(scores) != expected or any(
        value is None or type(value) is not int or not 0 <= value <= MAX_SCORE_PER_CRITERION
        for value in scores.values()
    ):
        return Grade("needs_review", None, maximum, rubric.version, "deterministic")

    complete_scores = {key: value for key, value in scores.items() if value is not None}
    total = sum(complete_scores.values())
    critical_met = all(complete_scores[item.key] >= 1 for item in rubric.criteria if item.critical)
    status: Literal["passed", "failed"] = (
        "passed" if total >= rubric.pass_score and critical_met else "failed"
    )
    return Grade(status, total, maximum, rubric.version, "deterministic")

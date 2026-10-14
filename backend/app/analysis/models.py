from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.auth.models import AuthMeta, PageMeta, Strict


class Hypothesis(Strict):
    text: str = Field(min_length=1)
    evidence_refs: list[UUID]


class SeveritySuggestion(Strict):
    level: Literal["low", "medium", "high", "critical"]
    reason: str = Field(min_length=1)


class Confidence(Strict):
    level: Literal["low", "medium", "high"]
    reason: str = Field(min_length=1)


class AnalysisResult(Strict):
    summary: str = Field(min_length=1)
    hypotheses: list[Hypothesis]
    evidence_refs: list[UUID]
    observed_impact: str
    potential_impact: str
    suggested_severity: SeveritySuggestion
    confidence: Confidence
    unknowns: list[str]
    recommended_checks: list[str]


class AnalysisView(Strict):
    id: UUID
    run_id: UUID
    retry_of: UUID | None
    mode: Literal["mock"]
    model_id: str
    prompt_version: str
    status: Literal[
        "queued",
        "running",
        "succeeded",
        "failed",
        "invalid_output",
        "quota_exceeded",
        "timed_out",
        "cancelled",
    ]
    version: int
    evidence_ids: list[UUID]
    result: AnalysisResult | None
    error_code: str | None
    usage: dict[str, Any] | None
    created_at: datetime
    finished_at: datetime | None


class AnalysisEnvelope(Strict):
    data: AnalysisView
    meta: AuthMeta


class AnalysisList(Strict):
    data: list[AnalysisView]
    meta: PageMeta


class RetryInput(Strict):
    expected_version: int = Field(ge=1)

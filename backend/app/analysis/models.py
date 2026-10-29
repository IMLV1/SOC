from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, StrictInt

from app.auth.models import AuthMeta, PageMeta, Strict
from app.input_validation import InputModel, NonBlankText


class Hypothesis(Strict):
    text: str = Field(min_length=1)
    evidence_refs: list[UUID]


class SeveritySuggestion(Strict):
    level: Literal["low", "medium", "high", "critical"]
    reason: str = Field(min_length=1)


class Confidence(Strict):
    level: Literal["low", "medium", "high"]
    reason: str = Field(min_length=1)


class Claim(Strict):
    text: str = Field(min_length=1, max_length=2000)
    kind: Literal["observation", "guidance"]
    evidence_refs: list[UUID]
    knowledge_refs: list[UUID]


class QuestionResult(Strict):
    answer: str = Field(min_length=1, max_length=6000)
    claims: list[Claim] = Field(max_length=20)
    unknowns: list[str]
    answer_status: Literal["answered", "insufficient_context"]
    evidence_truncated: bool = False
    omitted_evidence_ids: list[UUID] = Field(default_factory=list)


class SourceView(Strict):
    retrieval_item_id: UUID
    document_title: str
    document_version: str
    heading: str
    excerpt: str
    content_hash: str


class SourceEnvelope(Strict):
    data: SourceView
    meta: AuthMeta


class RetrievalView(Strict):
    status: Literal["matched", "no_match", "unavailable", "revoked"]
    release_id: UUID
    config_version: str
    citations: list[SourceView]


class QuestionInput(InputModel):
    question: NonBlankText = Field(min_length=1, max_length=2000)
    expected_version: StrictInt = Field(ge=1)


class AnalysisResult(Strict):
    knowledge_refs: list[UUID] = Field(default_factory=list)
    evidence_truncated: bool = False
    omitted_evidence_ids: list[UUID] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    hypotheses: list[Hypothesis]
    evidence_refs: list[UUID]
    observed_impact: str
    potential_impact: str
    suggested_severity: SeveritySuggestion
    confidence: Confidence
    unknowns: list[str]
    recommended_checks: list[str]


class ProviderUsage(Strict):
    mode: Literal["mock", "real"]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    pricing_tier: Literal["mock", "free"]


class ProviderResponseError(ValueError):
    """Safe output-validation error retaining provider-reported usage metadata."""

    def __init__(self, code: str, usage: ProviderUsage) -> None:
        super().__init__(code)
        self.usage = usage


class ProviderOutput(Strict):
    result: AnalysisResult
    usage: ProviderUsage


class AnalysisView(Strict):
    id: UUID
    run_id: UUID
    retry_of: UUID | None
    mode: Literal["mock", "real"]
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
    kind: Literal["triage", "question"] = "triage"
    question_text: str | None = None
    response_visibility: Literal["visible", "withdrawn"] = "visible"
    retrieval: RetrievalView | None = None
    result: AnalysisResult | QuestionResult | None
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


class RetryInput(InputModel):
    expected_version: StrictInt = Field(ge=1)

"""Dify adapter for released training evidence; output stays advisory."""

import hashlib
import json
import re
from typing import Any

from app.analysis.models import AnalysisResult, ProviderOutput, ProviderUsage
from app.analysis.provider import AnalysisInput, validate_citations
from app.knowledge.dify_client import DifyConfig
from app.knowledge.dify_workflow import run_workflow
from app.knowledge.generation import redact
from app.tutor.service import SECTION, answer_without_reasoning, redact_question


def validate_analysis_outputs(
    outputs: dict[str, Any], data: AnalysisInput, policy: dict[str, Any]
) -> AnalysisResult:
    raw, sources = outputs.get("answer"), outputs.get("sources")
    if not isinstance(raw, str) or not 1 <= len(raw) <= 12000:
        raise ValueError("Invalid analysis output")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 5:
        raise ValueError("Analysis sources required")
    sections: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("metadata"), dict):
            raise ValueError("Invalid analysis source")
        content = source.get("content")
        if (
            source["metadata"].get("document_id") not in policy["document_ids"]
            or not isinstance(content, str)
            or hashlib.sha256(content.encode()).hexdigest() not in policy["chunk_hashes"]
        ):
            raise ValueError("Unapproved analysis source")
        sections.update(SECTION.findall(content))
    parsed = json.loads(answer_without_reasoning(raw))
    result = AnalysisResult.model_validate(parsed)
    if result.knowledge_refs:
        raise ValueError("Dify sources are not local knowledge UUIDs")
    validate_citations(result, {item.id for item in data.evidence})
    # Reject invented manual headings anywhere in the advisory result.
    cited = set(SECTION.findall(json.dumps(parsed, ensure_ascii=False)))
    if not cited.issubset(sections):
        raise ValueError("Unapproved analysis citation")
    if re.search(r"</?think\b", raw, re.IGNORECASE):
        raise ValueError("Reasoning leaked")
    return result


class DifyAnalysisProvider:
    mode = "real"

    def __init__(self, policy: dict[str, Any]) -> None:
        self.policy = policy

    async def analyze(self, data: AnalysisInput) -> ProviderOutput:
        evidence = redact(data.model_dump(mode="json")["evidence"])

        # Redact each field before serialization so JSON escaping cannot bypass redaction.
        def clean(value: Any) -> Any:
            if isinstance(value, str):
                return redact_question(value)
            if isinstance(value, list):
                return [clean(item) for item in value]
            if isinstance(value, dict):
                return {key: clean(item) for key, item in value.items()}
            return value

        question = json.dumps(
            {"evidence": clean(evidence)}, ensure_ascii=False, separators=(",", ":")
        )
        reply = await run_workflow(
            DifyConfig.from_env(),
            self.policy["workflow_id"],
            question,
            f"analysis-{data.analysis_id}",
            mode="analyze",
        )
        result = validate_analysis_outputs(reply.outputs, data, self.policy)
        tokens = reply.total_tokens or 0
        return ProviderOutput(
            result=result,
            usage=ProviderUsage(
                mode="real",
                input_tokens=0,
                output_tokens=0,
                total_tokens=tokens,
                pricing_tier="free",
            ),
        )

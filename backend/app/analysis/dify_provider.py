"""Strict investigation transport; runtime requires explicit operator release review.

This app uses a separate Workflow/key from the lesson Tutor. Callers must reserve
logical quota and a verified cost ceiling before invoking it. No retries or tools.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import requests
from pydantic import ValidationError

from app.analysis.models import AnalysisResult, ProviderOutput, ProviderUsage
from app.analysis.provider import AnalysisInput, validate_citations
from app.knowledge.dify_client import DifyConfig, DifyUnavailable
from app.knowledge.dify_workflow import parse_workflow
from app.knowledge.generation import redact

MAX_REQUEST_BYTES = 32000
MAX_RESPONSE_BYTES = 128000
CONTRACT_VERSION = "soc-investigation-v1"


@dataclass(frozen=True)
class DifyAnalysisReply:
    result: AnalysisResult
    total_tokens: int | None
    run_id: str


class DifyAnalysisFailure(DifyUnavailable):
    """Safe error retaining known aggregate usage, never inventing a token split."""

    def __init__(self, code: str, total_tokens: int | None = None) -> None:
        super().__init__(code)
        self.total_tokens = total_tokens


def redact_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: redact_evidence(item)
            for key, item in value.items()
            if key.lower().replace("-", "_")
            not in {
                "username",
                "src_ip",
                "ip",
                "email",
                "password",
                "token",
                "authorization",
                "cookie",
                "set_cookie",
                "api_key",
                "secret",
                "access_token",
                "refresh_token",
            }
        }
    if isinstance(value, list):
        return [redact_evidence(item) for item in value]
    if isinstance(value, str):
        value = str(redact(value))
        value = re.sub(r"\b(?:app-|sb_secret_|AIza)[A-Za-z0-9_-]{16,}", "[redacted-key]", value)
        value = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", value)
        return re.sub(
            r"(?i)\b(password|token|api_key|secret)\s*[:=]\s*\S+", r"\1=[redacted]", value
        )
    return value


def request_inputs(data: AnalysisInput) -> dict[str, str]:
    # Only the evidence allowlist crosses the boundary. Never accept arbitrary
    # run/ticket objects containing labels, schedules, rubric or private truth.
    if (
        data.max_output_tokens != 2048
        or len(data.evidence) > 50
        or len({item.id for item in data.evidence}) != len(data.evidence)
    ):
        raise DifyAnalysisFailure("DIFY_ANALYSIS_INPUT_INVALID")
    payload = {
        "contract_version": CONTRACT_VERSION,
        "prompt_version": data.prompt_version,
        "evidence": redact_evidence([item.model_dump(mode="json") for item in data.evidence]),
        "response_schema": AnalysisResult.model_json_schema(),
        "max_output_tokens": data.max_output_tokens,
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > MAX_REQUEST_BYTES:
        # No silent truncation or changed evidence snapshot.
        raise DifyAnalysisFailure("DIFY_ANALYSIS_INPUT_TOO_LARGE")
    return {"analysis_input": serialized}


def parse_analysis(body: Any, workflow_id: str, allowed: set[UUID]) -> DifyAnalysisReply:
    reply = parse_workflow(body, expected_workflow_id=workflow_id)
    try:
        if set(reply.outputs) != {"analysis", "contract_version"}:
            raise ValueError("Unexpected outputs")
        if reply.outputs["contract_version"] != CONTRACT_VERSION:
            raise ValueError("Wrong contract")
        raw = reply.outputs["analysis"]
        result = (
            AnalysisResult.model_validate_json(raw)
            if isinstance(raw, str)
            else AnalysisResult.model_validate(raw)
        )
        validate_citations(result, allowed)
        if result.knowledge_refs or result.evidence_truncated or result.omitted_evidence_ids:
            raise ValueError("Unexpected retrieval/truncation")
        # This contract has no retrieval or generation tools; citations must be
        # exclusively from the frozen event snapshot, never external URLs.
        if re.search(r"</?think\b", result.model_dump_json(), re.IGNORECASE):
            raise ValueError("Reasoning output")
    except (ValidationError, ValueError, TypeError):
        raise DifyAnalysisFailure("DIFY_ANALYSIS_OUTPUT_INVALID", reply.total_tokens) from None
    return DifyAnalysisReply(result, reply.total_tokens, reply.run_id)


def _request(config: DifyConfig, workflow_id: str, data: AnalysisInput) -> DifyAnalysisReply:
    if not workflow_id or len(workflow_id) > 128:
        raise DifyAnalysisFailure("DIFY_WORKFLOW_INVALID")
    inputs = request_inputs(data)
    key = config.read_api_key()
    try:
        # A streamed response bounds memory even when a provider sends a large
        # invalid body. The request itself uses blocking Workflow execution.
        with requests.post(
            f"{config.base_url}/workflows/run",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "inputs": inputs,
                "response_mode": "blocking",
                "user": f"analysis-{data.analysis_id}",
            },
            timeout=(3.0, config.timeout_seconds),
            allow_redirects=False,
            stream=True,
        ) as response:
            if not 200 <= response.status_code < 300:
                # Even a 429/5xx cannot prove every upstream component used zero
                # tokens. Admission must retain unknown holds until reconciled.
                raise DifyAnalysisFailure("DIFY_ANALYSIS_REQUEST_FAILED")
            content = bytearray()
            for chunk in response.iter_content(8192):
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise DifyAnalysisFailure("DIFY_ANALYSIS_RESPONSE_TOO_LARGE")
            body = json.loads(content)
    except requests.Timeout:
        raise DifyAnalysisFailure("DIFY_TIMEOUT") from None
    except requests.RequestException:
        raise DifyAnalysisFailure("DIFY_REQUEST_FAILED") from None
    except (ValueError, UnicodeError):
        raise DifyAnalysisFailure("DIFY_INVALID_RESPONSE") from None
    return parse_analysis(body, workflow_id, {item.id for item in data.evidence})


async def analyze(config: DifyConfig, workflow_id: str, data: AnalysisInput) -> DifyAnalysisReply:
    """One dispatch only; never call without a durable quota/cost reservation."""
    return await asyncio.to_thread(_request, config, workflow_id, data)


class DifyInvestigationProvider:
    mode = "real"

    def __init__(self, snapshot: dict[str, Any]) -> None:
        from app.analysis.investigation_config import transport_config

        self.snapshot = snapshot
        self.config = transport_config(snapshot)

    async def analyze(self, data: AnalysisInput) -> ProviderOutput:
        from app.analysis.investigation_config import current_release

        if not current_release(self.snapshot):
            raise DifyAnalysisFailure("DIFY_RELEASE_WITHDRAWN")
        reply = await analyze(self.config, self.snapshot["workflow_id"], data)
        return ProviderOutput(
            result=reply.result,
            usage=ProviderUsage(
                mode="real", total_tokens=reply.total_tokens, pricing_tier="verified_bound"
            ),
        )

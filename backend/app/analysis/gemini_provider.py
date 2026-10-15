"""Bounded Gemini adapter for synthetic, frozen training evidence only."""

import asyncio
import json
from typing import Any

from pydantic import ValidationError

from app.analysis.gemini_smoke import call
from app.analysis.models import AnalysisResult, ProviderOutput, ProviderResponseError, ProviderUsage
from app.analysis.provider import AnalysisInput
from app.analysis.provider_config import ProviderConfig


class ProviderRateLimited(RuntimeError):
    """Safe explicit rejection; retry is a new budgeted logical request."""


def _string() -> dict[str, Any]:
    return {"type": "STRING"}


def _array(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "ARRAY", "items": item}


def response_schema() -> dict[str, Any]:
    """Inline schema uses Gemini's supported JSON Schema subset; Pydantic validates again."""
    hypothesis = {
        "type": "OBJECT",
        "properties": {"text": _string(), "evidence_refs": _array(_string())},
        "required": ["text", "evidence_refs"],
    }
    severity = {
        "type": "OBJECT",
        "properties": {
            "level": {"type": "STRING", "enum": ["low", "medium", "high", "critical"]},
            "reason": _string(),
        },
        "required": ["level", "reason"],
    }
    confidence = {
        "type": "OBJECT",
        "properties": {
            "level": {"type": "STRING", "enum": ["low", "medium", "high"]},
            "reason": _string(),
        },
        "required": ["level", "reason"],
    }
    return {
        "type": "OBJECT",
        "properties": {
            "summary": _string(),
            "hypotheses": {**_array(hypothesis), "maxItems": 1},
            "evidence_refs": _array(_string()),
            "observed_impact": _string(),
            "potential_impact": _string(),
            "suggested_severity": severity,
            "confidence": confidence,
            "unknowns": {**_array(_string()), "maxItems": 2},
            "recommended_checks": {**_array(_string()), "maxItems": 2},
        },
        "required": [
            "summary",
            "hypotheses",
            "evidence_refs",
            "observed_impact",
            "potential_impact",
            "suggested_severity",
            "confidence",
            "unknowns",
            "recommended_checks",
        ],
    }


def request_body(data: AnalysisInput) -> dict[str, Any]:
    evidence = [item.model_dump(mode="json") for item in data.evidence]
    instruction = (
        "Analyze only the supplied synthetic SOC training events. Do not use outside knowledge "
        "as evidence. Distinguish observed facts, hypotheses, potential impact, and unknowns. "
        "A blocked or HTTP 403 request is not successful compromise. Cite only event UUIDs from "
        "the supplied evidence. Do not infer ground truth, scores, or learner answers. Keep every "
        "field brief, use one hypothesis, at most two unknowns and checks, and avoid repeating "
        "events. Return cautious analysis in the requested JSON schema.\n\n"
        f"Prompt version: {data.prompt_version}\n"
        f"Allowed evidence UUIDs: {json.dumps([str(item.id) for item in data.evidence])}\n"
        f"Events: {json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))}"
    )
    return {
        "systemInstruction": {"parts": [{"text": instruction.split("\n\n", 1)[0]}]},
        "contents": [{"role": "user", "parts": [{"text": instruction.split("\n\n", 1)[1]}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema(),
            "thinkingConfig": {"thinkingLevel": "minimal"},
            "maxOutputTokens": data.max_output_tokens,
        },
    }


def parse_response(response: dict[str, Any]) -> ProviderOutput:
    metadata = response.get("usageMetadata") or {}
    input_tokens = int(metadata.get("promptTokenCount", 0))
    output_tokens = int(metadata.get("candidatesTokenCount", 0))
    usage = ProviderUsage(
        mode="real",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=int(metadata.get("totalTokenCount", input_tokens + output_tokens)),
        pricing_tier="free",
    )
    parts = response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in parts)
    if not text:
        raise ProviderResponseError("PROVIDER_EMPTY_RESPONSE", usage)
    try:
        result = AnalysisResult.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ProviderResponseError("INVALID_PROVIDER_OUTPUT", usage) from exc
    return ProviderOutput(
        result=result,
        usage=usage,
    )


class GeminiProvider:
    mode = "real"

    def __init__(self, config: ProviderConfig, request_timeout: float = 20) -> None:
        if config.mode != "gemini_free":
            raise ValueError("Real provider is not enabled")
        self.config = config
        self.request_timeout = request_timeout

    async def analyze(self, data: AnalysisInput) -> ProviderOutput:
        body = request_body(data)
        response = await asyncio.to_thread(
            call,
            self.config,
            self.config.chat_model,
            "generateContent",
            body,
            timeout=self.request_timeout,
        )
        if "smoke_error" in response:
            if response["smoke_error"] == "HTTP_429":
                raise ProviderRateLimited("PROVIDER_RATE_LIMITED")
            # A lost connection does not prove the provider did not process the
            # request. Keep its reservation unknown, just like a timeout.
            if response["smoke_error"] in {"TIMEOUT", "NETWORK_UNAVAILABLE"}:
                raise TimeoutError("GEMINI_REQUEST_TIMEOUT")
            raise RuntimeError("GEMINI_REQUEST_FAILED")
        return parse_response(response)

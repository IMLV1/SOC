import asyncio
import json
from uuid import uuid4

from app.analysis.gemini_provider import GeminiProvider, request_body
from app.analysis.provider import AnalysisInput, EvidenceItem, MockProvider
from app.analysis.provider_config import load_config


def analysis_input():
    return AnalysisInput(
        analysis_id=uuid4(),
        evidence=[
            EvidenceItem(
                id=uuid4(),
                source="web",
                username="synthetic-user",
                request={"method": "GET", "path": "/admin"},
                response={"status": 403},
                log={"event_type": "request_policy_denied"},
            )
        ],
        prompt_version="prompt-v1",
        max_output_tokens=256,
    )


def test_request_uses_inline_structured_schema_and_frozen_synthetic_evidence():
    data = analysis_input()
    body = request_body(data)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseSchema"]["type"] == "OBJECT"
    assert body["generationConfig"]["responseSchema"]["properties"]["hypotheses"]["maxItems"] == 1
    assert str(data.evidence[0].id) in body["contents"][0]["parts"][0]["text"]
    assert (
        "HTTP 403 request is not successful compromise"
        in body["systemInstruction"]["parts"][0]["text"]
    )
    assert "api_key" not in json.dumps(body).lower()


def test_gemini_adapter_parses_pydantic_output_and_usage_without_network(tmp_path, monkeypatch):
    data = analysis_input()
    expected = asyncio.run(MockProvider().analyze(data)).result
    key = tmp_path / "gemini_api_key.txt"
    key.write_text("synthetic-test-key")
    config = load_config(
        {
            "SOC_AI_PROVIDER": "gemini_free",
            "GEMINI_PROJECT_TIER_CONFIRMED": "free_no_billing",
            "GEMINI_SYNTHETIC_DATA_ONLY": "true",
            "GEMINI_API_KEY_FILE": str(key),
        }
    )
    requests = []

    def fake_call(received_config, model, method, body, timeout=20):
        requests.append((received_config, model, method, body))
        return {
            "candidates": [{"content": {"parts": [{"text": expected.model_dump_json()}]}}],
            "usageMetadata": {
                "promptTokenCount": 101,
                "candidatesTokenCount": 42,
                "totalTokenCount": 143,
            },
        }

    monkeypatch.setattr("app.analysis.gemini_provider.call", fake_call)
    output = asyncio.run(GeminiProvider(config).analyze(data))
    assert output.result == expected
    assert output.usage.mode == "real" and output.usage.pricing_tier == "free"
    assert (output.usage.input_tokens, output.usage.output_tokens, output.usage.total_tokens) == (
        101,
        42,
        143,
    )
    assert requests[0][1:3] == ("gemini-3.5-flash-lite", "generateContent")
    assert requests[0][3]["generationConfig"]["maxOutputTokens"] == 256
    assert requests[0][3]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}


def test_gemini_response_schema_is_revalidated():
    import pytest

    from app.analysis.gemini_provider import parse_response
    from app.analysis.models import ProviderResponseError

    with pytest.raises(ProviderResponseError) as caught:
        parse_response(
            {
                "candidates": [{"content": {"parts": [{"text": "{"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 50,
                    "candidatesTokenCount": 20,
                    "totalTokenCount": 70,
                },
            }
        )
    assert caught.value.usage.total_tokens == 70

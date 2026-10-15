from app.analysis import gemini_smoke
from app.analysis.provider_config import ProviderConfig


def test_generation_failure_stops_without_embedding_or_retry(monkeypatch):
    calls = []

    def fake_call(config, model, method, body):
        calls.append(method)
        return {"smoke_error": "HTTP_429"}

    monkeypatch.setattr(gemini_smoke, "call", fake_call)
    result = gemini_smoke.smoke(ProviderConfig("gemini_free", "chat", "embedding", None))
    assert calls == ["generateContent"]
    assert result["embedding"] == "NOT_ATTEMPTED"


def test_success_reports_usage_and_dimension_without_response_text(monkeypatch):
    def fake_call(config, model, method, body):
        if method == "generateContent":
            return {"candidates": [{"text": "do not log"}], "usageMetadata": {"totalTokenCount": 8}}
        return {"embedding": {"values": [0.1] * 768}}

    monkeypatch.setattr(gemini_smoke, "call", fake_call)
    result = gemini_smoke.smoke(ProviderConfig("gemini_free", "chat", "embedding", None))
    assert result["dimension"] == 768
    assert "do not log" not in str(result)

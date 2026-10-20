from pathlib import Path
from typing import Any

import pytest
import requests

from app.knowledge.dify_client import DifyConfig, DifyUnavailable, _parse_reply, chat


def test_dify_config_requires_https_and_server_secret(tmp_path: Path):
    with pytest.raises(DifyUnavailable, match="DIFY_CONFIGURATION_INVALID"):
        DifyConfig.from_env(
            {"DIFY_API_BASE_URL": "http://example.test/v1", "DIFY_APP_KEY_FILE": "key"}
        )
    config = DifyConfig.from_env(
        {"DIFY_API_BASE_URL": "https://dify.example.test/v1/", "DIFY_APP_KEY_FILE": "key"}
    )
    assert config.base_url == "https://dify.example.test/v1"
    assert config.api_key_file == Path("key")


def test_dify_config_allows_loopback_http_for_local_development():
    config = DifyConfig.from_env(
        {"DIFY_API_BASE_URL": "http://127.0.0.1:5001/v1", "DIFY_APP_KEY_FILE": "key"}
    )
    assert config.base_url == "http://127.0.0.1:5001/v1"


def test_dify_response_preserves_sources_and_unknown_usage():
    reply = _parse_reply(
        {
            "task_id": "task-safe-id",
            "answer": '{"answer":"check event"}',
            "metadata": {
                "retriever_resources": [
                    {
                        "segment_id": "segment-1",
                        "document_name": "approved-guide.md",
                        "content": "Use the request and response pair.",
                        "score": 0.87,
                    }
                ]
            },
        }
    )
    assert reply.total_tokens is None
    assert reply.sources[0].source_id == "segment-1"
    assert reply.sources[0].score == 0.87


def test_dify_rejects_missing_or_unbounded_sources():
    with pytest.raises(DifyUnavailable, match="DIFY_INVALID_RESPONSE"):
        _parse_reply({"answer": "ok", "metadata": {"retriever_resources": [{}]}})
    with pytest.raises(DifyUnavailable, match="DIFY_INVALID_RESPONSE"):
        _parse_reply({"answer": "ok", "metadata": {"retriever_resources": [{}] * 21}})


class _Response:
    status_code = 200

    def json(self) -> dict[str, Any]:
        return {
            "answer": "{}",
            "metadata": {"retriever_resources": [], "usage": {"total_tokens": 19}},
        }


def test_chat_calls_only_configured_api_and_keeps_auth_header_out_of_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    key_file = tmp_path / "dify-key"
    key_file.write_text("secret-dify-key", encoding="utf-8")
    config = DifyConfig("https://dify.example.test/v1", key_file)
    captured: dict[str, Any] = {}

    def post(url: str, **kwargs: Any) -> _Response:
        captured["url"] = url
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(requests, "post", post)
    reply = asyncio_run(chat(config, "question", "analysis-123"))
    assert captured["url"] == "https://dify.example.test/v1/chat-messages"
    assert captured["headers"]["Authorization"] == "Bearer secret-dify-key"
    assert captured["json"]["user"] == "analysis-123"
    assert reply.total_tokens == 19
    assert "secret-dify-key" not in repr(reply)


def asyncio_run(awaitable: Any) -> Any:
    import asyncio

    return asyncio.run(awaitable)


def test_chat_does_not_retry_after_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    key_file = tmp_path / "dify-key"
    key_file.write_text("secret-dify-key", encoding="utf-8")
    config = DifyConfig("https://dify.example.test/v1", key_file)
    calls = 0

    def post(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise requests.Timeout()

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(DifyUnavailable, match="DIFY_TIMEOUT"):
        asyncio_run(chat(config, "question", "analysis-123"))
    assert calls == 1

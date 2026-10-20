import pytest

from app.analysis.provider_config import load_config


def test_mock_is_default_and_ignores_legacy_gemini_credentials():
    config = load_config({"GEMINI_API_KEY_FILE": "must-not-read"})
    assert config.mode == "mock" and config.key_file is None


def test_dify_is_the_only_configurable_external_provider():
    config = load_config(
        {"SOC_AI_PROVIDER": "dify", "DIFY_API_BASE_URL": "https://dify.example.test/v1"}
    )
    assert config.mode == "dify" and config.chat_model == "dify-app"
    with pytest.raises(ValueError, match="HTTPS"):
        load_config({"SOC_AI_PROVIDER": "dify", "DIFY_API_BASE_URL": "http://example.test"})
    with pytest.raises(ValueError, match="Unsupported provider mode"):
        load_config({"SOC_AI_PROVIDER": "gemini_free"})
    with pytest.raises(ValueError, match="Unsupported provider mode"):
        load_config({"SOC_AI_PROVIDER": "paid"})


def test_worker_allows_mock_and_fails_closed_for_external_provider():
    from app.analysis.provider import MockProvider
    from app.analysis.worker import configured_provider

    assert isinstance(configured_provider("mock", "mock-v1"), MockProvider)
    with pytest.raises(RuntimeError, match="DIFY_ANALYSIS_ADAPTER_UNAVAILABLE"):
        configured_provider("real", "legacy-model-pin")

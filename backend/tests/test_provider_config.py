import pytest

from app.analysis.provider_config import load_config


def test_mock_is_default_and_does_not_read_credentials():
    config = load_config({"GEMINI_API_KEY_FILE": "must-not-read"})
    assert config.mode == "mock" and config.key_file is None
    with pytest.raises(ValueError, match="not enabled"):
        config.read_key()


def valid_env(path):
    return {
        "SOC_AI_PROVIDER": "gemini_free",
        "GEMINI_API_KEY_FILE": str(path),
        "GEMINI_PROJECT_TIER_CONFIRMED": "free_no_billing",
        "GEMINI_SYNTHETIC_DATA_ONLY": "true",
    }


@pytest.mark.parametrize(
    "field", ["GEMINI_API_KEY_FILE", "GEMINI_PROJECT_TIER_CONFIRMED", "GEMINI_SYNTHETIC_DATA_ONLY"]
)
def test_real_config_requires_explicit_setup(tmp_path, field):
    env = valid_env(tmp_path / "key")
    del env[field]
    with pytest.raises(ValueError):
        load_config(env)


def test_key_contents_are_not_in_config_repr_or_failure(tmp_path):
    path = tmp_path / "key"
    path.write_text("synthetic-test-key-only")
    config = load_config(valid_env(path))
    assert config.read_key() == "synthetic-test-key-only"
    assert "synthetic-test-key-only" not in repr(config)
    path.write_text("bad secret with spaces")
    with pytest.raises(ValueError, match="^Provider credential unavailable$"):
        config.read_key()


def test_paid_modes_and_unapproved_models_are_rejected(tmp_path):
    for override in (
        {"SOC_AI_PROVIDER": "paid"},
        {"GEMINI_CHAT_MODEL": "other"},
        {"GEMINI_EMBEDDING_MODEL": "other"},
    ):
        with pytest.raises(ValueError):
            load_config({**valid_env(tmp_path / "key"), **override})

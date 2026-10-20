"""Regression guard: legacy Gemini must not be selectable by runtime configuration."""

import pytest

from app.analysis.provider_config import load_config


def test_legacy_gemini_provider_mode_is_rejected():
    with pytest.raises(ValueError, match="Unsupported provider mode"):
        load_config({"SOC_AI_PROVIDER": "gemini_free"})

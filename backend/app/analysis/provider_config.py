"""Fail-closed configuration. Account billing tier cannot be inferred from an API key."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CHAT_MODEL = "gemini-3.5-flash-lite"
EMBEDDING_MODEL = "gemini-embedding-2"


@dataclass(frozen=True)
class ProviderConfig:
    mode: str
    chat_model: str
    embedding_model: str
    key_file: Path | None

    def read_key(self) -> str:
        if self.mode != "gemini_free" or self.key_file is None:
            raise ValueError("Real provider is not enabled")
        try:
            value = self.key_file.read_text(encoding="utf-8").strip()
        except OSError:
            raise ValueError("Provider credential unavailable") from None
        if not value or any(char.isspace() for char in value):
            raise ValueError("Provider credential unavailable")
        return value


def load_config(env: Mapping[str, str]) -> ProviderConfig:
    mode = env.get("SOC_AI_PROVIDER", "mock")
    if mode == "mock":
        return ProviderConfig(mode, "mock-v1", "fake-hash-16-v1", None)
    if mode != "gemini_free":
        raise ValueError("Unsupported provider mode")
    if env.get("GEMINI_PROJECT_TIER_CONFIRMED") != "free_no_billing":
        raise ValueError("Confirm a project without billing before enabling real calls")
    if env.get("GEMINI_SYNTHETIC_DATA_ONLY") != "true":
        raise ValueError("Synthetic-data policy required")
    key = env.get("GEMINI_API_KEY_FILE", "")
    if not key:
        raise ValueError("Provider credential file required")
    if env.get("GEMINI_CHAT_MODEL", CHAT_MODEL) != CHAT_MODEL:
        raise ValueError("Unapproved chat model")
    if env.get("GEMINI_EMBEDDING_MODEL", EMBEDDING_MODEL) != EMBEDDING_MODEL:
        raise ValueError("Unapproved embedding model")
    return ProviderConfig(mode, CHAT_MODEL, EMBEDDING_MODEL, Path(key))

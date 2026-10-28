"""Default mock; external dispatch requires a separately reviewed investigation release."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProviderConfig:
    mode: str
    chat_model: str
    embedding_model: str
    key_file: Path | None
    investigation_snapshot: dict[str, Any] | None = None

    def read_key(self) -> str:
        if self.mode != "dify" or self.key_file is None:
            raise ValueError("Live provider is not enabled")
        try:
            value = self.key_file.read_text(encoding="utf-8").strip()
        except OSError:
            raise ValueError("Provider credential unavailable") from None
        if not value or any(char.isspace() for char in value):
            raise ValueError("Provider credential unavailable")
        return value


def load_config(env: Mapping[str, str]) -> ProviderConfig:
    # Local and CI stay deterministic. Direct model-provider calls are disabled;
    # Dify is the sole external AI boundary. Missing/unapproved release config
    # fails admission before a real run or provider request can be created.
    mode = env.get("SOC_AI_PROVIDER", "mock")
    if mode == "mock":
        return ProviderConfig(mode, "mock-v1", "fake-hash-16-v1", None)
    if mode == "dify":
        base_url = env.get("DIFY_API_BASE_URL", "https://api.dify.ai/v1").strip()
        parsed = urlsplit(base_url)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if not parsed.hostname or (parsed.scheme != "https" and not local):
            raise ValueError("Dify Base URL must use HTTPS")
        from app.analysis.investigation_config import model_pin, release_snapshot

        snapshot = release_snapshot(env)
        return ProviderConfig(
            mode,
            model_pin(snapshot),
            "dify-managed",
            Path(env["DIFY_ANALYSIS_APP_KEY_FILE"]),
            snapshot,
        )
    raise ValueError("Unsupported provider mode")

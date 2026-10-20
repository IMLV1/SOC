"""Provider configuration. Real dispatch currently fails closed in the worker."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProviderConfig:
    mode: str
    chat_model: str
    embedding_model: str
    key_file: Path | None

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
    # Dify is the sole intended external AI boundary. The worker currently
    # rejects real dispatch until its structured/citation adapter is integrated.
    mode = env.get("SOC_AI_PROVIDER", "mock")
    if mode == "mock":
        return ProviderConfig(mode, "mock-v1", "fake-hash-16-v1", None)
    if mode == "dify":
        base_url = env.get("DIFY_API_BASE_URL", "").strip()
        parsed = urlsplit(base_url)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if not parsed.hostname or (parsed.scheme != "https" and not local):
            raise ValueError("Dify Base URL must use HTTPS")
        return ProviderConfig(mode, "dify-app", "dify-managed", None)
    raise ValueError("Unsupported provider mode")

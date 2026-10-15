"""Explicit bounded credential smoke; never invoked by API startup or CI."""

import json
import socket
import urllib.error
import urllib.request
from typing import Any

from app.analysis.provider_config import ProviderConfig


def call(
    config: ProviderConfig,
    model: str,
    method: str,
    body: dict[str, Any],
    timeout: float = 20,
) -> dict[str, Any]:
    if model not in {config.chat_model, config.embedding_model}:
        raise ValueError("Unapproved model")
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{method}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": config.read_key()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return dict(json.loads(response.read()))
    except urllib.error.HTTPError as error:
        # Never return upstream bodies, URLs or headers containing credentials.
        return {"smoke_error": f"HTTP_{error.code}"}
    except (urllib.error.URLError, TimeoutError) as error:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        return {
            "smoke_error": (
                "TIMEOUT"
                if isinstance(reason, (TimeoutError, socket.timeout))
                else "NETWORK_UNAVAILABLE"
            )
        }


def smoke(config: ProviderConfig) -> dict[str, object]:
    chat = call(
        config,
        config.chat_model,
        "generateContent",
        {
            "contents": [
                {
                    "parts": [
                        {"text": "Reply with exactly OK. This is a synthetic connectivity test."}
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": 16, "thinkingConfig": {"thinkingBudget": 0}},
        },
    )
    summary: dict[str, object] = {"chat_model": config.chat_model}
    if "smoke_error" in chat:
        summary["chat"] = chat["smoke_error"]
        summary["embedding"] = "NOT_ATTEMPTED"
        return summary
    summary["chat"] = "OK" if chat.get("candidates") else "NO_CANDIDATE"
    summary["usage"] = chat.get("usageMetadata", {})
    embedding = call(
        config,
        config.embedding_model,
        "embedContent",
        {
            "content": {
                "parts": [{"text": "Synthetic SOC guide: compare HTTP requests with responses."}]
            },
            "outputDimensionality": 768,
        },
    )
    summary["embedding_model"] = config.embedding_model
    summary["embedding"] = embedding.get(
        "smoke_error", "OK" if embedding.get("embedding") else "NO_VECTOR"
    )
    if "embedding" in embedding:
        summary["dimension"] = len(embedding["embedding"].get("values", []))
    return summary

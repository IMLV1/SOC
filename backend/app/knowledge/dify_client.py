"""Small server-side Dify Chat API client; disabled unless explicitly configured."""

import asyncio
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests


class DifyUnavailable(RuntimeError):
    """Safe, non-sensitive Dify failure code."""


@dataclass(frozen=True)
class DifyConfig:
    base_url: str
    api_key_file: Path
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "DifyConfig":
        values = env if env is not None else os.environ
        base_url = values.get("DIFY_API_BASE_URL", "https://api.dify.ai/v1").strip().rstrip("/")
        key_file = values.get("DIFY_APP_KEY_FILE", "").strip()
        parsed = urlsplit(base_url)
        local_http = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            parsed.scheme not in ({"https", "http"} if local_http else {"https"})
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not key_file
        ):
            raise DifyUnavailable("DIFY_CONFIGURATION_INVALID")
        return cls(base_url=base_url, api_key_file=Path(key_file))

    def read_api_key(self) -> str:
        try:
            key = self.api_key_file.read_text(encoding="utf-8").strip()
        except OSError:
            raise DifyUnavailable("DIFY_CREDENTIAL_UNAVAILABLE") from None
        if not key or any(character.isspace() for character in key):
            raise DifyUnavailable("DIFY_CREDENTIAL_UNAVAILABLE")
        return key


@dataclass(frozen=True)
class DifySource:
    source_id: str
    title: str
    excerpt: str
    score: float | None


@dataclass(frozen=True)
class DifyReply:
    answer: str
    sources: tuple[DifySource, ...]
    total_tokens: int | None
    task_id: str | None


def _parse_reply(body: Any) -> DifyReply:
    if not isinstance(body, dict) or not isinstance(body.get("answer"), str):
        raise DifyUnavailable("DIFY_INVALID_RESPONSE")
    metadata = body.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    raw_sources = metadata.get("retriever_resources", [])
    if not isinstance(raw_sources, list) or len(raw_sources) > 20:
        raise DifyUnavailable("DIFY_INVALID_RESPONSE")
    sources: list[DifySource] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            raise DifyUnavailable("DIFY_INVALID_RESPONSE")
        source_id = item.get("segment_id") or item.get("document_id") or item.get("id")
        title = item.get("document_name") or item.get("title")
        excerpt = item.get("content") or item.get("segment_content")
        if not isinstance(source_id, str) or not source_id.strip():
            raise DifyUnavailable("DIFY_INVALID_RESPONSE")
        if not isinstance(title, str) or not isinstance(excerpt, str):
            raise DifyUnavailable("DIFY_INVALID_RESPONSE")
        score_value = item.get("score")
        score = float(score_value) if isinstance(score_value, (int, float)) else None
        if score is not None and not 0 <= score <= 1:
            score = None
        sources.append(DifySource(source_id.strip(), title[:240], excerpt[:6000], score))
    usage = metadata.get("usage")
    tokens: int | None = None
    if isinstance(usage, dict):
        raw_total = usage.get("total_tokens")
        if isinstance(raw_total, int) and raw_total >= 0:
            tokens = raw_total
    task_id = body.get("task_id")
    return DifyReply(
        answer=body["answer"][:12000],
        sources=tuple(sources),
        total_tokens=tokens,
        task_id=task_id if isinstance(task_id, str) else None,
    )


def _request(config: DifyConfig, query: str, user_id: str) -> DifyReply:
    key = config.read_api_key()
    try:
        response = requests.post(
            f"{config.base_url}/chat-messages",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"inputs": {}, "query": query, "response_mode": "blocking", "user": user_id},
            timeout=(3.0, config.timeout_seconds),
        )
    except requests.Timeout as exc:
        raise DifyUnavailable("DIFY_TIMEOUT") from exc
    except requests.RequestException as exc:
        raise DifyUnavailable("DIFY_REQUEST_FAILED") from exc
    if response.status_code < 200 or response.status_code >= 300:
        raise DifyUnavailable("DIFY_REQUEST_FAILED")
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise DifyUnavailable("DIFY_INVALID_RESPONSE") from exc
    return _parse_reply(body)


async def chat(config: DifyConfig, query: str, user_id: str) -> DifyReply:
    """Call Dify outside DB transactions; callers must reserve quota before dispatch."""
    if not query.strip() or len(query.encode("utf-8")) > 12000:
        raise DifyUnavailable("DIFY_QUERY_INVALID")
    if not user_id.strip() or len(user_id) > 128:
        raise DifyUnavailable("DIFY_USER_INVALID")
    return await asyncio.to_thread(_request, config, query, user_id)

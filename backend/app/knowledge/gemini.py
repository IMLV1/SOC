"""Selected free-tier embeddings and structured generation; no implicit dispatch retries."""

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.analysis.budget import reserve_call, settle_call
from app.analysis.fake_embeddings import validate_vector
from app.analysis.gemini_provider import GeminiProvider
from app.analysis.gemini_smoke import call
from app.analysis.provider import StructuredAnalysisProvider
from app.analysis.provider_config import load_config
from app.db.session import Database

PROFILE = "gemini-embedding-2-768-v1"


async def dispatch(
    database: Database,
    identity: UUID,
    component: str,
    body: dict[str, Any],
    *,
    operation: str | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    config = load_config(os.environ)
    if (
        config.mode != "gemini_free"
        or os.getenv("SOC_RAG_REAL_CONFIRMED") != "approved-corpus-free-v1"
    ):
        raise ValueError("RAG_REAL_NOT_CONFIRMED")
    model = config.chat_model if component == "generation" else config.embedding_model
    bound = len(json.dumps(body, ensure_ascii=False).encode()) + 4096 + 1200
    async with database.sessions() as session, session.begin():
        if operation is None:
            reservation = await session.scalar(
                text("""SELECT reserved_tokens
                FROM app.quota_components WHERE analysis_id=:id AND component=:component"""),
                {"id": identity, "component": component},
            )
            if reservation is None or bound > reservation:
                raise ValueError("COMPONENT_BUDGET_EXCEEDED")
        if not await reserve_call(
            session, identity, model, bound, component=component, operation_key=operation
        ):
            raise RuntimeError("PROVIDER_BUDGET_OR_RATE_LIMIT")
    started = time.monotonic()
    if component == "generation":
        provider: StructuredAnalysisProvider = GeminiProvider(config)
        response = await provider.structured(body)
    else:
        response = await asyncio.to_thread(
            call,
            config,
            model,
            method or ("generateContent" if component == "generation" else "embedContent"),
            body,
            timeout=20 if component == "generation" else 5,
        )
    latency_ms = round((time.monotonic() - started) * 1000)
    error = response.get("smoke_error")
    metadata = response.get("usageMetadata") or {}
    tokens = int(
        metadata.get(
            "totalTokenCount",
            metadata.get("promptTokenCount", 0) if component != "generation" else 0,
        )
    )
    async with database.sessions() as session, session.begin():
        await settle_call(
            session,
            identity,
            tokens,
            rejected=error == "HTTP_429",
            cooldown=60 if error == "HTTP_429" else 0,
            component=component,
            operation_key=operation,
        )
        column = "operation_key" if operation is not None else "analysis_id"
        await session.execute(
            text(f"""UPDATE app.provider_calls SET telemetry_json=CAST(:telemetry AS jsonb)
            WHERE {column}=:id AND component=:component"""),
            {
                "id": operation if operation is not None else identity,
                "component": component,
                "telemetry": json.dumps(
                    {
                        "latency_ms": latency_ms,
                        "input_tokens": metadata.get("promptTokenCount"),
                        "output_tokens": metadata.get("candidatesTokenCount"),
                        "thinking_tokens": metadata.get("thoughtsTokenCount"),
                        "total_tokens": metadata.get("totalTokenCount"),
                        "error_code": error,
                    }
                ),
            },
        )
    if error in {"TIMEOUT", "NETWORK_UNAVAILABLE"}:
        raise TimeoutError("RAG_PROVIDER_TIMEOUT")
    if error:
        raise RuntimeError("RAG_PROVIDER_UNAVAILABLE")
    return response


async def embed(
    database: Database,
    identity: UUID,
    content: str,
    *,
    operation: str | None = None,
    document: bool = False,
) -> list[float]:
    if len(content.encode()) > 8000:
        raise ValueError("EMBEDDING_BUDGET_EXCEEDED")
    # Embedding 2 uses prompt instructions rather than taskType.
    response = await dispatch(
        database,
        identity,
        "document_embedding" if document else "query_embedding",
        {
            "model": "models/gemini-embedding-2",
            "content": {"parts": [{"text": content}]},
            "outputDimensionality": 768,
        },
        operation=operation,
    )
    vector = response.get("embedding", {}).get("values", [])
    validate_vector(vector, 768)
    if not any(vector):
        raise ValueError("ZERO_EMBEDDING")
    return list(vector)


async def count_prompt(
    database: Database, identity: UUID, body: dict[str, Any], operation: str | None = None
) -> int:
    """Model tokenizer preflight; counting input is not generation usage.

    Each HTTP dispatch consumes a global request slot. Failed/ambiguous calls
    retain their capacity hold. There is no silent local-tokenizer fallback.
    """
    config = load_config(os.environ)
    if (
        config.mode != "gemini_free"
        or os.getenv("SOC_RAG_REAL_CONFIRMED") != "approved-corpus-free-v1"
    ):
        raise ValueError("RAG_REAL_NOT_CONFIRMED")
    key = f"token-count:{operation or identity}"
    bound = len(json.dumps(body, ensure_ascii=False).encode()) + 4096
    async with database.sessions() as session, session.begin():
        if not await reserve_call(
            session,
            identity,
            config.chat_model,
            bound,
            component="token_count",
            operation_key=key,
        ):
            raise RuntimeError("PROVIDER_BUDGET_OR_RATE_LIMIT")
    started = time.monotonic()
    response = await asyncio.to_thread(
        call,
        config,
        config.chat_model,
        "countTokens",
        {"generateContentRequest": {"model": f"models/{config.chat_model}", **body}},
        timeout=3,
    )
    error = response.get("smoke_error")
    count = response.get("totalTokens")
    valid = type(count) is int and count > 0
    telemetry = {
        "latency_ms": round((time.monotonic() - started) * 1000),
        "counted_input_tokens": count if valid else None,
        "error_code": error if error else None if valid else "INVALID_TOKEN_COUNT",
    }
    async with database.sessions() as session, session.begin():
        await session.execute(text("SELECT id FROM app.provider_policy WHERE id=1 FOR UPDATE"))
        await session.execute(
            text("""UPDATE app.provider_calls SET status=:status,actual_tokens=:tokens,
            telemetry_json=CAST(:telemetry AS jsonb)
            WHERE operation_key=:key AND status='unknown'"""),
            {
                "key": key,
                "status": "consumed" if valid and not error else "unknown",
                # Counted input length is NOT tokens consumed by generation.
                "tokens": 0 if valid and not error else None,
                "telemetry": json.dumps(telemetry),
            },
        )
        if error == "HTTP_429":
            await settle_call(
                session,
                identity,
                0,
                rejected=True,
                cooldown=60,
                component="token_count",
                operation_key=key,
            )
    if error in {"TIMEOUT", "NETWORK_UNAVAILABLE"}:
        raise TimeoutError("TOKENIZER_UNAVAILABLE")
    if error or not valid:
        raise ValueError("TOKENIZER_UNAVAILABLE")
    assert isinstance(count, int)
    return count


async def structured(
    database: Database,
    identity: UUID,
    messages: Any,
    schema: dict[str, Any],
    operation: str | None = None,
    dispatch_guard: Callable[[], Awaitable[None]] | None = None,
) -> str:
    body = {
        "systemInstruction": {"parts": [{"text": messages.messages[0].content}]},
        "contents": [{"role": "user", "parts": [{"text": messages.messages[1].content}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
            "maxOutputTokens": 1200,
            "temperature": 0,
            "thinkingConfig": {"thinkingLevel": "minimal"},
        },
    }
    counted = await count_prompt(database, identity, body, operation)
    # Conservative 16k window, including output allowance and all request policy/schema.
    # Component context caps are stricter UTF-8 byte caps before this exact preflight.
    if counted + 1200 > 16000:
        raise ValueError("MODEL_CONTEXT_BUDGET_EXCEEDED")
    if dispatch_guard is not None:
        await dispatch_guard()
    response = await dispatch(database, identity, "generation", body, operation=operation)
    return "".join(
        p.get("text", "")
        for p in response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    )

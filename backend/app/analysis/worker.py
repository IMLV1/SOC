"""Execute one frozen mock analysis with fencing and typed output validation."""

import asyncio
import json
import os
import time
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import text

from app.analysis.gemini_provider import GeminiProvider
from app.analysis.models import AnalysisResult, ProviderOutput, ProviderResponseError, ProviderUsage
from app.analysis.provider import AnalysisInput, AnalysisProvider, MockProvider, validate_citations
from app.analysis.provider_config import load_config
from app.db.session import Database
from app.worker.fencing import lock_domain, require_lease


def configured_provider(mode: str, model_id: str) -> AnalysisProvider:
    if mode == "mock":
        return MockProvider()
    config = load_config(os.environ)
    if config.mode != "gemini_free" or config.chat_model != model_id:
        raise RuntimeError("PINNED_PROVIDER_UNAVAILABLE")
    return GeminiProvider(config)


async def analyze_job(
    database: Database,
    job: dict[str, Any],
    provider: AnalysisProvider | None = None,
    timeout: float = 30,
) -> None:
    analysis_id = UUID(job["payload"]["analysis_id"])
    attempt_id = uuid4()
    async with database.sessions() as session, session.begin():
        if not await lock_domain(session, job):
            return
        row = (
            (
                await session.execute(
                    text("""SELECT * FROM app.analyses
            WHERE id=:id FOR UPDATE"""),
                    {"id": analysis_id},
                )
            )
            .mappings()
            .one()
        )
        if row["status"] not in {"queued", "running"}:
            return
        evidence = (
            (
                await session.execute(
                    text("""SELECT e.id,e.source,e.username,
            e.request_json AS request,e.response_json AS response,e.log_json AS log
            FROM app.analysis_evidence ae JOIN app.events e
            ON e.run_id=ae.run_id AND e.id=ae.event_id
            WHERE ae.analysis_id=:id ORDER BY e.release_seq"""),
                    {"id": analysis_id},
                )
            )
            .mappings()
            .all()
        )
        data = AnalysisInput.model_validate(
            {
                "analysis_id": analysis_id,
                "evidence": [dict(item) for item in evidence],
                "prompt_version": row["prompt_version"],
                "max_output_tokens": 2048,
            }
        )
        await session.execute(
            text("""UPDATE app.analyses SET status='running',
            started_at=COALESCE(started_at,clock_timestamp()),version=version+1
            WHERE id=:id"""),
            {"id": analysis_id},
        )
        await session.execute(
            text("""INSERT INTO app.analysis_attempts
            (id,run_id,analysis_id,attempt_no,status)
            VALUES (:id,:run,:analysis,:number,'running')"""),
            {
                "id": attempt_id,
                "run": row["run_id"],
                "analysis": analysis_id,
                "number": job["attempts"],
            },
        )
        await require_lease(session, job)
    started = time.monotonic()
    status = "succeeded"
    error: str | None = None
    result_json: str | None = None
    usage = {
        "mode": row["mode"],
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "pricing_tier": "mock" if row["mode"] == "mock" else "free",
    }
    try:
        selected_provider = provider or configured_provider(row["mode"], row["model_id"])
        raw = await asyncio.wait_for(selected_provider.analyze(data), timeout=timeout)
        if isinstance(raw, ProviderOutput):
            output = raw
        elif isinstance(raw, dict) and "result" in raw and "usage" in raw:
            output = ProviderOutput.model_validate(raw)
        else:
            output = ProviderOutput(
                result=AnalysisResult.model_validate(raw),
                usage=ProviderUsage.model_validate(usage),
            )
        usage = output.usage.model_dump(mode="json")
        result = output.result
        validate_citations(result, {item.id for item in data.evidence})
        result_json = result.model_dump_json()
    except TimeoutError:
        status, error = "timed_out", "PROVIDER_TIMEOUT"
    except ProviderResponseError as exc:
        status, error = "invalid_output", "INVALID_PROVIDER_OUTPUT"
        usage = exc.usage.model_dump(mode="json")
    except (ValidationError, ValueError, TypeError):
        status, error = "invalid_output", "INVALID_PROVIDER_OUTPUT"
    except Exception:
        status, error = "failed", "PROVIDER_ERROR"
    latency = int((time.monotonic() - started) * 1000)
    async with database.sessions() as session, session.begin():
        if not await lock_domain(session, job):
            return
        await session.execute(
            text("""UPDATE app.analyses SET status=:status,
            result_json=CAST(:result AS jsonb),error_code=:error,
            usage_json=CAST(:usage AS jsonb),latency_ms=:latency,
            finished_at=clock_timestamp(),version=version+1 WHERE id=:id"""),
            {
                "status": status,
                "result": result_json,
                "error": error,
                "usage": json.dumps(usage),
                "latency": latency,
                "id": analysis_id,
            },
        )
        await session.execute(
            text("""UPDATE app.analysis_attempts SET status=:status,
            finished_at=clock_timestamp(),error_code=:error,
            usage_json=CAST(:usage AS jsonb) WHERE id=:id"""),
            {
                "status": status,
                "error": error,
                "usage": json.dumps(usage),
                "id": attempt_id,
            },
        )
        total_tokens = int(usage.get("total_tokens", 0))
        if total_tokens:
            await session.execute(
                text("""UPDATE app.quota_ledgers SET consumed_tokens=consumed_tokens+:tokens,
                version=version+1 WHERE id IN (
                    SELECT ledger_id FROM app.quota_reservations
                    WHERE analysis_id=:id AND status='reserved')"""),
                {"tokens": total_tokens, "id": analysis_id},
            )
        await session.execute(
            text("""UPDATE app.quota_reservations SET
            status=:status,actual_tokens=:tokens,settled_at=clock_timestamp()
            WHERE analysis_id=:id AND status='reserved'"""),
            {
                "status": (
                    "consumed"
                    if (row["mode"] == "mock" and status == "succeeded") or total_tokens > 0
                    else "unknown"
                    if row["mode"] == "real"
                    and status
                    in {
                        "succeeded",
                        "timed_out",
                        "invalid_output",
                    }
                    else "released"
                ),
                "tokens": (
                    total_tokens
                    if total_tokens > 0 or (row["mode"] == "mock" and status == "succeeded")
                    else None
                ),
                "id": analysis_id,
            },
        )

        await require_lease(session, job)

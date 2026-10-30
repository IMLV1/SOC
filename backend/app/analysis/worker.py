"""Execute a frozen training analysis with fencing and typed output validation."""

import asyncio
import json
import time
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import text

from app.analysis.budget import reserve_call, settle_call
from app.analysis.dify_provider import DifyAnalysisProvider
from app.analysis.models import AnalysisResult, ProviderOutput, ProviderResponseError, ProviderUsage
from app.analysis.provider import (
    AnalysisInput,
    AnalysisProvider,
    MockProvider,
    ProviderRateLimited,
    validate_citations,
)
from app.db.session import Database
from app.worker.fencing import lock_domain, require_lease


def configured_provider(
    mode: str, model_id: str, policy: dict[str, Any] | None = None
) -> AnalysisProvider:
    if mode == "mock":
        return MockProvider()
    if mode == "real" and policy is not None:
        return DifyAnalysisProvider(policy)
    raise RuntimeError("DIFY_ANALYSIS_ADAPTER_UNAVAILABLE")


async def analyze_job(
    database: Database,
    job: dict[str, Any],
    provider: AnalysisProvider | None = None,
    timeout: float = 30,
) -> None:
    # Domain preparation and finalization use short DB transactions; provider IO
    # happens between them so network latency never holds row locks open.
    analysis_policy: dict[str, Any] | None = None
    async with database.sessions() as session, session.begin():
        if not await session.scalar(
            text("SELECT app.is_training_run(:run)"), {"run": job["run_id"]}
        ):
            if await lock_domain(session, job):
                aid = UUID(job["payload"]["analysis_id"])
                await session.execute(
                    text("""UPDATE app.analyses SET status='cancelled',
                    error_code='AI_UNAVAILABLE_IN_EXAM',finished_at=clock_timestamp(),version=version+1
                    WHERE id=:id AND status IN ('queued','running')"""),
                    {"id": aid},
                )
                await session.execute(
                    text(
                        "UPDATE app.quota_components SET status='released' "
                        "WHERE analysis_id=:id AND status='reserved'"
                    ),
                    {"id": aid},
                )
                await session.execute(
                    text("""UPDATE app.quota_reservations SET status='released',
                    settled_at=clock_timestamp() WHERE analysis_id=:id AND status='reserved'"""),
                    {"id": aid},
                )
                await require_lease(session, job)
            return
        rag = await session.scalar(
            text("SELECT knowledge_release_id FROM app.analyses WHERE id=:id"),
            {"id": UUID(job["payload"]["analysis_id"])},
        )
    if rag is not None:
        # The local pgvector/Gemini pipeline is legacy. Dify owns retrieval in
        # the intended product flow; do not silently serve old local RAG jobs.
        async with database.sessions() as session, session.begin():
            if await lock_domain(session, job):
                analysis_id = UUID(job["payload"]["analysis_id"])
                await session.execute(
                    text("""UPDATE app.analyses SET status='failed',
                    error_code='DIFY_RAG_ADAPTER_UNAVAILABLE',finished_at=clock_timestamp(),
                    version=version+1 WHERE id=:id AND status IN ('queued','running')"""),
                    {"id": analysis_id},
                )
                await session.execute(
                    text("""UPDATE app.quota_reservations SET status='released',
                    settled_at=clock_timestamp() WHERE analysis_id=:id AND status='reserved'"""),
                    {"id": analysis_id},
                )
                await require_lease(session, job)
        return
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
        if row["mode"] == "real" and provider is None:
            from app.tutor.service import readiness, release_drift

            policy_row = (
                (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
                .mappings()
                .one()
            )
            pinned = (
                (
                    await session.execute(
                        text("""SELECT config_snapshot
                FROM app.run_versions WHERE run_id=:run"""),
                        {"run": row["run_id"]},
                    )
                )
                .mappings()
                .one()["config_snapshot"]
                .get("analysis_release")
            )
            if (
                not policy_row["analysis_enabled"]
                or readiness(policy_row)
                or await release_drift(session, policy_row["version"])
                or not isinstance(pinned, dict)
                or pinned.get("policy_version") != policy_row["version"]
                or pinned.get("workflow_id") != policy_row["workflow_id"]
                or pinned.get("corpus_revision") != policy_row["corpus_revision"]
            ):
                analysis_policy = None
            else:
                analysis_policy = dict(policy_row)
        if row["mode"] == "real" and provider is None and analysis_policy is None:
            await session.execute(
                text("""UPDATE app.analyses SET status='failed',
                error_code='DIFY_ANALYSIS_ADAPTER_UNAVAILABLE',finished_at=clock_timestamp(),
                version=version+1 WHERE id=:id"""),
                {"id": analysis_id},
            )
            await session.execute(
                text("""UPDATE app.quota_components SET status='released'
                WHERE analysis_id=:id AND status='reserved'"""),
                {"id": analysis_id},
            )
            await session.execute(
                text("""UPDATE app.quota_reservations SET status='released',
                settled_at=clock_timestamp() WHERE analysis_id=:id AND status='reserved'"""),
                {"id": analysis_id},
            )
            await require_lease(session, job)
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
        if row["mode"] == "real":
            # Reserve a conservative input/output bound before dispatch. If this
            # admission fails, the worker records unavailable without dispatch.
            # UTF-8 bytes conservatively bound input tokens, including schema,
            # with additional headroom for provider framing. Output is bounded.
            token_bound = (
                len(json.dumps(data.model_dump(mode="json"), ensure_ascii=False).encode())
                + 4096
                + data.max_output_tokens
            )
            admitted = await reserve_call(session, analysis_id, row["model_id"], token_bound)
            if not admitted:
                await session.execute(
                    text("""UPDATE app.analyses SET status='quota_exceeded',
                    error_code='PROVIDER_BUDGET_OR_RATE_LIMIT',finished_at=clock_timestamp(),
                    version=version+1 WHERE id=:id"""),
                    {"id": analysis_id},
                )
                await session.execute(
                    text("""UPDATE app.quota_reservations SET status='released',
                    settled_at=clock_timestamp() WHERE analysis_id=:id AND status='reserved'"""),
                    {"id": analysis_id},
                )
                await require_lease(session, job)
                return
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
        selected_provider = provider or configured_provider(
            row["mode"], row["model_id"], analysis_policy
        )
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
        # Citations must point only to the frozen evidence set prepared above.
        validate_citations(result, {item.id for item in data.evidence})
        result_json = result.model_dump_json()
    except ProviderRateLimited:
        status, error = "failed", "PROVIDER_RATE_LIMITED"
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
        # Recheck the lease before persistence; an expired worker must not overwrite
        # the result after another worker has reclaimed the job.
        if not await lock_domain(session, job):
            return
        if row["mode"] == "real":
            await settle_call(
                session,
                analysis_id,
                int(usage.get("total_tokens", 0)),
                rejected=error == "PROVIDER_RATE_LIMITED",
                cooldown=60 if error == "PROVIDER_RATE_LIMITED" else 0,
            )
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
        await session.execute(
            text("""SELECT l.id FROM app.quota_ledgers l
            JOIN app.quota_reservations q ON q.ledger_id=l.id
            WHERE q.analysis_id=:id AND q.status='reserved'
            ORDER BY l.scope_key,l.period_start FOR UPDATE OF l"""),
            {"id": analysis_id},
        )
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

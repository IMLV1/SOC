"""Execute one frozen mock analysis with fencing and typed output validation."""

import asyncio
import json
import time
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import text

from app.analysis.models import AnalysisResult
from app.analysis.provider import AnalysisInput, AnalysisProvider, MockProvider, validate_citations
from app.db.session import Database


async def analyze_job(
    database: Database,
    job: dict[str, Any],
    provider: AnalysisProvider | None = None,
    timeout: float = 30,
) -> None:
    analysis_id = UUID(job["payload"]["analysis_id"])
    attempt_id = uuid4()
    async with database.sessions() as session, session.begin():
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
                "max_output_tokens": 512,
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
    started = time.monotonic()
    status = "succeeded"
    error: str | None = None
    result_json: str | None = None
    try:
        raw = await asyncio.wait_for((provider or MockProvider()).analyze(data), timeout=timeout)
        result = AnalysisResult.model_validate(raw)
        validate_citations(result, {item.id for item in data.evidence})
        result_json = result.model_dump_json()
    except TimeoutError:
        status, error = "timed_out", "PROVIDER_TIMEOUT"
    except (ValidationError, ValueError, TypeError):
        status, error = "invalid_output", "INVALID_PROVIDER_OUTPUT"
    except Exception:
        status, error = "failed", "PROVIDER_ERROR"
    latency = int((time.monotonic() - started) * 1000)
    usage = {"mode": "mock", "tokens": 0, "cost": 0}
    async with database.sessions() as session, session.begin():
        # Stale workers may have lost their lease; never publish their output.
        current = await session.scalar(
            text("""SELECT 1 FROM app.jobs WHERE id=:id
            AND status='running' AND lease_token=:token
            AND lease_expires_at>clock_timestamp() FOR UPDATE"""),
            {"id": job["id"], "token": job["lease_token"]},
        )
        if not current:
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
        await session.execute(
            text("""UPDATE app.quota_reservations SET
            status=:status,actual_tokens=0,settled_at=clock_timestamp()
            WHERE analysis_id=:id AND status='reserved'"""),
            {"status": "consumed" if status == "succeeded" else "released", "id": analysis_id},
        )

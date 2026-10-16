"""Short transactions around retrieval/generation; no network while holding domain locks."""

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.analysis.models import AnalysisResult, QuestionResult
from app.analysis.provider import AnalysisInput
from app.db.session import Database
from app.knowledge.generation import generate, redact, validate_result
from app.knowledge.rag import freeze, revoked
from app.worker.fencing import lock_domain, require_lease


async def answer_job(database: Database, job: dict[str, Any]) -> None:
    aid = UUID(job["payload"]["analysis_id"])
    attempt = uuid4()
    async with database.sessions() as s, s.begin():
        if not await lock_domain(s, job):
            return
        row = (
            (
                await s.execute(
                    text("SELECT * FROM app.analyses WHERE id=:id FOR UPDATE"), {"id": aid}
                )
            )
            .mappings()
            .one()
        )
        if row["status"] not in {"queued", "running"}:
            return
        evidence = (
            (
                await s.execute(
                    text("""SELECT e.id,e.source,e.username,e.request_json AS request,
            e.response_json AS response,e.log_json AS log
            FROM app.analysis_evidence ae JOIN app.events e
            ON e.run_id=ae.run_id AND e.id=ae.event_id
            WHERE ae.analysis_id=:id ORDER BY e.release_seq"""),
                    {"id": aid},
                )
            )
            .mappings()
            .all()
        )
        data = AnalysisInput.model_validate(
            {
                "analysis_id": aid,
                "evidence": [dict(e) for e in evidence],
                "prompt_version": row["prompt_version"],
                "max_output_tokens": 1200,
            }
        )
        existing = bool(
            await s.scalar(text("SELECT id FROM app.retrievals WHERE analysis_id=:id"), {"id": aid})
        )
        profile = await s.scalar(
            text("SELECT profile_id FROM kb.releases WHERE id=:id"),
            {"id": row["knowledge_release_id"]},
        )
        await s.execute(
            text("""UPDATE app.analyses SET status='running',
            started_at=coalesce(started_at,clock_timestamp()),version=version+1 WHERE id=:id"""),
            {"id": aid},
        )
        await s.execute(
            text("""INSERT INTO app.analysis_attempts
            (id,run_id,analysis_id,attempt_no,status) VALUES (:id,:run,:aid,:number,'running')"""),
            {"id": attempt, "run": row["run_id"], "aid": aid, "number": job["attempts"]},
        )
        await require_lease(s, job)
    result, retrieval = None, None
    status, error = "succeeded", None
    try:

        async def execute() -> tuple[AnalysisResult | QuestionResult, dict[str, Any]]:
            async with database.sessions() as s:
                await require_lease(s, job)
                if await revoked(s, row["knowledge_release_id"]):
                    raise ValueError("KNOWLEDGE_REVOKED")
            real = row["mode"] == "real"
            if real != (profile == "gemini-embedding-2-768-v1"):
                raise RuntimeError("PINNED_RAG_PROVIDER_MISMATCH")
            query = row["question_text"] or " ".join(
                str(e["log"].get("event_type", "")) for e in evidence
            )
            query = redact(query)
            vector = None
            if real and not existing:
                from app.knowledge.gemini import embed

                vector = await embed(database, aid, query)
            async with database.sessions() as s, s.begin():
                if not await lock_domain(s, job):
                    raise RuntimeError("LEASE_LOST")
                snapshot = await freeze(s, row, query, vector)
                await require_lease(s, job)
            async with database.sessions() as s:
                await require_lease(s, job)
                if await revoked(s, row["knowledge_release_id"]):
                    raise ValueError("KNOWLEDGE_REVOKED")

            async def guard() -> None:
                async with database.sessions() as check:
                    await require_lease(check, job)
                    if await revoked(check, row["knowledge_release_id"]):
                        raise ValueError("KNOWLEDGE_REVOKED")

            if real:
                output = await generate(
                    data, row["question_text"], snapshot, database, dispatch_guard=guard
                )
            else:
                output = await generate(data, row["question_text"], snapshot)

            return output, snapshot

        result, retrieval = await asyncio.wait_for(execute(), 28)
    except TimeoutError:
        status, error = "timed_out", "PROVIDER_TIMEOUT"
    except ValueError as exc:
        status, error = (
            "invalid_output",
            "KNOWLEDGE_REVOKED" if str(exc) == "KNOWLEDGE_REVOKED" else "INVALID_PROVIDER_OUTPUT",
        )
    except Exception:
        status, error = "failed", "RAG_UNAVAILABLE"
    async with database.sessions() as s, s.begin():
        if not await lock_domain(s, job):
            return
        await s.execute(
            text("""SELECT v.id FROM kb.versions v JOIN kb.members m ON m.version_id=v.id
            WHERE m.release_id=:id ORDER BY v.id FOR SHARE OF v"""),
            {"id": row["knowledge_release_id"]},
        )
        if await revoked(s, row["knowledge_release_id"]):
            result, status, error = None, "failed", "KNOWLEDGE_REVOKED"
        if result is not None and retrieval is not None:
            refs = validate_result(
                result,
                {e.id for e in data.evidence},
                {UUID(str(i["retrieval_item_id"])) for i in retrieval["citations"]},
            )
            for ref in refs:
                await s.execute(
                    text("""INSERT INTO app.analysis_knowledge_refs
                    (run_id,analysis_id,retrieval_item_id) VALUES (:run,:aid,:ref)"""),
                    {"run": row["run_id"], "aid": aid, "ref": ref},
                )
        usage = {"mode": row["mode"], "components": []}
        calls = (
            (
                await s.execute(
                    text(
                        "SELECT component,status,actual_tokens FROM app.provider_calls "
                        "WHERE analysis_id=:id"
                    ),
                    {"id": aid},
                )
            )
            .mappings()
            .all()
        )
        for component in ("query_embedding", "generation"):
            call = next((c for c in calls if c["component"] == component), None)
            state = call["status"] if call else "released" if row["mode"] == "real" else "consumed"
            if (
                component == "generation"
                and retrieval
                and retrieval["status"] == "no_match"
                and row["kind"] == "question"
            ):
                state = "released"
            actual = call["actual_tokens"] if call else 0
            await s.execute(
                text("""UPDATE app.quota_components SET status=:state,actual_tokens=:actual,
                measured_cost=:cost WHERE analysis_id=:id AND component=:component"""),
                {
                    "id": aid,
                    "component": component,
                    "state": state,
                    "actual": actual,
                    "cost": None if state == "unknown" else 0,
                },
            )
            usage["components"].append(
                {
                    "component": component,
                    "status": state,
                    "actual_tokens": actual,
                    "measured_cost": None if state == "unknown" else 0,
                }
            )
        await s.execute(
            text("""UPDATE app.analyses SET status=:status,result_json=CAST(:result AS jsonb),
            error_code=:error,finished_at=clock_timestamp(),version=version+1,
            usage_json=CAST(:usage AS jsonb)
            WHERE id=:id"""),
            {
                "id": aid,
                "status": status,
                "error": error,
                "usage": json.dumps(usage),
                "result": result.model_dump_json() if result else None,
            },
        )
        await s.execute(
            text("""UPDATE app.analysis_attempts SET status=:status,error_code=:error,
            finished_at=clock_timestamp(),usage_json=CAST(:usage AS jsonb) WHERE id=:id"""),
            {"id": attempt, "status": status, "error": error, "usage": json.dumps(usage)},
        )
        ledgers = (
            (
                await s.execute(
                    text("""SELECT l.id FROM app.quota_ledgers l
            JOIN app.quota_reservations q ON q.ledger_id=l.id WHERE q.analysis_id=:id
            AND q.status='reserved' ORDER BY l.scope_key,l.period_start FOR UPDATE OF l"""),
                    {"id": aid},
                )
            )
            .scalars()
            .all()
        )
        unknown = any(c["status"] == "unknown" for c in calls)
        known_tokens = 0 if unknown else sum(c["actual_tokens"] or 0 for c in calls)
        for ledger in ledgers:
            await s.execute(
                text(
                    "UPDATE app.quota_ledgers SET consumed_tokens=consumed_tokens+:tokens,"
                    "version=version+1 WHERE id=:id"
                ),
                {"id": ledger, "tokens": known_tokens},
            )
        unknown = any(c["status"] == "unknown" for c in calls)
        await s.execute(
            text("""UPDATE app.quota_reservations SET status=:status,actual_tokens=:tokens,
            settled_at=clock_timestamp() WHERE analysis_id=:id AND status='reserved'"""),
            {
                "id": aid,
                "status": "unknown" if unknown else "consumed",
                "tokens": None if unknown else sum(c["actual_tokens"] or 0 for c in calls),
            },
        )
        await require_lease(s, job)

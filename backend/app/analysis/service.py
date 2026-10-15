"""Quota reservation and immutable analysis admission."""

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthError


async def analysis_view(session: AsyncSession, row: Mapping[Any, Any]) -> dict[str, Any]:
    ids = (
        (
            await session.execute(
                text("""SELECT event_id FROM app.analysis_evidence
        WHERE analysis_id=:analysis ORDER BY event_id"""),
                {"analysis": row["id"]},
            )
        )
        .scalars()
        .all()
    )
    return {
        key: row[key]
        for key in (
            "id",
            "run_id",
            "retry_of",
            "mode",
            "model_id",
            "prompt_version",
            "status",
            "version",
            "error_code",
            "created_at",
            "finished_at",
        )
    } | {"evidence_ids": list(ids), "result": row["result_json"], "usage": row["usage_json"]}


async def reserve_quota(
    session: AsyncSession,
    owner: UUID,
    run_id: UUID,
    analysis_id: UUID,
    experiment: bool = False,
) -> bool:
    column = "experiment_arm_id" if experiment else "analysis_id"
    limit = await session.scalar(
        text("""SELECT daily_ai_requests FROM app.user_quotas
        WHERE user_id=:owner"""),
        {"owner": owner},
    )
    if limit is None:
        raise AuthError(403, "FORBIDDEN")
    today = await session.scalar(text("SELECT (clock_timestamp() AT TIME ZONE 'UTC')::date"))
    scopes = [("system", None), (f"user:{owner}", owner)]
    for scope, user in scopes:
        await session.execute(
            text("""INSERT INTO app.quota_ledgers
            (id,scope_key,user_id,period_start) VALUES (:id,:scope,:user,:day)
            ON CONFLICT(scope_key,period_start) DO NOTHING"""),
            {"id": uuid4(), "scope": scope, "user": user, "day": today},
        )
    ledgers = []
    for scope, _ in scopes:
        row = (
            (
                await session.execute(
                    text("""SELECT id,ai_request_count FROM app.quota_ledgers
            WHERE scope_key=:scope AND period_start=:day FOR UPDATE"""),
                    {"scope": scope, "day": today},
                )
            )
            .mappings()
            .one()
        )
        ledgers.append(row)
    if ledgers[1]["ai_request_count"] >= limit:
        return False
    for ledger in ledgers:
        await session.execute(
            text("""UPDATE app.quota_ledgers SET
            ai_request_count=ai_request_count+1,version=version+1 WHERE id=:id"""),
            {"id": ledger["id"]},
        )
        await session.execute(
            text(f"""INSERT INTO app.quota_reservations
            (id,run_id,{column},ledger_id,reserved_tokens,status)
            VALUES (:id,:run,:analysis,:ledger,0,'reserved')"""),
            {
                "id": uuid4(),
                "run": run_id,
                "analysis": analysis_id,
                "ledger": ledger["id"],
            },
        )
    return True


async def enqueue_analysis(
    session: AsyncSession,
    run_id: UUID,
    owner: UUID,
    correlation: str,
    evidence_hash: str,
    evidence_ids: list[UUID],
    ticket_id: UUID | None = None,
    retry_of: UUID | None = None,
) -> UUID:
    analysis_id = uuid4()
    pinned = (
        (
            await session.execute(
                text("""SELECT r.analysis_mode,rv.model_id,rv.prompt_version
            FROM app.runs r JOIN app.run_versions rv ON rv.run_id=r.id
            WHERE r.id=:run"""),
                {"run": run_id},
            )
        )
        .mappings()
        .one()
    )
    # Every logical request has a fresh attempt group, including API retries.
    await session.execute(
        text("""INSERT INTO app.analyses
        (id,run_id,correlation_key,evidence_hash,attempt_group,retry_of,
         mode,model_id,prompt_version,status)
        VALUES (:id,:run,:correlation,:hash,:group,:retry,
                :mode,:model,:prompt,'queued')"""),
        {
            "id": analysis_id,
            "run": run_id,
            "correlation": correlation,
            "hash": evidence_hash,
            "group": uuid4(),
            "retry": retry_of,
            "mode": pinned["analysis_mode"],
            "model": pinned["model_id"],
            "prompt": pinned["prompt_version"],
        },
    )
    for event_id in evidence_ids:
        await session.execute(
            text("""INSERT INTO app.analysis_evidence
            (run_id,analysis_id,event_id) VALUES (:run,:analysis,:event)"""),
            {"run": run_id, "analysis": analysis_id, "event": event_id},
        )
    if ticket_id is not None:
        await session.execute(
            text("""INSERT INTO app.ticket_analyses
            (run_id,ticket_id,analysis_id) VALUES (:run,:ticket,:analysis)"""),
            {"run": run_id, "ticket": ticket_id, "analysis": analysis_id},
        )
    if not await reserve_quota(session, owner, run_id, analysis_id):
        await session.execute(
            text("""UPDATE app.analyses SET status='quota_exceeded',
            error_code='QUOTA_EXCEEDED',finished_at=clock_timestamp(),version=version+1
            WHERE id=:id"""),
            {"id": analysis_id},
        )
    else:
        await session.execute(
            text("""INSERT INTO app.jobs
            (id,run_id,type,dedupe_key,payload)
            VALUES (:id,:run,'analyze_evidence',:dedupe,CAST(:payload AS jsonb))"""),
            {
                "id": uuid4(),
                "run": run_id,
                "dedupe": f"analysis:{analysis_id}",
                "payload": json.dumps({"analysis_id": str(analysis_id)}),
            },
        )
    return analysis_id

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
    from app.knowledge.rag import retrieval_view

    retrieval, withdrawn = await retrieval_view(session, row)
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
    } | {
        "evidence_ids": list(ids),
        "result": None if withdrawn else row["result_json"],
        "usage": row["usage_json"],
        "kind": row["kind"],
        "question_text": None if withdrawn else row["question_text"],
        "retrieval": retrieval,
        "response_visibility": "withdrawn" if withdrawn else "visible",
    }


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
    reserved_tokens = (
        0
        if experiment
        else int(
            await session.scalar(
                text("""SELECT
        coalesce(sum(reserved_tokens),0) FROM app.quota_components WHERE analysis_id=:id"""),
                {"id": analysis_id},
            )
            or 0
        )
    )
    for ledger in ledgers:
        await session.execute(
            text("""UPDATE app.quota_ledgers SET
            ai_request_count=ai_request_count+1,version=version+1 WHERE id=:id"""),
            {"id": ledger["id"]},
        )
        await session.execute(
            text(f"""INSERT INTO app.quota_reservations
            (id,run_id,{column},ledger_id,reserved_tokens,status)
            VALUES (:id,:run,:analysis,:ledger,:tokens,'reserved')"""),
            {
                "id": uuid4(),
                "run": run_id,
                "analysis": analysis_id,
                "ledger": ledger["id"],
                "tokens": reserved_tokens,
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
    question: str | None = None,
) -> UUID:
    analysis_id = uuid4()
    pinned = (
        (
            await session.execute(
                text("""SELECT r.analysis_mode,rv.model_id,rv.prompt_version,
            rv.knowledge_release_id,rv.retrieval_config_version
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
         mode,model_id,prompt_version,status,kind,question_text,question_hash,ticket_id,
         knowledge_release_id,retrieval_config_version)
        VALUES (:id,:run,:correlation,:hash,:group,:retry,
                :mode,:model,:prompt,'queued',:kind,:question,:question_hash,:ticket,:release,:config)"""),
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
            "kind": "question" if question is not None else "triage",
            "question": question,
            "question_hash": __import__("hashlib").sha256(question.encode()).hexdigest()
            if question is not None
            else None,
            "ticket": ticket_id,
            "release": pinned["knowledge_release_id"],
            "config": pinned["retrieval_config_version"],
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
    if retry_of is not None:
        from app.knowledge.rag import copy_retrieval

        await copy_retrieval(session, retry_of, analysis_id)
    if pinned["knowledge_release_id"] is not None and pinned["analysis_mode"] == "real":
        policy = (
            (await session.execute(text("SELECT * FROM app.provider_policy WHERE id=1 FOR UPDATE")))
            .mappings()
            .one()
        )
        capacity = (
            (
                await session.execute(
                    text("""SELECT
            coalesce(sum(request_units),0) AS requests,coalesce(sum(tokens),0) AS tokens FROM (
              SELECT CASE WHEN status='unknown' THEN reserved_tokens
                ELSE coalesce(actual_tokens,0) END AS tokens,1 AS request_units
                FROM app.provider_calls WHERE status='unknown' OR dispatched_at >=
                  date_trunc('day',clock_timestamp() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
              UNION ALL SELECT c.reserved_tokens,
                  CASE WHEN c.component='generation' THEN 2 ELSE 1 END AS request_units
                FROM app.quota_components c
                JOIN app.analyses a ON a.id=c.analysis_id
                WHERE a.mode='real' AND c.status='reserved'
                AND a.status IN ('queued','running')
                AND NOT EXISTS(SELECT 1 FROM app.provider_calls p
                  WHERE p.analysis_id=c.analysis_id
                  AND p.component=c.component)) reservations""")
                )
            )
            .mappings()
            .one()
        )
        if (
            capacity["requests"] + 3 > policy["daily_requests"]
            or capacity["tokens"] + 48000 > policy["daily_tokens"]
        ):
            # Automatic detector/ticket transactions must commit even when AI
            # capacity is exhausted. HTTP admission translates this resource to 429.
            await session.execute(
                text("""UPDATE app.analyses SET status='quota_exceeded',
                error_code='PROVIDER_BUDGET_EXCEEDED',finished_at=clock_timestamp(),version=version+1
                WHERE id=:id"""),
                {"id": analysis_id},
            )
            return analysis_id
    if pinned["knowledge_release_id"] is not None:
        for component, model, tokens in (
            (
                "query_embedding",
                "gemini-embedding-2" if pinned["analysis_mode"] == "real" else "fake-hash-16-v1",
                16000,
            ),
            ("generation", pinned["model_id"], 32000),
        ):
            await session.execute(
                text("""INSERT INTO app.quota_components
                (analysis_id,component,model_id,reserved_tokens)
                VALUES (:id,:component,:model,:tokens)"""),
                {"id": analysis_id, "component": component, "model": model, "tokens": tokens},
            )
    if not await reserve_quota(session, owner, run_id, analysis_id):
        await session.execute(
            text("""UPDATE app.analyses SET status='quota_exceeded',
            error_code='QUOTA_EXCEEDED',finished_at=clock_timestamp(),version=version+1
            WHERE id=:id"""),
            {"id": analysis_id},
        )
        await session.execute(
            text("UPDATE app.quota_components SET status='released' WHERE analysis_id=:id"),
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

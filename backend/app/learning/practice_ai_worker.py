"""Dispatch post-submission practice questions through the approved Dify release."""

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.db.session import Database
from app.knowledge.dify_client import DifyConfig, DifyUnavailable
from app.knowledge.dify_workflow import run_workflow
from app.knowledge.generation import redact
from app.learning.practice_routes import encoded
from app.tutor.service import (
    NoKnowledgeMatch,
    readiness,
    redact_question,
    release_drift,
    validate_outputs,
)
from app.worker.fencing import LeaseLost, require_lease


async def locked(session: Any, job: dict[str, Any]) -> tuple[Any, Any]:
    identity = UUID(job["payload"]["question_id"])
    owner = await session.scalar(
        text("SELECT owner_user_id FROM app.practice_ai_questions WHERE id=:id"), {"id": identity}
    )
    if owner is None:
        raise LeaseLost("Practice question missing")
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
        {"owner": str(owner)},
    )
    await session.execute(text("SELECT pg_advisory_xact_lock(73102007)"))
    policy = (
        (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1"))).mappings().one()
    )
    row = (
        (
            await session.execute(
                text("SELECT * FROM app.practice_ai_questions WHERE id=:id FOR UPDATE"),
                {"id": identity},
            )
        )
        .mappings()
        .one()
    )
    valid = await session.scalar(
        text("""SELECT id FROM app.jobs WHERE id=:id
        AND type='practice_ai_question' AND run_id IS NULL
        AND payload->>'question_id'=:question AND status='running'
        AND lease_token=:token AND lease_expires_at>clock_timestamp() FOR UPDATE"""),
        {"id": job["id"], "token": job["lease_token"], "question": str(identity)},
    )
    if valid is None:
        raise LeaseLost("Practice question lease lost")
    return row, policy


async def process_practice_question(database: Database, job: dict[str, Any]) -> None:
    async with database.sessions() as session, session.begin():
        row, policy = await locked(session, job)
        if row["status"] not in {"queued", "running"}:
            return
        if row["dispatch_started_at"] is not None:
            await session.execute(
                text("""UPDATE app.practice_ai_questions
                SET status='needs_review',error_code='DIFY_DISPATCH_OUTCOME_UNKNOWN',
                usage_status='unknown',
                finished_at=clock_timestamp() WHERE id=:id"""),
                {"id": row["id"]},
            )
            await require_lease(session, job)
            return
        active_exam = await session.scalar(
            text("""SELECT 1 FROM app.exam_attempts
            WHERE owner_user_id=:owner AND status IN ('in_progress','submitted','needs_review')
            LIMIT 1"""),
            {"owner": row["owner_user_id"]},
        )
        account_active = await session.scalar(
            text("SELECT status='active' FROM app.users WHERE id=:owner"),
            {"owner": row["owner_user_id"]},
        )
        expired = await session.scalar(
            text(
                "SELECT expires_at<=clock_timestamp() FROM app.practice_ai_questions WHERE id=:id"
            ),
            {"id": row["id"]},
        )
        if (
            active_exam
            or not account_active
            or expired
            or not policy["practice_enabled"]
            or readiness(policy)
            or await release_drift(session, policy["version"])
            or policy["version"] != row["policy_version"]
        ):
            await session.execute(
                text("""UPDATE app.practice_ai_questions
                SET status='unavailable',error_code='DIFY_POLICY_OR_EXAM_BLOCKED',
                usage_status='released',
                finished_at=clock_timestamp() WHERE id=:id"""),
                {"id": row["id"]},
            )
            await require_lease(session, job)
            return
        snapshot = (
            (
                await session.execute(
                    text("""SELECT evidence_snapshot FROM app.practice_answers
            WHERE id=:answer AND case_id=:case AND owner_user_id=:owner"""),
                    {
                        "answer": row["answer_id"],
                        "case": row["case_id"],
                        "owner": row["owner_user_id"],
                    },
                )
            )
            .mappings()
            .first()
        )
        if snapshot is None:
            raise LeaseLost("Practice answer missing")
        case = snapshot["evidence_snapshot"]
        # A submitted case snapshot contains learner-visible events, never private truth.
        events = []
        for event in case["events"][:20]:
            events.append(
                {
                    key: event.get(key)
                    for key in (
                        "id",
                        "time",
                        "source",
                        "asset",
                        "username",
                        "src_ip",
                        "request",
                        "response",
                        "log",
                    )
                }
            )
        payload = (
            "คำถาม: " + row["question"] + "\nหลักฐานในเคสที่ส่งคำตอบแล้ว: " + encoded(redact(events))
        )
        payload = redact_question(payload)
        if len(payload) > 24000:
            await session.execute(
                text("""UPDATE app.practice_ai_questions
                SET status='unavailable',error_code='DIFY_CONTEXT_TOO_LONG',
                usage_status='released',
                finished_at=clock_timestamp() WHERE id=:id"""),
                {"id": row["id"]},
            )
            await require_lease(session, job)
            return
        config = DifyConfig.from_env()
        config.read_api_key()
        await session.execute(
            text("""UPDATE app.practice_ai_questions
            SET status='running',dispatch_started_at=clock_timestamp(),usage_status='unknown'
            WHERE id=:id"""),
            {"id": row["id"]},
        )
        await require_lease(session, job)
    result = None
    tokens = None
    error = None
    try:
        reply = await run_workflow(
            config, row["workflow_id"], payload, f"practice-{row['id']}", mode="practice"
        )
        tokens = reply.total_tokens
        result = validate_outputs(reply.outputs, policy["document_ids"], policy["chunk_hashes"])
    except NoKnowledgeMatch:
        error = "DIFY_NO_MATCH"
    except DifyUnavailable as cause:
        error = str(cause)
    except (ValueError, TypeError):
        error = "DIFY_CITATION_OR_OUTPUT_INVALID"
    async with database.sessions() as session, session.begin():
        current, current_policy = await locked(session, job)
        withdrawn = (
            not current_policy["enabled"] or current_policy["version"] != row["policy_version"]
        )
        await session.execute(
            text("""UPDATE app.practice_ai_questions SET
            status=:status,result_json=CAST(:result AS jsonb),error_code=:error,
            reported_tokens=:tokens,
            usage_status=CASE WHEN :accounted THEN 'reconciled' ELSE usage_status END,
            finished_at=clock_timestamp() WHERE id=:id"""),
            {
                "id": current["id"],
                "status": "withdrawn"
                if withdrawn
                else "succeeded"
                if result
                else "unavailable"
                if error == "DIFY_NO_MATCH"
                else "needs_review",
                "result": encoded(result.model_dump()) if result and not withdrawn else None,
                "error": "KNOWLEDGE_WITHDRAWN" if withdrawn else error,
                "tokens": tokens,
                "accounted": tokens is not None and current_policy["cost_bound_verified"],
            },
        )
        await require_lease(session, job)

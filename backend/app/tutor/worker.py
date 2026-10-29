"""At-most-one external dispatch per question; ambiguous outcomes retain cost holds."""

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.db.session import Database
from app.knowledge.dify_client import DifyConfig, DifyUnavailable
from app.knowledge.dify_workflow import run_workflow
from app.knowledge.generation import redact
from app.learning.practice_routes import encoded
from app.tutor.service import NoKnowledgeMatch, readiness, release_drift, validate_outputs
from app.worker.fencing import require_lease


async def locked(session: Any, job: dict[str, Any]) -> tuple[Any, Any]:
    identity = UUID(job["payload"]["question_id"])
    owner = await session.scalar(
        text("SELECT owner_user_id FROM app.tutor_questions WHERE id=:id"), {"id": identity}
    )
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
                text("SELECT * FROM app.tutor_questions WHERE id=:id FOR UPDATE"), {"id": identity}
            )
        )
        .mappings()
        .one()
    )
    valid = await session.scalar(
        text("""SELECT id FROM app.jobs WHERE id=:id
        AND type='tutor_question' AND run_id IS NULL AND payload->>'question_id'=:question
        AND status='running' AND lease_token=:token
        AND lease_expires_at>clock_timestamp() FOR UPDATE"""),
        {"id": job["id"], "token": job["lease_token"], "question": str(identity)},
    )
    if valid is None:
        from app.worker.fencing import LeaseLost

        raise LeaseLost("Tutor lease lost")
    return row, policy


async def process_question(database: Database, job: dict[str, Any]) -> None:
    async with database.sessions() as session, session.begin():
        row, policy = await locked(session, job)
        if row["status"] not in {"queued", "running"}:
            return
        active = await session.scalar(
            text("""SELECT 1 FROM app.exam_attempts WHERE owner_user_id=:owner
            AND status IN ('in_progress','submitted','needs_review') LIMIT 1"""),
            {"owner": row["owner_user_id"]},
        )
        if row["dispatch_started_at"] is not None:
            # A prior process might have sent the request before crashing. Never replay it.
            await session.execute(
                text("""UPDATE app.tutor_questions SET status='needs_review',
                error_code='DIFY_DISPATCH_OUTCOME_UNKNOWN',finished_at=clock_timestamp()
                WHERE id=:id"""),
                {"id": row["id"]},
            )
            await require_lease(session, job)
            return
        account_active = await session.scalar(
            text("SELECT status='active' FROM app.users WHERE id=:owner"),
            {"owner": row["owner_user_id"]},
        )
        expired = await session.scalar(
            text("SELECT expires_at<=clock_timestamp() FROM app.tutor_questions WHERE id=:id"),
            {"id": row["id"]},
        )
        if (
            active
            or not account_active
            or expired
            or readiness(policy)
            or await release_drift(session, policy["version"])
            or policy["version"] != row["policy_version"]
        ):
            await session.execute(
                text("""UPDATE app.tutor_questions SET status='unavailable',
                error_code='DIFY_POLICY_OR_EXAM_BLOCKED',usage_status='released',
                finished_at=clock_timestamp() WHERE id=:id"""),
                {"id": row["id"]},
            )
            await require_lease(session, job)
            return
        config = DifyConfig.from_env()
        # Credential failures happen before marking a possible dispatch.
        config.read_api_key()
        await session.execute(
            text("""UPDATE app.tutor_questions SET status='running',
            dispatch_started_at=clock_timestamp(),usage_status='unknown' WHERE id=:id"""),
            {"id": row["id"]},
        )
        await require_lease(session, job)
    result = None
    tokens = None
    error = None
    accounted = False
    try:
        args = (config, row["workflow_id"], redact(row["question"]), f"tutor-{row['id']}")
        reply = (
            await run_workflow(*args, mode="tutor")
            if policy["grade_enabled"]
            else await run_workflow(*args)
        )
        tokens = reply.total_tokens
        # Account the entire verified per-call ceiling, not an invented $0 bill.
        # Unknown/mismatched dispatches retain their hold across UTC days.
        accounted = tokens is not None and policy["cost_bound_verified"]
        result = validate_outputs(reply.outputs, policy["document_ids"], policy["chunk_hashes"])
    except NoKnowledgeMatch:
        error = "DIFY_NO_MATCH" if tokens == 0 else "DIFY_CITATION_OR_OUTPUT_INVALID"
    except DifyUnavailable as cause:
        error = str(cause)
    except (ValueError, TypeError):
        error = "DIFY_CITATION_OR_OUTPUT_INVALID"
    async with database.sessions() as session, session.begin():
        current, current_policy = await locked(session, job)
        withdrawn = (
            not current_policy["enabled"] or current_policy["version"] != row["policy_version"]
        )
        status = (
            "withdrawn"
            if withdrawn
            else "succeeded"
            if result is not None
            else "unavailable"
            if error == "DIFY_NO_MATCH"
            else "needs_review"
        )
        await session.execute(
            text("""UPDATE app.tutor_questions SET status=:status,
            result_json=CAST(:result AS jsonb),error_code=:error,reported_tokens=:tokens,
            usage_status=CASE WHEN :accounted THEN 'reconciled' ELSE usage_status END,
            finished_at=clock_timestamp() WHERE id=:id"""),
            {
                "id": current["id"],
                "status": status,
                "result": encoded(result.model_dump())
                if result is not None and not withdrawn
                else None,
                "error": "KNOWLEDGE_WITHDRAWN" if withdrawn else error,
                "tokens": tokens,
                "accounted": accounted,
            },
        )
        # reserved_usd remains the full upper bound, including retrieval. Never
        # reduce it to zero from token usage or release an ambiguous dispatch.
        await require_lease(session, job)

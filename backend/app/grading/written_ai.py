"""Advisory feedback for frozen written answers using the lesson Dify workflow."""

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import text

from app.auth import service as auth
from app.auth.routes import json_only
from app.db.session import Database
from app.http_models import Meta, StrictModel
from app.input_validation import InputModel
from app.knowledge.dify_client import DifyConfig, DifyUnavailable
from app.knowledge.dify_workflow import run_workflow
from app.learning.practice_routes import encoded, learner
from app.tutor.models import TutorSource
from app.tutor.service import (
    answer_without_reasoning,
    readiness,
    redact_question,
    release_drift,
    reserve_logical_request,
)
from app.worker.fencing import require_lease

router = APIRouter(
    prefix="/api/v1/learning/levels/{level_id}/written-submissions",
    dependencies=[Depends(json_only)],
    include_in_schema=False,
)


class FeedbackItem(StrictModel):
    question_id: UUID
    verdict: Literal["supported", "unsupported", "insufficient"]
    explanation: str = Field(min_length=1, max_length=1000)
    section_ids: list[str] = Field(max_length=5)


class FeedbackResult(StrictModel):
    items: list[FeedbackItem] = Field(min_length=10, max_length=10)
    sources: list[TutorSource] = Field(min_length=1, max_length=5)


class FeedbackView(StrictModel):
    submission_id: UUID
    status: Literal["queued", "running", "succeeded", "needs_review", "unavailable", "withdrawn"]
    result: FeedbackResult | None
    error_code: str | None
    created_at: datetime


class FeedbackEnvelope(StrictModel):
    data: FeedbackView
    meta: Meta


class FeedbackRequest(InputModel):
    pass


def view(row: Any, policy: Any) -> FeedbackView:
    withdrawn = (
        not policy["enabled"]
        or not policy["grade_enabled"]
        or policy["version"] != row["policy_version"]
        or policy["corpus_revision"] != row["corpus_revision"]
    )
    if row["result_json"] is not None:
        for source in row["result_json"]["sources"]:
            if (
                source["document_id"] not in policy["document_ids"]
                or hashlib.sha256(source["excerpt"].encode()).hexdigest()
                not in policy["chunk_hashes"]
            ):
                withdrawn = True
    return FeedbackView(
        submission_id=row["submission_id"],
        status="withdrawn" if withdrawn else row["status"],
        result=None if withdrawn else row["result_json"],
        error_code="KNOWLEDGE_WITHDRAWN" if withdrawn else row["error_code"],
        created_at=row["created_at"],
    )


def validate_feedback(outputs: dict[str, Any], submission: Any, policy: Any) -> FeedbackResult:
    raw = outputs.get("answer")
    sources = outputs.get("sources")
    if not isinstance(raw, str) or len(raw) > 12000 or not isinstance(sources, list):
        raise ValueError("Invalid grade output")
    raw = answer_without_reasoning(raw)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != {"items"}:
        raise ValueError("Invalid grade schema")
    allowed_sections: set[str] = set()
    approved_sources: list[TutorSource] = []
    if not 1 <= len(sources) <= 5:
        raise ValueError("Feedback sources required")
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("metadata"), dict):
            raise ValueError("Invalid source")
        content = source.get("content")
        if (
            source["metadata"].get("document_id") not in policy["document_ids"]
            or not isinstance(content, str)
            or hashlib.sha256(content.encode()).hexdigest() not in policy["chunk_hashes"]
        ):
            raise ValueError("Unapproved source")
        allowed_sections.update(re.findall(r"\bSOC-\d{3}\b", content))
        title = source.get("title")
        if not isinstance(title, str) or not 1 <= len(title) <= 500:
            raise ValueError("Invalid source title")
        approved_sources.append(
            TutorSource(
                document_id=source["metadata"]["document_id"],
                title=title,
                excerpt=content,
                section_ids=sorted(set(re.findall(r"\bSOC-\d{3}\b", content))),
            )
        )
    result = FeedbackResult.model_validate({"items": parsed["items"], "sources": approved_sources})
    expected = {UUID(item["id"]) for item in submission["question_snapshot"]}
    actual = [item.question_id for item in result.items]
    if len(set(actual)) != 10 or set(actual) != expected:
        raise ValueError("Feedback question mismatch")
    for item in result.items:
        if not item.section_ids or not set(item.section_ids).issubset(allowed_sections):
            raise ValueError("Unsupported citation")
        if set(re.findall(r"\bSOC-\d{3}\b", item.explanation)) - set(item.section_ids):
            raise ValueError("Unlisted citation")
        if re.search(r"https?://", item.explanation):
            raise ValueError("URLs are not supported in feedback")
    return result


async def owned_submission(session: Any, owner: UUID, level: UUID, submission_id: UUID) -> Any:
    row = (
        (
            await session.execute(
                text("""SELECT * FROM app.written_submissions
                WHERE id=:id AND owner_user_id=:owner AND level_id=:level"""),
                {"id": submission_id, "owner": owner, "level": level},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise auth.AuthError(404, "NOT_FOUND")
    return row


@router.post("/{submission_id}/feedback", response_model=FeedbackEnvelope, status_code=202)
async def request_feedback(
    level_id: UUID, submission_id: UUID, body: FeedbackRequest, request: Request
) -> FeedbackEnvelope:
    await auth.rate_limit(request, "tutor_write")
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request, write=True)
        await owned_submission(session, user["id"], level_id, submission_id)
        await session.execute(text("SELECT pg_advisory_xact_lock(73102007)"))
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        existing = (
            (
                await session.execute(
                    text("SELECT * FROM app.written_feedback WHERE submission_id=:id"),
                    {"id": submission_id},
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            data = view(existing, policy)
        else:
            if not policy["grade_enabled"] or readiness(policy):
                raise auth.AuthError(503, "DIFY_GRADE_NOT_APPROVED")
            if await release_drift(session, policy["version"]):
                raise auth.AuthError(503, "DIFY_WORKFLOW_VERSION_MISMATCH")
            await reserve_logical_request(session, user["id"])
            row = (
                (
                    await session.execute(
                        text("""INSERT INTO app.written_feedback
                        (submission_id,owner_user_id,policy_version,workflow_id,
                         corpus_revision,reserved_usd)
                        VALUES (:id,:owner,:version,:workflow,:corpus,:cost) RETURNING *"""),
                        {
                            "id": submission_id,
                            "owner": user["id"],
                            "version": policy["version"],
                            "workflow": policy["workflow_id"],
                            "corpus": policy["corpus_revision"],
                            "cost": policy["grade_call_bound_usd"],
                        },
                    )
                )
                .mappings()
                .one()
            )
            await session.execute(
                text("""INSERT INTO app.jobs(id,type,dedupe_key,payload)
                VALUES (:id,'written_feedback',:dedupe,CAST(:payload AS jsonb))"""),
                {
                    "id": uuid4(),
                    "dedupe": f"written-feedback:{submission_id}",
                    "payload": encoded({"submission_id": str(submission_id)}),
                },
            )
            await auth.audit(session, "written.feedback.request", user["id"], request)
            data = view(row, policy)
    return FeedbackEnvelope(data=data, meta=Meta(request_id=request.state.request_id))


@router.get("/{submission_id}/feedback", response_model=FeedbackEnvelope)
async def get_feedback(level_id: UUID, submission_id: UUID, request: Request) -> FeedbackEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        await owned_submission(session, user["id"], level_id, submission_id)
        row = (
            (
                await session.execute(
                    text("SELECT * FROM app.written_feedback WHERE submission_id=:id"),
                    {"id": submission_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise auth.AuthError(404, "NOT_FOUND")
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        data = view(row, policy)
    return FeedbackEnvelope(data=data, meta=Meta(request_id=request.state.request_id))


async def process_feedback(database: Database, job: dict[str, Any]) -> None:
    submission_id = UUID(job["payload"]["submission_id"])
    async with database.sessions() as session, session.begin():
        owner = await session.scalar(
            text("SELECT owner_user_id FROM app.written_feedback WHERE submission_id=:id"),
            {"id": submission_id},
        )
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
            {"owner": str(owner)},
        )
        await session.execute(text("SELECT pg_advisory_xact_lock(73102007)"))
        row = (
            (
                await session.execute(
                    text("SELECT * FROM app.written_feedback WHERE submission_id=:id FOR UPDATE"),
                    {"id": submission_id},
                )
            )
            .mappings()
            .one()
        )
        await require_lease(session, job)
        if row["status"] not in {"queued", "running"}:
            return
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        if row["dispatch_started_at"] is not None:
            await session.execute(
                text("""UPDATE app.written_feedback SET status='needs_review',
                error_code='DIFY_DISPATCH_OUTCOME_UNKNOWN',finished_at=clock_timestamp()
                WHERE submission_id=:id"""),
                {"id": submission_id},
            )
            await require_lease(session, job)
            return
        if (
            not policy["grade_enabled"]
            or readiness(policy)
            or policy["version"] != row["policy_version"]
        ):
            await session.execute(
                text("""UPDATE app.written_feedback SET status='unavailable',
                error_code='DIFY_POLICY_UNAVAILABLE',finished_at=clock_timestamp()
                WHERE submission_id=:id"""),
                {"id": submission_id},
            )
            await require_lease(session, job)
            return
        submission = (
            (
                await session.execute(
                    text("SELECT * FROM app.written_submissions WHERE id=:id"),
                    {"id": submission_id},
                )
            )
            .mappings()
            .one()
        )
        try:
            config = DifyConfig.from_env()
            config.read_api_key()
        except DifyUnavailable as cause:
            await session.execute(
                text("""UPDATE app.written_feedback SET status='unavailable',
                error_code=:error,finished_at=clock_timestamp()
                WHERE submission_id=:id"""),
                {"id": submission_id, "error": str(cause)},
            )
            await require_lease(session, job)
            return
        await session.execute(
            text("""UPDATE app.written_feedback SET status='running',
            dispatch_started_at=clock_timestamp() WHERE submission_id=:id"""),
            {"id": submission_id},
        )
        await require_lease(session, job)
    question = encoded(
        {
            "questions": [
                {
                    "id": item["id"],
                    "prompt": item["prompt"],
                    "answer": next(
                        answer["answer"]
                        for answer in submission["answers_json"]
                        if answer["question_id"] == item["id"]
                    ),
                }
                for item in submission["question_snapshot"]
            ]
        }
    )
    result: FeedbackResult | None = None
    error: str | None = None
    tokens: int | None = None
    try:
        reply = await run_workflow(
            config,
            row["workflow_id"],
            redact_question(question),
            f"grade-{submission_id}",
            mode="grade",
        )
        tokens = reply.total_tokens
        result = validate_feedback(reply.outputs, submission, policy)
    except (DifyUnavailable, ValueError, TypeError, KeyError, StopIteration) as cause:
        error = str(cause) if isinstance(cause, DifyUnavailable) else "DIFY_GRADE_INVALID"
    async with database.sessions() as session, session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
            {"owner": str(row["owner_user_id"])},
        )
        await session.execute(text("SELECT pg_advisory_xact_lock(73102007)"))
        current = (
            (
                await session.execute(
                    text("SELECT * FROM app.written_feedback WHERE submission_id=:id FOR UPDATE"),
                    {"id": submission_id},
                )
            )
            .mappings()
            .one()
        )
        current_policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        withdrawn = (
            not current_policy["enabled"]
            or not current_policy["grade_enabled"]
            or current_policy["version"] != row["policy_version"]
        )
        await session.execute(
            text("""UPDATE app.written_feedback SET status=:status,
            result_json=CAST(:result AS jsonb),error_code=:error,
            reported_tokens=:tokens,finished_at=clock_timestamp()
            WHERE submission_id=:id"""),
            {
                "id": current["submission_id"],
                "status": "withdrawn" if withdrawn else "succeeded" if result else "needs_review",
                "result": encoded(result.model_dump(mode="json"))
                if result and not withdrawn
                else None,
                "error": "KNOWLEDGE_WITHDRAWN" if withdrawn else error,
                "tokens": tokens,
            },
        )
        await require_lease(session, job)

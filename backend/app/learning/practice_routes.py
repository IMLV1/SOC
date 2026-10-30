"""Account-backed training. No local fixtures or answer keys enter public serializers."""

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth
from app.auth.routes import json_only
from app.exams.routes import key_from_header
from app.http_models import ErrorEnvelope, Meta
from app.learning.access import require_level, require_no_exam
from app.learning.practice_models import (
    AnswerEnvelope,
    AnswerView,
    CaseEnvelope,
    DraftInput,
    HistoryEnvelope,
    PracticeAIEnvelope,
    PracticeAIHistory,
    PracticeAIInput,
    PracticeAIView,
    PracticeAnswer,
    PracticeCase,
    PracticeCatalog,
    PracticeSummary,
    QuestionsEnvelope,
    WrittenEnvelope,
    WrittenHistory,
    WrittenInput,
    WrittenQuestion,
    WrittenView,
)
from app.tutor.models import AvailabilityEnvelope, TutorAvailability

router = APIRouter(
    prefix="/api/v1",
    tags=["Database training"],
    dependencies=[Depends(json_only)],
    include_in_schema=False,
    responses={
        status: {"model": ErrorEnvelope} for status in (400, 401, 403, 404, 409, 422, 429, 503)
    },
)


def meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(encoded(value).encode()).hexdigest()


async def learner(session: AsyncSession, request: Request, *, write: bool = False) -> Any:
    user = await auth.require_user(session, request)
    if user["role"] != "analyst":
        raise auth.AuthError(403, "FORBIDDEN")
    if write:
        await auth.csrf_check(session, request)
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
            {"owner": str(user["id"])},
        )
    await require_no_exam(session, user["id"])
    return user


async def case_row(session: AsyncSession, case_id: UUID, owner: UUID) -> Any:
    row = (
        (
            await session.execute(
                text("""SELECT c.id,c.stable_key,c.level_id,l.ordinal AS level,
        c.category,c.title,c.version,c.content_json FROM app.practice_cases c
        JOIN app.learning_levels l ON l.id=c.level_id
        WHERE c.id=:id AND c.enabled AND c.published_at<=now()"""),
                {"id": case_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise auth.AuthError(404, "NOT_FOUND")
    await require_level(session, owner, row["level_id"])
    return row


def summary(row: Any) -> dict[str, object]:
    return {
        key: row[key]
        for key in ("id", "stable_key", "level_id", "level", "category", "title", "version")
    } | {"available": True}


def validate_evidence(answer: Any, case: Any) -> None:
    allowed = {item["id"] for item in case["content_json"]["events"]}
    if any(str(item) not in allowed for item in answer.evidence_ids):
        raise auth.AuthError(422, "INVALID_EVIDENCE")


def answer_view(row: Any) -> AnswerView:
    return AnswerView(
        id=row["id"],
        case_id=row["case_id"],
        case_version=row["case_version"],
        answer=row["answer_json"],
        feedback=row["feedback_json"],
        created_at=row["created_at"],
    )


def practice_ai_view(row: Any, policy: Any) -> PracticeAIView:
    withdrawn = (
        not policy["enabled"]
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
    return PracticeAIView(
        id=row["id"],
        case_id=row["case_id"],
        answer_id=row["answer_id"],
        question=row["question"],
        status="withdrawn" if withdrawn else row["status"],
        result=None if withdrawn else row["result_json"],
        error_code="KNOWLEDGE_WITHDRAWN" if withdrawn else row["error_code"],
        created_at=row["created_at"],
    )


@router.get("/practice/ai-availability", response_model=AvailabilityEnvelope)
async def practice_ai_availability(request: Request) -> AvailabilityEnvelope:
    from app.tutor.service import readiness, release_drift

    async with auth.database(request).sessions() as session, session.begin():
        await learner(session, request)
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        reason = (
            "DIFY_PRACTICE_NOT_APPROVED" if not policy["practice_enabled"] else readiness(policy)
        )
        if reason is None and await release_drift(session, policy["version"]):
            reason = "DIFY_WORKFLOW_VERSION_MISMATCH"
    return AvailabilityEnvelope(
        data=TutorAvailability(available=reason is None, reason=reason), meta=meta(request)
    )


@router.post(
    "/practice/cases/{case_id}/ai-questions", response_model=PracticeAIEnvelope, status_code=202
)
async def ask_practice_ai(
    case_id: UUID,
    body: PracticeAIInput,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> PracticeAIEnvelope:
    from app.tutor.quota import reserve_logical_request
    from app.tutor.service import readiness, redact_question, release_drift

    key = key_from_header(idempotency_key)
    await auth.rate_limit(request, "tutor_write")
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request, write=True)
        await case_row(session, case_id, user["id"])
        answer = await session.scalar(
            text("""SELECT id FROM app.practice_answers
            WHERE id=:id AND case_id=:case AND owner_user_id=:owner"""),
            {"id": body.answer_id, "case": case_id, "owner": user["id"]},
        )
        if answer is None:
            raise auth.AuthError(404, "NOT_FOUND")
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        fingerprint = digest(body.model_dump(mode="json"))
        previous = (
            (
                await session.execute(
                    text("""SELECT * FROM app.practice_ai_questions
            WHERE owner_user_id=:owner AND idempotency_key=:key"""),
                    {"owner": user["id"], "key": key},
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != fingerprint or previous["case_id"] != case_id:
                raise auth.AuthError(409, "IDEMPOTENCY_CONFLICT")
            return PracticeAIEnvelope(data=practice_ai_view(previous, policy), meta=meta(request))
        if not policy["practice_enabled"]:
            raise auth.AuthError(503, "DIFY_PRACTICE_NOT_APPROVED")
        reason = readiness(policy)
        if reason or await release_drift(session, policy["version"]):
            raise auth.AuthError(503, reason or "DIFY_WORKFLOW_VERSION_MISMATCH")
        await reserve_logical_request(session, user["id"])
        question_id = uuid4()
        row = (
            (
                await session.execute(
                    text("""INSERT INTO app.practice_ai_questions
            (id,owner_user_id,case_id,answer_id,question,idempotency_key,request_hash,
             policy_version,workflow_id,corpus_revision,reserved_usd)
            VALUES(:id,:owner,:case,:answer,:question,:key,:hash,:version,:workflow,:corpus,:cost)
            RETURNING *"""),
                    {
                        "id": question_id,
                        "owner": user["id"],
                        "case": case_id,
                        "answer": body.answer_id,
                        "question": redact_question(body.question),
                        "key": key,
                        "hash": fingerprint,
                        "version": policy["version"],
                        "workflow": policy["workflow_id"],
                        "corpus": policy["corpus_revision"],
                        "cost": policy["practice_call_bound_usd"],
                    },
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            text("""INSERT INTO app.jobs(id,type,dedupe_key,payload)
            VALUES(:id,'practice_ai_question',:dedupe,CAST(:payload AS jsonb))"""),
            {
                "id": uuid4(),
                "dedupe": f"practice-ai:{question_id}",
                "payload": encoded({"question_id": str(question_id)}),
            },
        )
        await auth.audit(session, "practice.ai_question", user["id"], request)
    return PracticeAIEnvelope(data=practice_ai_view(row, policy), meta=meta(request))


@router.get("/practice/cases/{case_id}/ai-questions", response_model=PracticeAIHistory)
async def practice_ai_history(case_id: UUID, request: Request) -> PracticeAIHistory:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        await case_row(session, case_id, user["id"])
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        rows = (
            (
                await session.execute(
                    text("""SELECT * FROM app.practice_ai_questions
            WHERE owner_user_id=:owner AND case_id=:case AND expires_at>now()
            ORDER BY created_at DESC,id DESC LIMIT 20"""),
                    {"owner": user["id"], "case": case_id},
                )
            )
            .mappings()
            .all()
        )
    return PracticeAIHistory(
        data=[practice_ai_view(row, policy) for row in rows], meta=meta(request)
    )


@router.get("/practice/cases", response_model=PracticeCatalog)
async def catalog(request: Request) -> PracticeCatalog:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        rows = (
            (
                await session.execute(
                    text("""SELECT c.id,c.stable_key,c.level_id,l.ordinal AS level,
            c.category,c.title,c.version,(l.ordinal=1 OR EXISTS(SELECT 1 FROM app.level_unlocks u
                WHERE u.user_id=:owner AND u.level_id=l.id)) AS available
            FROM app.practice_cases c JOIN app.learning_levels l ON l.id=c.level_id
            WHERE c.enabled AND l.enabled AND c.published_at<=now()
            ORDER BY l.ordinal,c.stable_key"""),
                    {"owner": user["id"]},
                )
            )
            .mappings()
            .all()
        )
    return PracticeCatalog(
        data=[PracticeSummary.model_validate(dict(row)) for row in rows], meta=meta(request)
    )


@router.get("/practice/cases/{case_id}", response_model=CaseEnvelope)
async def detail(case_id: UUID, request: Request) -> CaseEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        case = await case_row(session, case_id, user["id"])
        draft = (
            (
                await session.execute(
                    text(
                        "SELECT answer_json,version,updated_at FROM app.practice_drafts "
                        "WHERE owner_user_id=:owner AND case_id=:case"
                    ),
                    {"owner": user["id"], "case": case_id},
                )
            )
            .mappings()
            .first()
        )
        data = PracticeCase.model_validate(
            summary(case)
            | case["content_json"]
            | {
                "draft": draft["answer_json"] if draft else None,
                "draft_version": draft["version"] if draft else 0,
                "draft_saved_at": draft["updated_at"] if draft else None,
            }
        )
    return CaseEnvelope(data=data, meta=meta(request))


@router.patch("/practice/cases/{case_id}/draft", response_model=CaseEnvelope)
async def save_draft(case_id: UUID, body: DraftInput, request: Request) -> CaseEnvelope:
    await auth.rate_limit(request, "practice_write")
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request, write=True)
        case = await case_row(session, case_id, user["id"])
        validate_evidence(body.answer, case)
        params = {"owner": user["id"], "case": case_id}
        version = await session.scalar(
            text(
                "SELECT version FROM app.practice_drafts "
                "WHERE owner_user_id=:owner AND case_id=:case FOR UPDATE"
            ),
            params,
        )
        if (version or 0) != body.expected_version:
            raise auth.AuthError(409, "VERSION_CONFLICT")
        await session.execute(
            text("""INSERT INTO app.practice_drafts(owner_user_id,case_id,answer_json,version)
            VALUES (:owner,:case,CAST(:answer AS jsonb),1) ON CONFLICT(owner_user_id,case_id)
            DO UPDATE SET answer_json=EXCLUDED.answer_json,
                version=app.practice_drafts.version+1,updated_at=now()"""),
            params | {"answer": body.answer.model_dump_json()},
        )
        await auth.audit(session, "practice.draft", user["id"], request)
        data = PracticeCase.model_validate(
            summary(case)
            | case["content_json"]
            | {"draft": body.answer.model_dump(mode="json"), "draft_version": (version or 0) + 1}
        )
    return CaseEnvelope(data=data, meta=meta(request))


@router.post("/practice/cases/{case_id}/answers", response_model=AnswerEnvelope, status_code=201)
async def submit(
    case_id: UUID,
    body: PracticeAnswer,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> AnswerEnvelope:
    key = key_from_header(idempotency_key)
    await auth.rate_limit(request, "practice_submit")
    payload = body.model_dump(mode="json")
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request, write=True)
        case = await case_row(session, case_id, user["id"])
        validate_evidence(body, case)
        params = {"owner": user["id"], "case": case_id, "key": key}
        previous = (
            (
                await session.execute(
                    text("""SELECT * FROM app.practice_answers
            WHERE owner_user_id=:owner AND case_id=:case AND idempotency_key=:key"""),
                    params,
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != digest(payload):
                raise auth.AuthError(409, "IDEMPOTENCY_CONFLICT")
            return AnswerEnvelope(data=answer_view(previous), meta=meta(request))
        answer_id = uuid4()
        await session.execute(
            text("""INSERT INTO app.practice_answers
            (id,owner_user_id,case_id,case_version,idempotency_key,request_hash,answer_json,evidence_snapshot)
            VALUES (:id,:owner,:case,:version,:key,:hash,
                CAST(:answer AS jsonb),CAST(:snapshot AS jsonb))"""),
            params
            | {
                "id": answer_id,
                "version": case["version"],
                "hash": digest(payload),
                "answer": encoded(payload),
                "snapshot": encoded(case["content_json"]),
            },
        )
        await session.execute(
            text("SELECT private.review_practice(:owner,:id)"),
            {"owner": user["id"], "id": answer_id},
        )
        row = (
            (
                await session.execute(
                    text("SELECT * FROM app.practice_answers WHERE id=:id"), {"id": answer_id}
                )
            )
            .mappings()
            .one()
        )
        await auth.audit(session, "practice.submit", user["id"], request)
        result = answer_view(row)
    return AnswerEnvelope(data=result, meta=meta(request))


@router.get("/practice/cases/{case_id}/answers", response_model=HistoryEnvelope)
async def history(case_id: UUID, request: Request) -> HistoryEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        await case_row(session, case_id, user["id"])
        rows = (
            (
                await session.execute(
                    text("""SELECT * FROM app.practice_answers
            WHERE owner_user_id=:owner AND case_id=:case
            ORDER BY created_at DESC,id DESC LIMIT 50"""),
                    {"owner": user["id"], "case": case_id},
                )
            )
            .mappings()
            .all()
        )
    return HistoryEnvelope(data=[answer_view(row) for row in rows], meta=meta(request))


async def questions(session: AsyncSession, owner: UUID, level_id: UUID) -> list[dict[str, Any]]:
    await require_level(session, owner, level_id)
    incomplete = await session.scalar(
        text("""SELECT 1 FROM app.lessons l WHERE l.level_id=:level
        AND l.published_at<=now() AND NOT EXISTS(SELECT 1 FROM app.user_lesson_progress p
        WHERE p.user_id=:owner AND p.lesson_id=l.id AND p.lesson_version=l.version
            AND p.completed_at IS NOT NULL)
        LIMIT 1"""),
        {"level": level_id, "owner": owner},
    )
    if incomplete:
        raise auth.AuthError(409, "LESSON_REQUIRED")
    rows = (
        (
            await session.execute(
                text(
                    "SELECT id,ordinal,version,prompt,category FROM app.written_questions "
                    "WHERE level_id=:level ORDER BY ordinal"
                ),
                {"level": level_id},
            )
        )
        .mappings()
        .all()
    )
    if len(rows) != 10:
        raise auth.AuthError(503, "WRITTEN_EXAM_UNAVAILABLE")
    return [dict(row) | {"id": str(row["id"])} for row in rows]


@router.get("/learning/levels/{level_id}/written-questions", response_model=QuestionsEnvelope)
async def written_questions(level_id: UUID, request: Request) -> QuestionsEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        data = await questions(session, user["id"], level_id)
    return QuestionsEnvelope(
        data=[WrittenQuestion.model_validate(item) for item in data], meta=meta(request)
    )


def written_view(row: Any) -> WrittenView:
    return WrittenView(
        id=row["id"],
        level_id=row["level_id"],
        status=row["status"],
        answers=row["answers_json"],
        questions=row["question_snapshot"],
        created_at=row["created_at"],
    )


@router.post(
    "/learning/levels/{level_id}/written-submissions",
    response_model=WrittenEnvelope,
    status_code=201,
)
async def submit_written(
    level_id: UUID,
    body: WrittenInput,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> WrittenEnvelope:
    key = key_from_header(idempotency_key)
    await auth.rate_limit(request, "written_submit")
    payload = body.model_dump(mode="json")["answers"]
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request, write=True)
        snapshot = await questions(session, user["id"], level_id)
        if {str(item.question_id) for item in body.answers} != {
            item["id"] for item in snapshot
        } or len({item.question_id for item in body.answers}) != 10:
            raise auth.AuthError(422, "INVALID_QUESTIONS")
        params = {"owner": user["id"], "level": level_id, "key": key}
        previous = (
            (
                await session.execute(
                    text("""SELECT * FROM app.written_submissions
            WHERE owner_user_id=:owner AND level_id=:level AND idempotency_key=:key"""),
                    params,
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != digest(payload):
                raise auth.AuthError(409, "IDEMPOTENCY_CONFLICT")
            return WrittenEnvelope(data=written_view(previous), meta=meta(request))
        row = (
            (
                await session.execute(
                    text("""INSERT INTO app.written_submissions
            (id,owner_user_id,level_id,idempotency_key,request_hash,answers_json,question_snapshot)
            VALUES (:id,:owner,:level,:key,:hash,
                CAST(:answers AS jsonb),CAST(:snapshot AS jsonb)) RETURNING *"""),
                    params
                    | {
                        "id": uuid4(),
                        "hash": digest(payload),
                        "answers": encoded(payload),
                        "snapshot": encoded(snapshot),
                    },
                )
            )
            .mappings()
            .one()
        )
        await auth.audit(session, "written.submit", user["id"], request)
        result = written_view(row)
    return WrittenEnvelope(data=result, meta=meta(request))


@router.get("/learning/levels/{level_id}/written-submissions", response_model=WrittenHistory)
async def written_history(level_id: UUID, request: Request) -> WrittenHistory:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        await require_level(session, user["id"], level_id)
        rows = (
            (
                await session.execute(
                    text("""SELECT * FROM app.written_submissions
            WHERE owner_user_id=:owner AND level_id=:level
            ORDER BY created_at DESC,id DESC LIMIT 50"""),
                    {"owner": user["id"], "level": level_id},
                )
            )
            .mappings()
            .all()
        )
    return WrittenHistory(data=[written_view(row) for row in rows], meta=meta(request))

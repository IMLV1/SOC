from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text

from app.auth import service as auth
from app.auth.routes import json_only
from app.exams.routes import key_from_header
from app.http_models import Meta
from app.learning.practice_routes import learner
from app.tutor.models import (
    AvailabilityEnvelope,
    TutorAvailability,
    TutorEnvelope,
    TutorHistory,
    TutorInput,
)
from app.tutor.service import admit, question_view, readiness, release_drift

router = APIRouter(
    prefix="/api/v1/tutor", dependencies=[Depends(json_only)], include_in_schema=False
)


@router.get("/availability", response_model=AvailabilityEnvelope)
async def availability(request: Request) -> AvailabilityEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        if user["role"] != "analyst":
            raise auth.AuthError(403, "FORBIDDEN")
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        reason = readiness(policy)
        if reason is None and await release_drift(session, policy["version"]):
            reason = "DIFY_WORKFLOW_VERSION_MISMATCH"
        if await session.scalar(
            text("""SELECT 1 FROM app.exam_attempts WHERE owner_user_id=:owner
            AND status IN ('in_progress','submitted','needs_review') LIMIT 1"""),
            {"owner": user["id"]},
        ):
            reason = "EXAM_ATTEMPT_ACTIVE"
    return AvailabilityEnvelope(
        data=TutorAvailability(
            available=reason is None, reason=reason, daily_budget_usd=str(policy["daily_usd"])
        ),
        meta=Meta(request_id=request.state.request_id),
    )


@router.post("/questions", response_model=TutorEnvelope, status_code=202)
async def create(
    body: TutorInput,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> TutorEnvelope:
    key = key_from_header(idempotency_key)
    await auth.rate_limit(request, "tutor_write")
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request, write=True)
        data = await admit(session, user["id"], body.lesson_id, body.question, key)
        await auth.audit(session, "tutor.question", user["id"], request)
    return TutorEnvelope(data=data, meta=Meta(request_id=request.state.request_id))


@router.get("/questions", response_model=TutorHistory)
async def history(request: Request) -> TutorHistory:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        rows = (
            (
                await session.execute(
                    text("""SELECT * FROM app.tutor_questions
            WHERE owner_user_id=:owner AND expires_at>now()
            ORDER BY created_at DESC,id DESC LIMIT 20"""),
                    {"owner": user["id"]},
                )
            )
            .mappings()
            .all()
        )
    return TutorHistory(
        data=[question_view(row, policy) for row in rows],
        meta=Meta(request_id=request.state.request_id),
    )


@router.get("/questions/{question_id}", response_model=TutorEnvelope)
async def detail(question_id: UUID, request: Request) -> TutorEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await learner(session, request)
        row = (
            (
                await session.execute(
                    text("""SELECT * FROM app.tutor_questions
            WHERE id=:id AND owner_user_id=:owner AND expires_at>now()"""),
                    {"id": question_id, "owner": user["id"]},
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
    return TutorEnvelope(
        data=question_view(row, policy), meta=Meta(request_id=request.state.request_id)
    )

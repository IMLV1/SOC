"""Ask AI and scoped sources. No question/retry operation for Instructor review."""

import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import (
    AnalysisEnvelope,
    AnalysisView,
    QuestionInput,
    SourceEnvelope,
    SourceView,
)
from app.analysis.service import analysis_view, enqueue_analysis, require_dify_question_release
from app.auth import service as auth
from app.auth.models import AuthMeta
from app.evaluation.routes import assigned_run
from app.http_models import ErrorEnvelope
from app.investigation.service import ticket_row
from app.knowledge.rag import ensure_training, revoked, source
from app.runs.idempotency import complete, reserve
from app.runs.routes import guard_write, idempotency_key
from app.runs.service import get_owned_run

router = APIRouter(
    prefix="/api/v1",
    tags=["RAG"],
    responses={s: {"model": ErrorEnvelope} for s in (400, 401, 403, 404, 409, 410, 422, 429, 503)},
)


@router.post(
    "/runs/{run_id}/tickets/{ticket_id}/questions",
    status_code=202,
    response_model=AnalysisEnvelope,
    operation_id="questions_create",
)
async def question(
    run_id: UUID, ticket_id: UUID, body: QuestionInput, request: Request
) -> AnalysisEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        # Ownership precedes reading idempotency cache; run lock serializes finish/questions.
        run = await get_owned_run(session, run_id, user["id"])
        await ensure_training(session, run_id)
        key, cached = await reserve(
            session,
            user["id"],
            f"/runs/{run_id}/tickets/{ticket_id}/questions",
            idempotency_key(request),
            body.model_dump(),
        )
        if cached is not None:
            cached_row = (
                (
                    await session.execute(
                        text("SELECT * FROM app.analyses WHERE run_id=:run AND id=:id"),
                        {"run": run_id, "id": UUID(str(cached["id"]))},
                    )
                )
                .mappings()
                .first()
            )
            if cached_row is None:
                raise auth.AuthError(404, "NOT_FOUND")
            cached = await analysis_view(session, cached_row)
            return AnalysisEnvelope(
                data=AnalysisView.model_validate(cached),
                meta=AuthMeta(request_id=request.state.request_id),
            )
        run = await get_owned_run(session, run_id, user["id"], lock=True)
        # No exam endpoints exist: only training manifests may enter this feature.
        training = await session.scalar(text("SELECT app.is_training_run(:run)"), {"run": run_id})
        if not training or run["status"] not in {"running", "paused", "reviewing"}:
            raise auth.AuthError(409, "RUN_READ_ONLY")
        ticket = await ticket_row(session, run_id, ticket_id, lock=True)
        if ticket["deleted_at"] is not None:
            raise auth.AuthError(409, "TICKET_DELETED")
        if ticket["version"] != body.expected_version:
            raise auth.AuthError(409, "VERSION_CONFLICT")
        content = body.question.strip()
        if not content:
            raise auth.AuthError(422, "VALIDATION_ERROR")
        release = await session.scalar(
            text("SELECT knowledge_release_id FROM app.run_versions WHERE run_id=:run"),
            {"run": run_id},
        )
        if release is None:
            await require_dify_question_release(session, run_id)
        elif await revoked(session, release):
            raise auth.AuthError(409, "KNOWLEDGE_REVOKED")
        ids = list(
            (
                await session.execute(
                    text(
                        "SELECT event_id FROM app.ticket_events "
                        "WHERE run_id=:run AND ticket_id=:id ORDER BY event_id"
                    ),
                    {"run": run_id, "id": ticket_id},
                )
            )
            .scalars()
            .all()
        )
        if not ids:
            raise auth.AuthError(422, "INVALID_EVIDENCE")
        aid = await enqueue_analysis(
            session,
            run_id,
            user["id"],
            f"question:{uuid4()}",
            hashlib.sha256("|".join(map(str, ids)).encode()).hexdigest(),
            ids,
            ticket_id,
            question=content,
        )
        row = (
            (await session.execute(text("SELECT * FROM app.analyses WHERE id=:id"), {"id": aid}))
            .mappings()
            .one()
        )
        if row["status"] == "quota_exceeded":
            raise auth.AuthError(429, "AI_QUOTA_EXCEEDED")
        data = await analysis_view(session, row)
        await complete(session, key, data, aid, response_status=202)
        await session.execute(
            text("""INSERT INTO app.audit_logs
            (id,run_id,actor_user_id,actor_role,action,entity_type,entity_id)
            VALUES (:id,:run,:actor,'analyst','question.create','analysis',:aid)"""),
            {"id": uuid4(), "run": run_id, "actor": user["id"], "aid": aid},
        )
    return AnalysisEnvelope(
        data=AnalysisView.model_validate(data), meta=AuthMeta(request_id=request.state.request_id)
    )


@router.get(
    "/runs/{run_id}/analyses/{analysis_id}/sources/{retrieval_item_id}",
    response_model=SourceEnvelope,
    operation_id="analysis_source_get",
)
async def read_source(
    run_id: UUID, analysis_id: UUID, retrieval_item_id: UUID, request: Request
) -> SourceEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        await ensure_training(session, run_id)
        data = await source(session, run_id, analysis_id, retrieval_item_id)
    return SourceEnvelope(
        data=SourceView.model_validate(data), meta=AuthMeta(request_id=request.state.request_id)
    )


async def instructor_access(session: AsyncSession, request: Request, run_id: UUID) -> None:
    user = await auth.require_user(session, request)
    await assigned_run(session, user, run_id)
    await ensure_training(session, run_id)
    await session.execute(
        text("""INSERT INTO app.audit_logs
        (id,run_id,actor_user_id,actor_role,action,entity_type,entity_id)
        VALUES (:id,:run,:actor,'instructor','analysis.instructor_read','run',:run)"""),
        {"id": uuid4(), "run": run_id, "actor": user["id"]},
    )


@router.get(
    "/admin/runs/{run_id}/analyses/{analysis_id}",
    response_model=AnalysisEnvelope,
    operation_id="instructor_analysis_get",
)
async def instructor_analysis(
    run_id: UUID, analysis_id: UUID, request: Request
) -> AnalysisEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        await instructor_access(session, request, run_id)
        row = (
            (
                await session.execute(
                    text("SELECT * FROM app.analyses WHERE run_id=:run AND id=:id"),
                    {"run": run_id, "id": analysis_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise auth.AuthError(404, "NOT_FOUND")
        data = await analysis_view(session, row)
    return AnalysisEnvelope(
        data=AnalysisView.model_validate(data), meta=AuthMeta(request_id=request.state.request_id)
    )


@router.get(
    "/admin/runs/{run_id}/analyses/{analysis_id}/sources/{retrieval_item_id}",
    response_model=SourceEnvelope,
    operation_id="instructor_source_get",
)
async def instructor_source(
    run_id: UUID, analysis_id: UUID, retrieval_item_id: UUID, request: Request
) -> SourceEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        await instructor_access(session, request, run_id)
        data = await source(session, run_id, analysis_id, retrieval_item_id)
    return SourceEnvelope(
        data=SourceView.model_validate(data), meta=AuthMeta(request_id=request.state.request_id)
    )

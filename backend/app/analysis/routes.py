from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import text

from app.analysis.models import AnalysisEnvelope, AnalysisList, AnalysisView, RetryInput
from app.analysis.service import analysis_view, enqueue_analysis
from app.auth import service as auth
from app.auth.models import AuthMeta, PageMeta
from app.http_models import ErrorEnvelope
from app.runs.idempotency import complete, reserve
from app.runs.pagination import decode_cursor, encode_cursor
from app.runs.routes import guard_write, idempotency_key
from app.runs.service import get_owned_run

router = APIRouter(
    prefix="/api/v1/runs/{run_id}/analyses",
    tags=["Analysis"],
    responses={
        status: {"model": ErrorEnvelope} for status in (400, 401, 403, 404, 409, 422, 429, 503)
    },
)


def meta(request: Request) -> AuthMeta:
    return AuthMeta(request_id=request.state.request_id)


@router.get("", response_model=AnalysisList, operation_id="analyses_list")
async def list_analyses(
    run_id: UUID, request: Request, status: str | None = None,
    ticket_id: UUID | None = None, cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> AnalysisList:
    allowed = {
        "queued",
        "running",
        "succeeded",
        "failed",
        "invalid_output",
        "quota_exceeded",
        "timed_out",
        "cancelled",
    }
    if status is not None and status not in allowed:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    filters = {"status": status, "ticket_id": str(ticket_id) if ticket_id else None}
    cursor_at, cursor_id = decode_cursor(cursor, filters)
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        rows = (
            (
                await session.execute(
                    text("""SELECT a.* FROM app.analyses a
            WHERE a.run_id=:run AND (CAST(:status AS text) IS NULL OR a.status=:status)
            AND (CAST(:ticket AS uuid) IS NULL OR EXISTS (
                SELECT 1 FROM app.ticket_analyses ta
                WHERE ta.run_id=a.run_id AND ta.analysis_id=a.id AND ta.ticket_id=:ticket))
            AND (CAST(:cursor_at AS timestamptz) IS NULL OR
                 (a.created_at,a.id)<(CAST(:cursor_at AS timestamptz),CAST(:cursor_id AS uuid)))
            ORDER BY a.created_at DESC,a.id DESC LIMIT :limit"""),
                    {"run": run_id, "status": status, "ticket": ticket_id,
                     "cursor_at": cursor_at, "cursor_id": cursor_id, "limit": limit + 1},
                )
            )
            .mappings()
            .all()
        )
        visible = rows[:limit]
        items = [AnalysisView.model_validate(await analysis_view(session, row)) for row in visible]
    next_cursor = (
        encode_cursor(visible[-1]["created_at"], visible[-1]["id"], filters)
        if len(rows) > limit else None
    )
    return AnalysisList(data=items, meta=PageMeta(request_id=request.state.request_id,
                                                 next_cursor=next_cursor))


@router.get("/{analysis_id}", response_model=AnalysisEnvelope, operation_id="analyses_get")
async def detail(run_id: UUID, analysis_id: UUID, request: Request) -> AnalysisEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        row = (
            (
                await session.execute(
                    text("""SELECT * FROM app.analyses
            WHERE run_id=:run AND id=:id"""),
                    {"run": run_id, "id": analysis_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise auth.AuthError(404, "NOT_FOUND")
        data = await analysis_view(session, row)
    return AnalysisEnvelope(data=AnalysisView.model_validate(data), meta=meta(request))


@router.post(
    "/{analysis_id}/retry",
    response_model=AnalysisEnvelope,
    status_code=202,
    operation_id="analyses_retry",
)
async def retry(
    run_id: UUID, analysis_id: UUID, body: RetryInput, request: Request
) -> AnalysisEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        route = f"/runs/{run_id}/analyses/{analysis_id}/retry"
        request_id, cached = await reserve(
            session, user["id"], route, idempotency_key(request), body.model_dump()
        )
        if cached is not None:
            return AnalysisEnvelope(data=AnalysisView.model_validate(cached), meta=meta(request))
        run = await get_owned_run(session, run_id, user["id"], lock=True)
        if run["status"] not in {"running", "paused", "reviewing"}:
            raise auth.AuthError(409, "RUN_READ_ONLY")
        old = (
            (
                await session.execute(
                    text("""SELECT * FROM app.analyses
            WHERE run_id=:run AND id=:id FOR UPDATE"""),
                    {"run": run_id, "id": analysis_id},
                )
            )
            .mappings()
            .first()
        )
        if old is None:
            raise auth.AuthError(404, "NOT_FOUND")
        if old["version"] != body.expected_version:
            raise auth.AuthError(409, "VERSION_CONFLICT")
        if old["status"] not in {"failed", "timed_out", "invalid_output", "quota_exceeded"}:
            raise auth.AuthError(409, "INVALID_ANALYSIS_STATE")
        ids = (
            (
                await session.execute(
                    text("""SELECT event_id FROM app.analysis_evidence
            WHERE analysis_id=:id ORDER BY event_id"""),
                    {"id": analysis_id},
                )
            )
            .scalars()
            .all()
        )
        ticket_id = await session.scalar(
            text("""SELECT ta.ticket_id FROM app.ticket_analyses ta
            JOIN app.tickets t ON t.id=ta.ticket_id AND t.run_id=ta.run_id
            WHERE ta.run_id=:run AND ta.analysis_id=:id AND t.deleted_at IS NULL"""),
            {"run": run_id, "id": analysis_id},
        )
        new_id = await enqueue_analysis(
            session,
            run_id,
            user["id"],
            old["correlation_key"],
            old["evidence_hash"],
            list(ids),
            ticket_id,
            analysis_id,
        )
        row = (
            (await session.execute(text("SELECT * FROM app.analyses WHERE id=:id"), {"id": new_id}))
            .mappings()
            .one()
        )
        if row["status"] == "quota_exceeded":
            raise auth.AuthError(429, "AI_QUOTA_EXCEEDED")
        data = await analysis_view(session, row)
        await complete(session, request_id, data, new_id, response_status=202)
    return AnalysisEnvelope(data=AnalysisView.model_validate(data), meta=meta(request))

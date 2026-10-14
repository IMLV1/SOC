from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth
from app.auth.models import AuthMeta, PageMeta
from app.http_models import ErrorEnvelope
from app.investigation.models import (
    AssessmentList,
    AssessmentView,
    DeleteInput,
    InstructorTicketPatch,
    NoteCreate,
    NoteEnvelope,
    NoteList,
    NotePatch,
    NoteVersionView,
    NoteView,
    TicketCreate,
    TicketEnvelope,
    TicketList,
    TicketPatch,
    TicketTimelineEntry,
    TicketTimelineList,
    TicketView,
    VersionList,
)
from app.investigation.service import (
    VALID_TRANSITIONS,
    cleaned,
    create_note,
    create_ticket,
    delete_or_restore_ticket,
    mutate_note,
    note_row,
    note_view,
    patch_ticket,
    ticket_row,
    ticket_view,
)
from app.runs.pagination import decode_cursor, encode_cursor
from app.runs.routes import guard_write, idempotency_key
from app.runs.service import get_owned_run

router = APIRouter(
    prefix="/api/v1/runs/{run_id}/tickets",
    tags=["Tickets"],
    responses={status: {"model": ErrorEnvelope} for status in (400, 401, 403, 404, 409, 422, 503)},
)
admin_router = APIRouter(prefix="/api/v1/admin/runs/{run_id}/tickets", tags=["Instructor"])


def meta(request: Request) -> AuthMeta:
    return AuthMeta(request_id=request.state.request_id)


@router.get("", response_model=TicketList, operation_id="tickets_list")
async def list_tickets(
    run_id: UUID,
    request: Request,
    deleted: str = "exclude",
    q: str | None = Query(None, max_length=200),
    severity: str | None = None,
    status: str | None = None,
    disposition: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> TicketList:
    if deleted not in {"exclude", "include", "only"}:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    if severity is not None and severity not in {"low", "medium", "high", "critical"}:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    if status is not None and status not in VALID_TRANSITIONS:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    if disposition is not None and disposition not in {
        "true_positive",
        "false_positive",
        "undetermined",
    }:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    filters = {
        "deleted": deleted,
        "q": q,
        "severity": severity,
        "status": status,
        "disposition": disposition,
    }
    cursor_at, cursor_id = decode_cursor(cursor, filters)
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        rows = (
            (
                await session.execute(
                    text("""SELECT t.* FROM app.tickets t
            LEFT JOIN LATERAL (SELECT disposition FROM app.assessments a
                WHERE a.run_id=t.run_id AND a.ticket_id=t.id
                ORDER BY revision DESC LIMIT 1) latest ON TRUE
            WHERE t.run_id=:run AND (:deleted='include' OR
             (:deleted='only' AND t.deleted_at IS NOT NULL) OR
             (:deleted='exclude' AND t.deleted_at IS NULL))
            AND (CAST(:severity AS text) IS NULL OR t.severity=:severity)
            AND (CAST(:status AS text) IS NULL OR t.status=:status)
            AND (CAST(:disposition AS text) IS NULL OR latest.disposition=:disposition)
            AND (CAST(:q AS text) IS NULL OR t.title ILIKE :search
                 OR t.correlation_key ILIKE :search)
            AND (CAST(:cursor_at AS timestamptz) IS NULL OR
                 (t.created_at,t.id)<(CAST(:cursor_at AS timestamptz),CAST(:cursor_id AS uuid)))
            ORDER BY t.created_at DESC,t.id DESC LIMIT :limit"""),
                    {
                        "run": run_id,
                        "deleted": deleted,
                        "severity": severity,
                        "status": status,
                        "disposition": disposition,
                        "q": q,
                        "search": f"%{q}%" if q else None,
                        "cursor_at": cursor_at,
                        "cursor_id": cursor_id,
                        "limit": limit + 1,
                    },
                )
            )
            .mappings()
            .all()
        )
        visible = rows[:limit]
        items = [TicketView.model_validate(await ticket_view(session, row)) for row in visible]
    next_cursor = (
        encode_cursor(visible[-1]["created_at"], visible[-1]["id"], filters)
        if len(rows) > limit
        else None
    )
    return TicketList(
        data=items, meta=PageMeta(request_id=request.state.request_id, next_cursor=next_cursor)
    )


@router.post("", response_model=TicketEnvelope, status_code=201, operation_id="tickets_create")
async def create(run_id: UUID, body: TicketCreate, request: Request) -> TicketEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await create_ticket(session, run_id, user["id"], body, idempotency_key(request))
    return TicketEnvelope(data=TicketView.model_validate(data), meta=meta(request))


@router.get("/{ticket_id}", response_model=TicketEnvelope, operation_id="tickets_get")
async def detail(run_id: UUID, ticket_id: UUID, request: Request) -> TicketEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        data = await ticket_view(session, await ticket_row(session, run_id, ticket_id))
    return TicketEnvelope(data=TicketView.model_validate(data), meta=meta(request))


@router.get(
    "/{ticket_id}/timeline", response_model=TicketTimelineList, operation_id="tickets_timeline"
)
async def ticket_timeline(
    run_id: UUID,
    ticket_id: UUID,
    request: Request,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> TicketTimelineList:
    filters = {"ticket_id": str(ticket_id)}
    cursor_at, cursor_id = decode_cursor(cursor, filters)
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        await ticket_row(session, run_id, ticket_id)
        rows = (
            (
                await session.execute(
                    text("""WITH history AS (
                SELECT e.id,e.ingested_at AS occurred_at,'event' AS kind,
                       e.source AS action,e.id AS event_id
                FROM app.ticket_events te JOIN app.events e
                  ON e.run_id=te.run_id AND e.id=te.event_id
                WHERE te.run_id=:run AND te.ticket_id=:ticket
                UNION ALL
                SELECT a.id,a.created_at,'audit',a.action,NULL::uuid
                FROM app.audit_logs a WHERE a.run_id=:run AND
                  ((a.entity_type='ticket' AND a.entity_id=:ticket) OR
                   (a.entity_type='note' AND EXISTS (
                     SELECT 1 FROM app.notes n WHERE n.run_id=:run AND
                       n.ticket_id=:ticket AND n.id=a.entity_id)))
                UNION ALL
                SELECT a.id,a.created_at,'assessment',a.disposition,NULL::uuid
                FROM app.assessments a WHERE a.run_id=:run AND a.ticket_id=:ticket
            ) SELECT * FROM history
            WHERE CAST(:cursor_at AS timestamptz) IS NULL OR
                  (occurred_at,id)<(CAST(:cursor_at AS timestamptz),CAST(:cursor_id AS uuid))
            ORDER BY occurred_at DESC,id DESC LIMIT :limit"""),
                    {
                        "run": run_id,
                        "ticket": ticket_id,
                        "cursor_at": cursor_at,
                        "cursor_id": cursor_id,
                        "limit": limit + 1,
                    },
                )
            )
            .mappings()
            .all()
        )
        visible = rows[:limit]
        items = [TicketTimelineEntry.model_validate(dict(row)) for row in visible]
    next_cursor = (
        encode_cursor(visible[-1]["occurred_at"], visible[-1]["id"], filters)
        if len(rows) > limit
        else None
    )
    return TicketTimelineList(
        data=items, meta=PageMeta(request_id=request.state.request_id, next_cursor=next_cursor)
    )


@router.patch("/{ticket_id}", response_model=TicketEnvelope, operation_id="tickets_patch")
async def patch(
    run_id: UUID, ticket_id: UUID, body: TicketPatch, request: Request
) -> TicketEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await patch_ticket(session, run_id, ticket_id, user["id"], body)
    return TicketEnvelope(data=TicketView.model_validate(data), meta=meta(request))


@router.delete("/{ticket_id}", response_model=TicketEnvelope, operation_id="tickets_delete")
async def delete(
    run_id: UUID, ticket_id: UUID, body: DeleteInput, request: Request
) -> TicketEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await delete_or_restore_ticket(session, run_id, ticket_id, user["id"], body, False)
    return TicketEnvelope(data=TicketView.model_validate(data), meta=meta(request))


@router.post("/{ticket_id}/restore", response_model=TicketEnvelope, operation_id="tickets_restore")
async def restore(
    run_id: UUID, ticket_id: UUID, body: DeleteInput, request: Request
) -> TicketEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await delete_or_restore_ticket(session, run_id, ticket_id, user["id"], body, True)
    return TicketEnvelope(data=TicketView.model_validate(data), meta=meta(request))


@router.get(
    "/{ticket_id}/assessments", response_model=AssessmentList, operation_id="assessments_list"
)
async def assessments(
    run_id: UUID,
    ticket_id: UUID,
    request: Request,
    cursor: int | None = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> AssessmentList:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        await ticket_row(session, run_id, ticket_id)
        rows = (
            (
                await session.execute(
                    text("""SELECT id,revision,author_user_id,
            disposition,reason,created_at FROM app.assessments
            WHERE run_id=:run AND ticket_id=:ticket AND revision>:cursor
            ORDER BY revision LIMIT :limit"""),
                    {"run": run_id, "ticket": ticket_id, "cursor": cursor or 0, "limit": limit + 1},
                )
            )
            .mappings()
            .all()
        )
    visible = rows[:limit]
    return AssessmentList(
        data=[AssessmentView.model_validate(dict(row)) for row in visible],
        meta=PageMeta(
            request_id=request.state.request_id,
            next_cursor=str(visible[-1]["revision"]) if len(rows) > limit else None,
        ),
    )


@router.get("/{ticket_id}/notes", response_model=NoteList, operation_id="notes_list")
async def list_notes(
    run_id: UUID,
    ticket_id: UUID,
    request: Request,
    deleted: bool = False,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> NoteList:
    filters = {"ticket_id": str(ticket_id), "deleted": deleted}
    cursor_at, cursor_id = decode_cursor(cursor, filters)
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        await ticket_row(session, run_id, ticket_id)
        rows = (
            (
                await session.execute(
                    text("""SELECT * FROM app.notes
            WHERE run_id=:run AND ticket_id=:ticket
            AND (:deleted OR deleted_at IS NULL)
            AND (CAST(:cursor_at AS timestamptz) IS NULL OR
                 (created_at,id)>(CAST(:cursor_at AS timestamptz),CAST(:cursor_id AS uuid)))
            ORDER BY created_at,id LIMIT :limit"""),
                    {
                        "run": run_id,
                        "ticket": ticket_id,
                        "deleted": deleted,
                        "cursor_at": cursor_at,
                        "cursor_id": cursor_id,
                        "limit": limit + 1,
                    },
                )
            )
            .mappings()
            .all()
        )
        visible = rows[:limit]
        items = [NoteView.model_validate(await note_view(session, row)) for row in visible]
    next_cursor = (
        encode_cursor(visible[-1]["created_at"], visible[-1]["id"], filters)
        if len(rows) > limit
        else None
    )
    return NoteList(
        data=items, meta=PageMeta(request_id=request.state.request_id, next_cursor=next_cursor)
    )


@router.post(
    "/{ticket_id}/notes", response_model=NoteEnvelope, status_code=201, operation_id="notes_create"
)
async def add_note(
    run_id: UUID, ticket_id: UUID, body: NoteCreate, request: Request
) -> NoteEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await create_note(
            session, run_id, ticket_id, user["id"], body, idempotency_key(request)
        )
    return NoteEnvelope(data=NoteView.model_validate(data), meta=meta(request))


@router.patch(
    "/{ticket_id}/notes/{note_id}", response_model=NoteEnvelope, operation_id="notes_patch"
)
async def edit_note(
    run_id: UUID, ticket_id: UUID, note_id: UUID, body: NotePatch, request: Request
) -> NoteEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await mutate_note(session, run_id, ticket_id, note_id, user["id"], "edit", body)
    return NoteEnvelope(data=NoteView.model_validate(data), meta=meta(request))


@router.delete(
    "/{ticket_id}/notes/{note_id}", response_model=NoteEnvelope, operation_id="notes_delete"
)
async def delete_note(
    run_id: UUID, ticket_id: UUID, note_id: UUID, body: DeleteInput, request: Request
) -> NoteEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await mutate_note(session, run_id, ticket_id, note_id, user["id"], "delete", body)
    return NoteEnvelope(data=NoteView.model_validate(data), meta=meta(request))


@router.post(
    "/{ticket_id}/notes/{note_id}/restore",
    response_model=NoteEnvelope,
    operation_id="notes_restore",
)
async def restore_note(
    run_id: UUID, ticket_id: UUID, note_id: UUID, body: DeleteInput, request: Request
) -> NoteEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await mutate_note(session, run_id, ticket_id, note_id, user["id"], "restore", body)
    return NoteEnvelope(data=NoteView.model_validate(data), meta=meta(request))


@router.get(
    "/{ticket_id}/notes/{note_id}/versions",
    response_model=VersionList,
    operation_id="note_versions_list",
)
async def note_versions(
    run_id: UUID,
    ticket_id: UUID,
    note_id: UUID,
    request: Request,
    cursor: int | None = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> VersionList:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        await note_row(session, run_id, ticket_id, note_id)
        rows = (
            (
                await session.execute(
                    text("""SELECT id,version,body,change_kind,reason,
            actor_user_id,created_at FROM app.note_versions
            WHERE run_id=:run AND note_id=:note AND version>:cursor
            ORDER BY version LIMIT :limit"""),
                    {"run": run_id, "note": note_id, "cursor": cursor or 0, "limit": limit + 1},
                )
            )
            .mappings()
            .all()
        )
        items = []
        for row in rows[:limit]:
            ids = (
                (
                    await session.execute(
                        text("""SELECT event_id FROM app.note_version_evidence
                WHERE note_version_id=:id ORDER BY event_id"""),
                        {"id": row["id"]},
                    )
                )
                .scalars()
                .all()
            )
            view = {key: value for key, value in row.items() if key != "id"}
            items.append(NoteVersionView.model_validate(view | {"evidence_ids": list(ids)}))
    return VersionList(
        data=items,
        meta=PageMeta(
            request_id=request.state.request_id,
            next_cursor=str(rows[limit - 1]["version"]) if len(rows) > limit else None,
        ),
    )


async def assigned_run(session: AsyncSession, request: Request, run_id: UUID) -> Mapping[str, Any]:
    user = await auth.require_user(session, request)
    owner = await session.scalar(
        text("SELECT owner_user_id FROM app.runs WHERE id=:run"), {"run": run_id}
    )
    if owner is None:
        raise auth.AuthError(404, "NOT_FOUND")
    await auth.authorize_assignment(session, user, owner)
    return user


@admin_router.get("/{ticket_id}", response_model=TicketEnvelope, operation_id="admin_ticket_get")
async def admin_detail(run_id: UUID, ticket_id: UUID, request: Request) -> TicketEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        await assigned_run(session, request, run_id)
        data = await ticket_view(session, await ticket_row(session, run_id, ticket_id))
    return TicketEnvelope(data=TicketView.model_validate(data), meta=meta(request))


@admin_router.patch(
    "/{ticket_id}", response_model=TicketEnvelope, operation_id="admin_ticket_patch"
)
async def admin_patch(
    run_id: UUID, ticket_id: UUID, body: InstructorTicketPatch, request: Request
) -> TicketEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        await auth.csrf_check(session, request)
        user = await assigned_run(session, request, run_id)
        run_status = await session.scalar(
            text("SELECT status FROM app.runs WHERE id=:run FOR UPDATE"), {"run": run_id}
        )
        if run_status not in {"running", "paused", "reviewing"}:
            raise auth.AuthError(409, "RUN_READ_ONLY")
        row = await ticket_row(session, run_id, ticket_id, lock=True)
        if row["version"] != body.expected_version:
            raise auth.AuthError(409, "VERSION_CONFLICT")
        if row["deleted_at"] is not None:
            raise auth.AuthError(409, "TICKET_DELETED")
        status = body.status or row["status"]
        if status not in VALID_TRANSITIONS[row["status"]]:
            raise auth.AuthError(409, "INVALID_TICKET_STATE")
        if status in {"resolved", "closed"}:
            disposition = await session.scalar(
                text("""SELECT disposition FROM app.assessments
                WHERE run_id=:run AND ticket_id=:ticket
                ORDER BY revision DESC LIMIT 1"""),
                {"run": run_id, "ticket": ticket_id},
            )
            if disposition is None:
                raise auth.AuthError(422, "ASSESSMENT_REQUIRED")
        if body.severity is None and body.status is None:
            raise auth.AuthError(422, "VALIDATION_ERROR")
        updated = (
            (
                await session.execute(
                    text("""UPDATE app.tickets SET
            severity=COALESCE(:severity,severity),status=:status,
            human_severity_override=CASE WHEN :severity IS NULL
                THEN human_severity_override ELSE true END,
            version=version+1,updated_at=clock_timestamp() WHERE id=:id RETURNING *"""),
                    {"severity": body.severity, "status": status, "id": ticket_id},
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            text("""INSERT INTO app.audit_logs
            (id,run_id,actor_user_id,actor_role,action,entity_type,entity_id,reason)
            VALUES (:id,:run,:actor,'instructor','ticket.instructor_update',
                    'ticket',:ticket,:reason)"""),
            {
                "id": uuid4(),
                "run": run_id,
                "actor": user["id"],
                "ticket": ticket_id,
                "reason": cleaned(body.reason),
            },
        )
        data = await ticket_view(session, updated)
    return TicketEnvelope(data=TicketView.model_validate(data), meta=meta(request))

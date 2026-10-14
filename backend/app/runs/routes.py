import base64
import binascii
import hashlib
import ipaddress
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import text

from app.auth import service as auth
from app.auth.models import AuthMeta, PageMeta
from app.http_models import ErrorEnvelope
from app.runs.models import (
    AlertEnvelope,
    AlertList,
    AlertView,
    EventEnvelope,
    EventList,
    EventPageMeta,
    EventView,
    FinishEnvelope,
    FinishView,
    RunEnvelope,
    RunList,
    RunView,
    VersionInput,
)
from app.runs.pagination import decode_cursor, encode_cursor
from app.runs.service import (
    change_state,
    finish_run,
    get_owned_run,
    run_view,
    server_time,
    start_run,
)
from app.scenarios.models import TrainingSelection

router = APIRouter(
    prefix="/api/v1/runs",
    tags=["Runs"],
    responses={
        status: {"model": ErrorEnvelope} for status in (400, 401, 403, 404, 409, 422, 429, 503)
    },
)


def meta(request: Request) -> AuthMeta:
    return AuthMeta(request_id=request.state.request_id)


async def guard_write(session: object, request: Request) -> Mapping[str, Any]:
    # The session is an AsyncSession; this wrapper keeps request checks in one place.
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise auth.AuthError(415, "UNSUPPORTED_MEDIA_TYPE")
    await auth.csrf_check(session, request)
    user = await auth.require_user(session, request)
    if user["role"] != "analyst":
        raise auth.AuthError(403, "FORBIDDEN")
    return dict(user)


def idempotency_key(request: Request) -> UUID:
    try:
        return UUID(request.headers["idempotency-key"])
    except (KeyError, ValueError):
        raise auth.AuthError(400, "IDEMPOTENCY_KEY_REQUIRED") from None


@router.post("", response_model=RunEnvelope, status_code=201, operation_id="runs_create")
async def create(body: TrainingSelection, request: Request) -> RunEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data, _ = await start_run(session, user["id"], body, idempotency_key(request))
    return RunEnvelope(data=RunView.model_validate(data), meta=meta(request))


@router.get("", response_model=RunList, operation_id="runs_list")
async def list_runs(
    request: Request, status: str | None = None, cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100)
) -> RunList:
    if status is not None and status not in {
        "created",
        "running",
        "paused",
        "reviewing",
        "completing",
        "completed",
        "failed",
    }:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    cursor_at, cursor_id = decode_cursor(cursor, {"status": status})
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        rows = (
            (
                await session.execute(
                    text("""SELECT id,status,version,elapsed_ms,duration_ms,expires_at,
                seed,analysis_mode,resumed_at,created_at
                FROM app.runs WHERE owner_user_id=:owner
                AND (CAST(:status AS text) IS NULL OR status=:status)
                AND (CAST(:cursor_at AS timestamptz) IS NULL OR
                     (created_at,id)<(CAST(:cursor_at AS timestamptz),CAST(:cursor_id AS uuid)))
                ORDER BY created_at DESC,id DESC LIMIT :limit"""),
                    {"owner": user["id"], "status": status, "cursor_at": cursor_at,
                     "cursor_id": cursor_id, "limit": limit + 1},
                )
            )
            .mappings()
            .all()
        )
        now = await server_time(session)
    visible = rows[:limit]
    next_cursor = encode_cursor(visible[-1]["created_at"], visible[-1]["id"],
                                {"status": status}) if len(rows) > limit else None
    return RunList(data=[RunView.model_validate(run_view(row, now)) for row in visible],
                   meta=PageMeta(request_id=request.state.request_id, next_cursor=next_cursor))


@router.get("/{run_id}", response_model=RunEnvelope, operation_id="runs_get")
async def get_run(run_id: UUID, request: Request) -> RunEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        row = await get_owned_run(session, run_id, user["id"])
        now = await server_time(session)
    return RunEnvelope(data=RunView.model_validate(run_view(row, now)), meta=meta(request))


@router.post("/{run_id}/pause", response_model=RunEnvelope, operation_id="runs_pause")
async def pause(run_id: UUID, body: VersionInput, request: Request) -> RunEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await change_state(session, run_id, user["id"], "pause", body.expected_version)
    return RunEnvelope(data=RunView.model_validate(data), meta=meta(request))


@router.post("/{run_id}/resume", response_model=RunEnvelope, operation_id="runs_resume")
async def resume(run_id: UUID, body: VersionInput, request: Request) -> RunEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await change_state(session, run_id, user["id"], "resume", body.expected_version)
    return RunEnvelope(data=RunView.model_validate(data), meta=meta(request))


@router.post(
    "/{run_id}/finish", response_model=FinishEnvelope, status_code=202, operation_id="runs_finish"
)
async def finish(run_id: UUID, body: VersionInput, request: Request) -> FinishEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await guard_write(session, request)
        data = await finish_run(session, run_id, user["id"], body.expected_version)
    return FinishEnvelope(data=FinishView.model_validate(data), meta=meta(request))


def event_view(row: object) -> EventView:
    from collections.abc import Mapping

    assert isinstance(row, Mapping)
    return EventView(
        id=row["id"],
        run_id=row["run_id"],
        release_seq=row["release_seq"],
        event_time=row["event_time"],
        ingested_at=row["ingested_at"],
        source=row["source"],
        asset_id=row["asset_id"],
        username=row["username"],
        src_ip=str(row["src_ip"]) if row["src_ip"] else None,
        request=row["request_json"],
        response=row["response_json"],
        log=row["log_json"],
    )


def cursor_signature(filters: Mapping[str, object]) -> str:
    return hashlib.sha256(json.dumps(filters, sort_keys=True, default=str).encode()).hexdigest()[
        :16
    ]


@router.get("/{run_id}/events", response_model=EventList, operation_id="events_list")
async def list_events(
    run_id: UUID,
    request: Request,
    after_seq: int | None = Query(None, ge=0),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    source: str | None = None,
    asset_id: str | None = None,
    username: str | None = None,
    src_ip: str | None = None,
    q: str | None = Query(None, max_length=200),
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> EventList:
    if after_seq is not None and cursor is not None:
        raise auth.AuthError(400, "BAD_CURSOR")
    if source is not None and source not in {
        "authentication",
        "web",
        "file_access",
        "change_management",
        "baseline",
    }:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    if src_ip is not None:
        try:
            ipaddress.ip_address(src_ip)
        except ValueError:
            raise auth.AuthError(422, "VALIDATION_ERROR") from None
    if any(value is not None and value.tzinfo is None for value in (from_, to)):
        raise auth.AuthError(422, "VALIDATION_ERROR")
    if from_ is not None and to is not None and from_ >= to:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    filters = {
        "source": source,
        "asset_id": asset_id,
        "username": username,
        "src_ip": src_ip,
        "q": q,
        "from": from_.isoformat() if from_ else None,
        "to": to.isoformat() if to else None,
    }
    signature = cursor_signature(filters)
    position = after_seq or 0
    if cursor:
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            if (
                decoded["filters"] != signature
                or not isinstance(decoded["seq"], int)
                or decoded["seq"] < 0
            ):
                raise ValueError
            position = decoded["seq"]
        except (ValueError, KeyError, UnicodeDecodeError, binascii.Error):
            raise auth.AuthError(400, "BAD_CURSOR") from None
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        run = await get_owned_run(session, run_id, user["id"])
        start = run["created_at"]
        end = start + timedelta(milliseconds=run["duration_ms"])
        if (from_ is not None and not start <= from_ <= end) or (
            to is not None and not start <= to <= end
        ):
            raise auth.AuthError(422, "VALIDATION_ERROR")
        rows = (
            (
                await session.execute(
                    text("""SELECT id,run_id,release_seq,event_time,ingested_at,
            source,asset_id,username,src_ip,request_json,response_json,log_json
            FROM app.events WHERE run_id=:run AND release_seq>:position
            AND (CAST(:source AS text) IS NULL OR source=:source)
            AND (CAST(:asset AS text) IS NULL OR asset_id=:asset)
            AND (CAST(:username AS text) IS NULL OR username=:username)
            AND (CAST(:ip AS inet) IS NULL OR src_ip=CAST(:ip AS inet))
            AND (CAST(:q AS text) IS NULL OR asset_id ILIKE :search OR username ILIKE :search
                 OR source ILIKE :search)
            AND (CAST(:from AS timestamptz) IS NULL OR event_time>=CAST(:from AS timestamptz))
            AND (CAST(:to AS timestamptz) IS NULL OR event_time<CAST(:to AS timestamptz))
            ORDER BY release_seq LIMIT :limit"""),
                    {
                        "run": run_id,
                        "position": position,
                        "source": source,
                        "asset": asset_id,
                        "username": username,
                        "ip": src_ip,
                        "q": q,
                        "search": f"%{q}%" if q else None,
                        "from": from_,
                        "to": to,
                        "limit": limit + 1,
                    },
                )
            )
            .mappings()
            .all()
        )
    items = [event_view(row) for row in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        next_cursor = base64.urlsafe_b64encode(
            json.dumps({"seq": items[-1].release_seq, "filters": signature}).encode()
        ).decode()
    return EventList(
        data=items, meta=EventPageMeta(request_id=request.state.request_id, next_cursor=next_cursor)
    )


@router.get("/{run_id}/events/{event_id}", response_model=EventEnvelope, operation_id="events_get")
async def get_event(run_id: UUID, event_id: UUID, request: Request) -> EventEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        row = (
            (
                await session.execute(
                    text("""SELECT id,run_id,release_seq,event_time,ingested_at,
            source,asset_id,username,src_ip,request_json,response_json,log_json
            FROM app.events WHERE run_id=:run AND id=:event"""),
                    {"run": run_id, "event": event_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise auth.AuthError(404, "NOT_FOUND")
    return EventEnvelope(data=event_view(row), meta=meta(request))


async def alert_view(session: object, row: Mapping[Any, Any]) -> AlertView:
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    evidence = (
        (
            await session.execute(
                text("""SELECT event_id FROM app.detection_evidence
        WHERE detection_id=:id ORDER BY event_id"""),
                {"id": row["detection_id"]},
            )
        )
        .scalars()
        .all()
    )
    return AlertView(
        id=row["id"],
        run_id=row["run_id"],
        severity=row["severity"],
        detector_type=row["detector_type"],
        detector_version=row["detector_version"],
        correlation_key=row["correlation_key"],
        explanation=row["explanation"],
        evidence_ids=list(evidence),
        ticket_id=row["ticket_id"],
        created_at=row["created_at"],
    )


ALERT_QUERY = """SELECT a.id,a.run_id,a.detection_id,a.severity,a.created_at,
 d.detector_type,d.detector_version,d.correlation_key,d.explanation,
 ta.ticket_id FROM app.alerts a JOIN app.detections d
 ON d.run_id=a.run_id AND d.id=a.detection_id
 LEFT JOIN app.ticket_alerts ta ON ta.run_id=a.run_id AND ta.alert_id=a.id"""


@router.get("/{run_id}/alerts", response_model=AlertList, operation_id="alerts_list")
async def list_alerts(
    run_id: UUID,
    request: Request,
    cursor: UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    severity: str | None = None,
    detector_type: str | None = None,
) -> AlertList:
    if severity is not None and severity not in {"low", "medium", "high", "critical"}:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    if detector_type is not None and detector_type not in {"rule", "anomaly"}:
        raise auth.AuthError(422, "VALIDATION_ERROR")
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        rows = (
            (
                await session.execute(
                    text(
                        ALERT_QUERY
                        + """ WHERE a.run_id=:run
            AND (CAST(:cursor AS uuid) IS NULL OR a.id>:cursor)
            AND (CAST(:severity AS text) IS NULL OR a.severity=:severity)
            AND (CAST(:kind AS text) IS NULL OR d.detector_type=:kind)
            ORDER BY a.id LIMIT :limit"""
                    ),
                    {
                        "run": run_id,
                        "cursor": cursor,
                        "severity": severity,
                        "kind": detector_type,
                        "limit": limit + 1,
                    },
                )
            )
            .mappings()
            .all()
        )
        items = [await alert_view(session, row) for row in rows[:limit]]
    next_cursor = str(items[-1].id) if len(rows) > limit else None
    return AlertList(
        data=items, meta=EventPageMeta(request_id=request.state.request_id, next_cursor=next_cursor)
    )


@router.get("/{run_id}/alerts/{alert_id}", response_model=AlertEnvelope, operation_id="alerts_get")
async def get_alert(run_id: UUID, alert_id: UUID, request: Request) -> AlertEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await get_owned_run(session, run_id, user["id"])
        row = (
            (
                await session.execute(
                    text(ALERT_QUERY + " WHERE a.run_id=:run AND a.id=:id"),
                    {"run": run_id, "id": alert_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise auth.AuthError(404, "NOT_FOUND")
        item = await alert_view(session, row)
    return AlertEnvelope(data=item, meta=meta(request))

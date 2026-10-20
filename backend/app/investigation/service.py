"""Run-scoped investigation mutations; history is append-only."""

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthError
from app.investigation.models import (
    DeleteInput,
    NoteCreate,
    NotePatch,
    TicketCreate,
    TicketPatch,
)
from app.runs.idempotency import complete, reserve
from app.runs.service import get_owned_run


def cleaned(value: str) -> str:
    result = value.strip()
    if not result:
        raise AuthError(422, "VALIDATION_ERROR")
    return result


async def mutable_run(session: AsyncSession, run_id: UUID, owner: UUID) -> None:
    # Lock the run before editing child records so finish/pause cannot race a mutation.
    run = await get_owned_run(session, run_id, owner, lock=True)
    if run["status"] not in {"running", "paused", "reviewing"}:
        raise AuthError(409, "RUN_READ_ONLY")


async def ticket_row(
    session: AsyncSession, run_id: UUID, ticket_id: UUID, *, lock: bool = False
) -> Mapping[Any, Any]:
    suffix = " FOR UPDATE" if lock else ""
    row = (
        (
            await session.execute(
                text("SELECT * FROM app.tickets WHERE run_id=:run AND id=:id" + suffix),
                {"run": run_id, "id": ticket_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise AuthError(404, "NOT_FOUND")
    return row


async def ticket_view(session: AsyncSession, row: Mapping[Any, Any]) -> dict[str, Any]:
    evidence = (
        (
            await session.execute(
                text("""SELECT event_id FROM app.ticket_events
        WHERE run_id=:run AND ticket_id=:ticket ORDER BY event_id"""),
                {"run": row["run_id"], "ticket": row["id"]},
            )
        )
        .scalars()
        .all()
    )
    latest = (
        (
            await session.execute(
                text("""SELECT id,revision,author_user_id,
        disposition,reason,created_at FROM app.assessments
        WHERE run_id=:run AND ticket_id=:ticket ORDER BY revision DESC LIMIT 1"""),
                {"run": row["run_id"], "ticket": row["id"]},
            )
        )
        .mappings()
        .first()
    )
    fields = (
        "id",
        "run_id",
        "origin",
        "correlation_key",
        "title",
        "severity",
        "human_severity_override",
        "status",
        "version",
        "deleted_at",
        "created_at",
        "updated_at",
    )
    return {key: row[key] for key in fields} | {
        "evidence_ids": list(evidence),
        "latest_assessment": dict(latest) if latest else None,
    }


async def check_events(
    session: AsyncSession, run_id: UUID, ids: list[UUID], ticket_id: UUID | None = None
) -> None:
    # Evidence IDs are accepted only if every ID belongs to this run (and, when
    # supplied, to this ticket); partial matches are rejected as a whole.
    if not ids:
        return
    if ticket_id is None:
        found = (
            (
                await session.execute(
                    text("""SELECT id FROM app.events
            WHERE run_id=:run AND id=ANY(:ids)"""),
                    {"run": run_id, "ids": ids},
                )
            )
            .scalars()
            .all()
        )
    else:
        found = (
            (
                await session.execute(
                    text("""SELECT event_id FROM app.ticket_events
            WHERE run_id=:run AND ticket_id=:ticket AND event_id=ANY(:ids)"""),
                    {"run": run_id, "ticket": ticket_id, "ids": ids},
                )
            )
            .scalars()
            .all()
        )
    if set(found) != set(ids):
        raise AuthError(422, "INVALID_EVIDENCE")


async def audit(
    session: AsyncSession,
    run_id: UUID,
    actor: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    reason: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        text("""INSERT INTO app.audit_logs
        (id,run_id,actor_user_id,actor_role,action,entity_type,entity_id,
         before_json,after_json,reason)
        VALUES (:id,:run,:actor,'analyst',:action,:kind,:entity,
                CAST(:before AS jsonb),CAST(:after AS jsonb),:reason)"""),
        {
            "id": uuid4(),
            "run": run_id,
            "actor": actor,
            "action": action,
            "kind": entity_type,
            "entity": entity_id,
            "reason": reason,
            "before": json.dumps(before, default=str) if before else None,
            "after": json.dumps(after, default=str) if after else None,
        },
    )


async def create_ticket(
    session: AsyncSession, run_id: UUID, owner: UUID, body: TicketCreate, key: UUID
) -> dict[str, Any]:
    # Idempotency reservation, ticket, evidence links, audit, and cached response
    # share the caller's transaction so retries cannot create duplicate tickets.
    request_id, cached = await reserve(
        session, owner, f"/runs/{run_id}/tickets", key, body.model_dump(mode="json")
    )
    if cached is not None:
        return cached
    await mutable_run(session, run_id, owner)
    await check_events(session, run_id, body.evidence_ids)
    ticket_id = uuid4()
    row = (
        (
            await session.execute(
                text("""INSERT INTO app.tickets
        (id,run_id,origin,title,severity) VALUES (:id,:run,'manual',:title,:severity)
        RETURNING *"""),
                {
                    "id": ticket_id,
                    "run": run_id,
                    "title": cleaned(body.title),
                    "severity": body.severity,
                },
            )
        )
        .mappings()
        .one()
    )
    for event_id in body.evidence_ids:
        await session.execute(
            text("""INSERT INTO app.ticket_events
            (run_id,ticket_id,event_id) VALUES (:run,:ticket,:event)"""),
            {"run": run_id, "ticket": ticket_id, "event": event_id},
        )
    await audit(
        session,
        run_id,
        owner,
        "ticket.create",
        "ticket",
        ticket_id,
        cleaned(body.reason),
        after={"version": 1},
    )
    result = await ticket_view(session, row)
    await complete(session, request_id, result, ticket_id)
    return result


VALID_TRANSITIONS = {
    # Keep status changes explicit; callers cannot jump from open straight to closed.
    "open": {"open", "investigating"},
    "investigating": {"investigating", "resolved"},
    "resolved": {"resolved", "investigating", "closed"},
    "closed": {"closed", "investigating"},
}


async def patch_ticket(
    session: AsyncSession, run_id: UUID, ticket_id: UUID, owner: UUID, body: TicketPatch
) -> dict[str, Any]:
    await mutable_run(session, run_id, owner)
    row = await ticket_row(session, run_id, ticket_id, lock=True)
    if row["deleted_at"] is not None:
        raise AuthError(409, "TICKET_DELETED")
    if row["version"] != body.expected_version:
        raise AuthError(409, "VERSION_CONFLICT")
    # Validate the state machine before writing either the ticket or its assessment.
    next_status = body.status or row["status"]
    if next_status not in VALID_TRANSITIONS[row["status"]]:
        raise AuthError(409, "INVALID_TICKET_STATE")
    latest = (
        (
            await session.execute(
                text("""SELECT revision,disposition FROM app.assessments
        WHERE ticket_id=:id ORDER BY revision DESC LIMIT 1"""),
                {"id": ticket_id},
            )
        )
        .mappings()
        .first()
    )
    disposition = body.disposition or (latest["disposition"] if latest else None)
    if next_status in {"resolved", "closed"} and disposition is None:
        raise AuthError(422, "ASSESSMENT_REQUIRED")
    reason = cleaned(body.reason)
    updated = (
        (
            await session.execute(
                text("""UPDATE app.tickets SET
        title=COALESCE(:title,title),severity=COALESCE(:severity,severity),
        human_severity_override=CASE WHEN :severity IS NULL
            THEN human_severity_override ELSE true END,
        status=:status,version=version+1,updated_at=clock_timestamp()
        WHERE id=:id RETURNING *"""),
                {
                    "title": cleaned(body.title) if body.title is not None else None,
                    "severity": body.severity,
                    "status": next_status,
                    "id": ticket_id,
                },
            )
        )
        .mappings()
        .one()
    )
    if body.disposition is not None:
        await session.execute(
            text("""INSERT INTO app.assessments
            (id,run_id,ticket_id,revision,author_user_id,disposition,reason)
            VALUES (:id,:run,:ticket,:revision,:author,:disposition,:reason)"""),
            {
                "id": uuid4(),
                "run": run_id,
                "ticket": ticket_id,
                "revision": (latest["revision"] if latest else 0) + 1,
                "author": owner,
                "disposition": body.disposition,
                "reason": reason,
            },
        )
    await audit(
        session,
        run_id,
        owner,
        "ticket.update",
        "ticket",
        ticket_id,
        reason,
        before={"version": row["version"], "status": row["status"]},
        after={"version": updated["version"], "status": next_status},
    )
    return await ticket_view(session, updated)


async def delete_or_restore_ticket(
    session: AsyncSession,
    run_id: UUID,
    ticket_id: UUID,
    owner: UUID,
    body: DeleteInput,
    restore: bool,
) -> dict[str, Any]:
    await mutable_run(session, run_id, owner)
    row = await ticket_row(session, run_id, ticket_id, lock=True)
    if row["version"] != body.expected_version:
        raise AuthError(409, "VERSION_CONFLICT")
    if (row["deleted_at"] is None) == restore:
        raise AuthError(409, "INVALID_TICKET_STATE")
    reason = cleaned(body.reason)
    updated = (
        (
            await session.execute(
                text("""UPDATE app.tickets SET
        deleted_at=CASE WHEN :restore THEN NULL ELSE clock_timestamp() END,
        deleted_by=CASE WHEN :restore THEN NULL ELSE CAST(:actor AS uuid) END,
        delete_reason=CASE WHEN :restore THEN NULL ELSE :reason END,
        version=version+1,updated_at=clock_timestamp()
        WHERE id=:id RETURNING *"""),
                {"restore": restore, "actor": owner, "reason": reason, "id": ticket_id},
            )
        )
        .mappings()
        .one()
    )
    await audit(
        session,
        run_id,
        owner,
        "ticket.restore" if restore else "ticket.delete",
        "ticket",
        ticket_id,
        reason,
        before={"version": row["version"]},
        after={"version": updated["version"]},
    )
    return await ticket_view(session, updated)


async def note_row(
    session: AsyncSession, run_id: UUID, ticket_id: UUID, note_id: UUID, *, lock: bool = False
) -> Mapping[Any, Any]:
    suffix = " FOR UPDATE" if lock else ""
    row = (
        (
            await session.execute(
                text(
                    """SELECT * FROM app.notes
        WHERE run_id=:run AND ticket_id=:ticket AND id=:note"""
                    + suffix
                ),
                {"run": run_id, "ticket": ticket_id, "note": note_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise AuthError(404, "NOT_FOUND")
    return row


async def note_view(session: AsyncSession, row: Mapping[Any, Any]) -> dict[str, Any]:
    evidence = (
        (
            await session.execute(
                text("""SELECT event_id FROM app.note_evidence
        WHERE note_id=:note ORDER BY event_id"""),
                {"note": row["id"]},
            )
        )
        .scalars()
        .all()
    )
    return {
        key: row[key]
        for key in (
            "id",
            "ticket_id",
            "owner_user_id",
            "body",
            "version",
            "deleted_at",
            "created_at",
            "updated_at",
        )
    } | {"evidence_ids": list(evidence)}


async def snapshot_note(
    session: AsyncSession,
    row: Mapping[Any, Any],
    actor: UUID,
    kind: str,
    reason: str | None,
    evidence: list[UUID],
) -> None:
    # Preserve the prior note body and evidence as an immutable revision before later edits.
    version_id = uuid4()
    await session.execute(
        text("""INSERT INTO app.note_versions
        (id,run_id,ticket_id,note_id,version,body,change_kind,reason,actor_user_id)
        VALUES (:id,:run,:ticket,:note,:version,:body,:kind,:reason,:actor)"""),
        {
            "id": version_id,
            "run": row["run_id"],
            "ticket": row["ticket_id"],
            "note": row["id"],
            "version": row["version"],
            "body": row["body"],
            "kind": kind,
            "reason": reason,
            "actor": actor,
        },
    )
    for event_id in evidence:
        await session.execute(
            text("""INSERT INTO app.note_version_evidence
            (run_id,note_version_id,event_id) VALUES (:run,:version,:event)"""),
            {"run": row["run_id"], "version": version_id, "event": event_id},
        )


async def create_note(
    session: AsyncSession, run_id: UUID, ticket_id: UUID, owner: UUID, body: NoteCreate, key: UUID
) -> dict[str, Any]:
    request_id, cached = await reserve(
        session,
        owner,
        f"/runs/{run_id}/tickets/{ticket_id}/notes",
        key,
        body.model_dump(mode="json"),
    )
    if cached is not None:
        return cached
    await mutable_run(session, run_id, owner)
    ticket = await ticket_row(session, run_id, ticket_id, lock=True)
    if ticket["deleted_at"] is not None:
        raise AuthError(409, "TICKET_DELETED")
    await check_events(session, run_id, body.evidence_ids, ticket_id)
    note_id = uuid4()
    row = (
        (
            await session.execute(
                text("""INSERT INTO app.notes
        (id,run_id,ticket_id,owner_user_id,body)
        VALUES (:id,:run,:ticket,:owner,:body) RETURNING *"""),
                {
                    "id": note_id,
                    "run": run_id,
                    "ticket": ticket_id,
                    "owner": owner,
                    "body": cleaned(body.body),
                },
            )
        )
        .mappings()
        .one()
    )
    for event_id in body.evidence_ids:
        await session.execute(
            text("""INSERT INTO app.note_evidence
            (run_id,ticket_id,note_id,event_id) VALUES (:run,:ticket,:note,:event)"""),
            {"run": run_id, "ticket": ticket_id, "note": note_id, "event": event_id},
        )
    await snapshot_note(session, row, owner, "create", None, body.evidence_ids)
    await audit(session, run_id, owner, "note.create", "note", note_id, None, after={"version": 1})
    result = await note_view(session, row)
    await complete(session, request_id, result, note_id)
    return result


async def mutate_note(
    session: AsyncSession,
    run_id: UUID,
    ticket_id: UUID,
    note_id: UUID,
    owner: UUID,
    action: str,
    body: NotePatch | DeleteInput,
) -> dict[str, Any]:
    # Lock parent then note, matching ticket operations and preventing edits to a deleted case.
    await mutable_run(session, run_id, owner)
    ticket = await ticket_row(session, run_id, ticket_id, lock=True)
    if ticket["deleted_at"] is not None:
        raise AuthError(409, "TICKET_DELETED")
    row = await note_row(session, run_id, ticket_id, note_id, lock=True)
    if row["owner_user_id"] != owner:
        raise AuthError(404, "NOT_FOUND")
    if row["version"] != body.expected_version:
        raise AuthError(409, "VERSION_CONFLICT")
    if action == "restore" and row["deleted_at"] is None:
        raise AuthError(409, "INVALID_NOTE_STATE")
    if action != "restore" and row["deleted_at"] is not None:
        raise AuthError(409, "NOTE_DELETED")
    reason = cleaned(body.reason)
    ids = (
        body.evidence_ids
        if isinstance(body, NotePatch)
        else (
            await session.execute(
                text("SELECT event_id FROM app.note_evidence WHERE note_id=:note"),
                {"note": note_id},
            )
        )
        .scalars()
        .all()
    )
    await check_events(session, run_id, list(ids), ticket_id)
    updated = (
        (
            await session.execute(
                text("""UPDATE app.notes SET
        body=COALESCE(:body,body),version=version+1,updated_at=clock_timestamp(),
        deleted_at=CASE WHEN :action='delete' THEN clock_timestamp()
                        WHEN :action='restore' THEN NULL ELSE deleted_at END,
        deleted_by=CASE WHEN :action='delete' THEN CAST(:actor AS uuid)
                        WHEN :action='restore' THEN NULL ELSE deleted_by END,
        delete_reason=CASE WHEN :action='delete' THEN :reason
                           WHEN :action='restore' THEN NULL ELSE delete_reason END
        WHERE id=:note RETURNING *"""),
                {
                    "body": cleaned(body.body) if isinstance(body, NotePatch) else None,
                    "action": action,
                    "actor": owner,
                    "reason": reason,
                    "note": note_id,
                },
            )
        )
        .mappings()
        .one()
    )
    if isinstance(body, NotePatch):
        await session.execute(
            text("DELETE FROM app.note_evidence WHERE note_id=:note"), {"note": note_id}
        )
        for event_id in ids:
            await session.execute(
                text("""INSERT INTO app.note_evidence
                (run_id,ticket_id,note_id,event_id) VALUES (:run,:ticket,:note,:event)"""),
                {"run": run_id, "ticket": ticket_id, "note": note_id, "event": event_id},
            )
    await snapshot_note(session, updated, owner, action, reason, list(ids))
    await audit(
        session,
        run_id,
        owner,
        f"note.{action}",
        "note",
        note_id,
        reason,
        before={"version": row["version"]},
        after={"version": updated["version"]},
    )
    return await note_view(session, updated)

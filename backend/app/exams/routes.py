"""Blind exam APIs. All admission, evidence, ownership and review checks run server-side."""

import hashlib
import json
from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth
from app.exams.models import (
    AttemptData,
    AttemptEnvelope,
    AttemptView,
    ExamEvent,
    InstructorAttemptData,
    InstructorAttemptEnvelope,
    ResultCriterion,
    ResultData,
    ResultEnvelope,
    ReviewInput,
    StartAttemptInput,
    SubmitInput,
)
from app.grading.exam_policy import (
    MAX_ATTEMPTS_PER_CASE_PER_WINDOW,
    check_admission,
    validate_submission_evidence,
)
from app.grading.rubric import FOUNDATIONS_RUBRIC, score_rubric
from app.http_models import ErrorEnvelope, Meta
from app.learning.catalog import LESSON_ID, LEVEL_ID
from app.runs.service import effective_ms, server_time, start_run
from app.scenarios.models import ScenarioView, TrainingSelection

router = APIRouter(
    prefix="/api/v1",
    tags=["Exams"],
    include_in_schema=False,
    responses={
        status: {"model": ErrorEnvelope} for status in (400, 401, 403, 404, 409, 422, 429, 503)
    },
)


def meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


def key_from_header(value: str | None) -> UUID:
    try:
        return UUID(value or "")
    except ValueError:
        raise auth.AuthError(400, "IDEMPOTENCY_KEY_REQUIRED") from None


def route_for_level(level_id: UUID) -> str:
    return f"/learning/levels/{level_id}/attempts"


def start_hash(level_id: UUID, progress_version: int) -> str:
    encoded = json.dumps(
        {"level_id": str(level_id), "expected_progress_version": progress_version},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


async def write_guard(session: AsyncSession, request: Request) -> Mapping[str, Any]:
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise auth.AuthError(415, "UNSUPPORTED_MEDIA_TYPE")
    await auth.csrf_check(session, request)
    user = await auth.require_user(session, request)
    if user["role"] != "analyst":
        raise auth.AuthError(403, "FORBIDDEN")
    return user


async def _attempt_row(
    session: AsyncSession, attempt_id: UUID, user_id: UUID, *, lock: bool = False
) -> Any:
    suffix = " FOR UPDATE" if lock else ""
    row = (
        (
            await session.execute(
                text(
                    """SELECT id,owner_user_id,level_id,run_id,case_id,status,version,
                   started_at,expires_at,submitted_at
                   FROM app.exam_attempts WHERE id=:attempt AND owner_user_id=:owner"""
                    + suffix
                ),
                {"attempt": attempt_id, "owner": user_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise auth.AuthError(404, "NOT_FOUND")
    return row


async def _event_rows(session: AsyncSession, run_id: UUID) -> list[ExamEvent]:
    rows = (
        (
            await session.execute(
                text("""SELECT id,run_id,release_seq,event_time,ingested_at,source,asset_id,
                   username,src_ip,request_json,response_json,log_json
                   FROM app.events WHERE run_id=:run ORDER BY release_seq"""),
                {"run": run_id},
            )
        )
        .mappings()
        .all()
    )
    return [
        ExamEvent(
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
        for row in rows
    ]


def _view(row: Any) -> AttemptView:
    return AttemptView(
        id=row["id"],
        run_id=row["run_id"],
        level_id=row["level_id"],
        status=row["status"],
        version=row["version"],
        started_at=row["started_at"],
        expires_at=row["expires_at"],
        submitted_at=row["submitted_at"],
    )


async def _learner_answer(session: AsyncSession, attempt_id: UUID) -> dict[str, object] | None:
    row = (
        (
            await session.execute(
                text("""SELECT evidence_event_ids,severity,disposition,reason,frozen_at
                   FROM app.exam_answers WHERE attempt_id=:attempt"""),
                {"attempt": attempt_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return {
        "evidence_event_ids": row["evidence_event_ids"],
        "severity": row["severity"],
        "disposition": row["disposition"],
        "reason": row["reason"],
        "submitted_at": row["frozen_at"],
    }


async def _result(session: AsyncSession, attempt: Mapping[str, Any]) -> ResultData:
    grade = (
        (
            await session.execute(
                text("""SELECT score,criteria_json FROM app.grading_revisions
                   WHERE attempt_id=:attempt ORDER BY revision DESC LIMIT 1"""),
                {"attempt": attempt["id"]},
            )
        )
        .mappings()
        .first()
    )
    criteria = []
    score = None
    if grade:
        score = grade["score"]
        criteria = [ResultCriterion.model_validate(item) for item in grade["criteria_json"]]
    return ResultData(
        attempt_id=attempt["id"], status=attempt["status"], score=score, criteria=criteria
    )


@router.post(
    "/learning/levels/{level_id}/attempts", response_model=AttemptEnvelope, status_code=201
)
async def start_attempt(
    level_id: UUID,
    body: StartAttemptInput,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> AttemptEnvelope:
    key = key_from_header(idempotency_key)
    await auth.rate_limit(request, "exam_start")
    route = route_for_level(level_id)
    async with auth.database(request).sessions() as session, session.begin():
        user = await write_guard(session, request)
        owner = user["id"]
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
            {"owner": str(owner)},
        )
        digest = start_hash(level_id, body.expected_progress_version)
        previous = (
            (
                await session.execute(
                    text("""SELECT request_hash,resource_id FROM app.idempotency_keys
                       WHERE user_id=:owner AND method='POST' AND route_key=:route AND key=:key"""),
                    {"owner": owner, "route": route, "key": key},
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != digest or previous["resource_id"] is None:
                raise auth.AuthError(409, "IDEMPOTENCY_CONFLICT")
            attempt = await _attempt_row(session, previous["resource_id"], owner)
            events = await _event_rows(session, attempt["run_id"])
            answer = await _learner_answer(session, attempt["id"])
            return AttemptEnvelope(
                data=AttemptData(**_view(attempt).model_dump(), events=events, answer=answer),
                meta=meta(request),
            )

        if level_id != LEVEL_ID:
            unlocked = await session.scalar(
                text("SELECT 1 FROM app.level_unlocks WHERE user_id=:owner AND level_id=:level"),
                {"owner": owner, "level": level_id},
            )
            if not unlocked:
                raise auth.AuthError(404, "NOT_FOUND")

        progress = (
            (
                await session.execute(
                    text("""SELECT p.version,p.completed_at FROM app.user_lesson_progress p
                       JOIN app.lessons l ON l.id=p.lesson_id AND l.level_id=:level
                       WHERE p.user_id=:owner AND p.lesson_id=:lesson
                       ORDER BY l.version DESC LIMIT 1 FOR UPDATE OF p"""),
                    {"level": level_id, "owner": owner, "lesson": LESSON_ID},
                )
            )
            .mappings()
            .first()
        )
        if progress is None or progress["completed_at"] is None:
            raise auth.AuthError(409, "LESSON_REQUIRED")
        if progress["version"] != body.expected_progress_version:
            raise auth.AuthError(409, "VERSION_CONFLICT")

        now = await server_time(session)
        await session.execute(
            text("""UPDATE app.exam_attempts SET status='expired',version=version+1
               WHERE owner_user_id=:owner AND status='in_progress' AND expires_at<=:now"""),
            {"owner": owner, "now": now},
        )
        await session.execute(
            text("""UPDATE app.runs r SET status='failed',failure_code='EXAM_EXPIRED',
               resumed_at=NULL,version=version+1
               WHERE r.mode='exam' AND r.status IN ('running','reviewing')
                 AND EXISTS(SELECT 1 FROM app.exam_attempts a
                   WHERE a.run_id=r.id AND a.owner_user_id=:owner AND a.status='expired')"""),
            {"owner": owner},
        )
        active_statuses = (
            (
                await session.execute(
                    text("""SELECT status FROM app.exam_attempts WHERE owner_user_id=:owner
                   AND status IN ('in_progress','submitted','needs_review')"""),
                    {"owner": owner},
                )
            )
            .scalars()
            .all()
        )
        history = (
            (
                await session.execute(
                    text("""SELECT status,started_at,coalesce(finalized_at,expires_at) AS failed_at
                       FROM app.exam_attempts
                       WHERE owner_user_id=:owner AND level_id=:level
                         AND started_at>:cutoff ORDER BY started_at"""),
                    {"owner": owner, "level": level_id, "cutoff": now - timedelta(hours=24)},
                )
            )
            .mappings()
            .all()
        )
        decision = check_admission(
            active_statuses=active_statuses,
            started_at=[row["started_at"] for row in history],
            last_failed_at=max(
                (row["failed_at"] for row in history if row["status"] in {"failed", "expired"}),
                default=None,
            ),
            now=now,
        )
        if not decision.allowed:
            code = decision.code or "EXAM_UNAVAILABLE"
            raise auth.AuthError(
                429 if code.endswith("QUOTA_EXCEEDED") else 409,
                code,
            )

        selected = (
            (
                await session.execute(
                    text("""SELECT s.id,s.version,s.public_title AS title,s.difficulty,
                       c.duration_ms,s.learning_objectives,c.id AS exam_case_id
                       FROM app.exam_cases c JOIN app.scenarios s ON s.id=c.scenario_id
                       WHERE c.level_id=:level AND c.enabled AND s.enabled AND s.purpose='exam'
                       AND (SELECT count(*) FROM app.exam_attempts a
                         WHERE a.owner_user_id=:owner AND a.case_id=c.id
                           AND a.started_at>:cutoff) < :case_limit
                       ORDER BY (SELECT count(*) FROM app.exam_attempts a
                         WHERE a.owner_user_id=:owner AND a.case_id=c.id
                           AND a.started_at>:cutoff), random() LIMIT 1"""),
                    {
                        "level": level_id,
                        "owner": owner,
                        "cutoff": now - timedelta(hours=24),
                        "case_limit": MAX_ATTEMPTS_PER_CASE_PER_WINDOW,
                    },
                )
            )
            .mappings()
            .first()
        )
        if selected is None:
            selected = (
                (
                    await session.execute(
                        text("""SELECT s.id,s.version,s.public_title AS title,s.difficulty,
                           c.duration_ms,s.learning_objectives,c.id AS exam_case_id
                           FROM app.exam_cases c JOIN app.scenarios s ON s.id=c.scenario_id
                           WHERE c.level_id=:level AND c.enabled AND s.enabled AND s.purpose='exam'
                           ORDER BY random() LIMIT 1"""),
                        {"level": level_id},
                    )
                )
                .mappings()
                .first()
            )
        if selected is None:
            raise auth.AuthError(503, "EXAM_UNAVAILABLE")
        scenario = ScenarioView.model_validate(
            {
                key: selected[key]
                for key in (
                    "id",
                    "version",
                    "title",
                    "difficulty",
                    "duration_ms",
                    "learning_objectives",
                )
            }
        )
        start_body = TrainingSelection(scenario_ids=[scenario.id])
        run, created = await start_run(
            session,
            owner,
            start_body,
            key,
            mode="exam",
            route_key=route,
            request_digest=digest,
            selected_scenarios=[scenario],
        )
        run_id = UUID(str(run["id"]))
        attempt_id = uuid4()
        await session.execute(
            text("""INSERT INTO app.exam_attempts
               (id,owner_user_id,level_id,case_id,run_id,status,rubric_version,expires_at)
               VALUES (:id,:owner,:level,:case,:run,'in_progress',:rubric,:expires)"""),
            {
                "id": attempt_id,
                "owner": owner,
                "level": level_id,
                "case": selected["exam_case_id"],
                "run": run_id,
                "rubric": FOUNDATIONS_RUBRIC.version,
                "expires": now + timedelta(hours=24),
            },
        )
        await session.execute(
            text("""UPDATE app.idempotency_keys SET resource_id=:attempt
               WHERE user_id=:owner AND method='POST' AND route_key=:route AND key=:key"""),
            {"attempt": attempt_id, "owner": owner, "route": route, "key": key},
        )
        await session.execute(
            text("""INSERT INTO app.audit_logs
               (id,actor_user_id,actor_role,action,entity_type,entity_id,request_id)
               VALUES (:id,:owner,'analyst','exam.attempt.start','exam_attempt',
                       :attempt,:request)"""),
            {
                "id": uuid4(),
                "owner": owner,
                "attempt": attempt_id,
                "request": request.state.request_id,
            },
        )
        attempt = await _attempt_row(session, attempt_id, owner)
        events = await _event_rows(session, run_id)
    return AttemptEnvelope(
        data=AttemptData(**_view(attempt).model_dump(), events=events, answer=None),
        meta=meta(request),
    )


@router.get("/exam/attempts/active", response_model=AttemptEnvelope)
async def get_active_attempt(request: Request) -> AttemptEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        attempt_id = await session.scalar(
            text("""SELECT id FROM app.exam_attempts WHERE owner_user_id=:owner
               AND status IN ('in_progress','submitted','needs_review')
               ORDER BY started_at DESC LIMIT 1"""),
            {"owner": user["id"]},
        )
        if attempt_id is None:
            raise auth.AuthError(404, "NOT_FOUND")
        attempt = await _attempt_row(session, attempt_id, user["id"])
        events = await _event_rows(session, attempt["run_id"])
        answer = await _learner_answer(session, attempt_id)
    return AttemptEnvelope(
        data=AttemptData(**_view(attempt).model_dump(), events=events, answer=answer),
        meta=meta(request),
    )


@router.get("/exam/attempts/latest/result", response_model=ResultEnvelope)
async def get_latest_final_result(request: Request) -> ResultEnvelope:
    """Return only the caller's most recent final outcome for refresh recovery."""
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        attempt = (
            (
                await session.execute(
                    text("""SELECT id,status FROM app.exam_attempts
                       WHERE owner_user_id=:owner AND status IN ('passed','failed','expired')
                       ORDER BY started_at DESC,id DESC LIMIT 1"""),
                    {"owner": user["id"]},
                )
            )
            .mappings()
            .first()
        )
        if attempt is None:
            raise auth.AuthError(404, "NOT_FOUND")
        result = await _result(session, attempt)
    return ResultEnvelope(data=result, meta=meta(request))


@router.get("/exam/attempts/{attempt_id}", response_model=AttemptEnvelope)
async def get_attempt(attempt_id: UUID, request: Request) -> AttemptEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        attempt = await _attempt_row(session, attempt_id, user["id"])
        events = await _event_rows(session, attempt["run_id"])
        answer = await _learner_answer(session, attempt_id)
    return AttemptEnvelope(
        data=AttemptData(**_view(attempt).model_dump(), events=events, answer=answer),
        meta=meta(request),
    )


@router.post("/exam/attempts/{attempt_id}/submit", response_model=ResultEnvelope)
async def submit_attempt(
    attempt_id: UUID,
    body: SubmitInput,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> ResultEnvelope:
    key = key_from_header(idempotency_key)
    await auth.rate_limit(request, "exam_submit")
    route = f"/exam/attempts/{attempt_id}/submit"
    payload = body.model_dump(mode="json")
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    async with auth.database(request).sessions() as session, session.begin():
        user = await write_guard(session, request)
        owner = user["id"]
        initial = await _attempt_row(session, attempt_id, owner)
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
            {"owner": str(owner)},
        )
        previous = (
            (
                await session.execute(
                    text("""SELECT request_hash,response_json FROM app.idempotency_keys
                       WHERE user_id=:owner AND method='POST' AND route_key=:route AND key=:key"""),
                    {"owner": owner, "route": route, "key": key},
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != digest:
                raise auth.AuthError(409, "IDEMPOTENCY_CONFLICT")
            return ResultEnvelope(
                data=ResultData.model_validate(previous["response_json"]), meta=meta(request)
            )
        run = (
            (
                await session.execute(
                    text("""SELECT id,status,elapsed_ms,duration_ms,resumed_at,owner_user_id,
                       release_cursor
                       FROM app.runs WHERE id=:run AND owner_user_id=:owner
                         AND mode='exam' FOR UPDATE"""),
                    {"run": initial["run_id"], "owner": owner},
                )
            )
            .mappings()
            .first()
        )
        if run is None:
            raise auth.AuthError(404, "NOT_FOUND")
        attempt = await _attempt_row(session, attempt_id, owner, lock=True)
        if attempt["status"] != "in_progress":
            raise auth.AuthError(409, "ALREADY_SUBMITTED")
        if attempt["version"] != body.expected_version:
            raise auth.AuthError(409, "VERSION_CONFLICT")
        now = await server_time(session)
        if attempt["expires_at"] <= now:
            await session.execute(
                text("""UPDATE app.exam_attempts SET status='expired',version=version+1
                   WHERE id=:attempt AND status='in_progress'"""),
                {"attempt": attempt_id},
            )
            await session.execute(
                text("""UPDATE app.runs SET status='failed',failure_code='EXAM_EXPIRED',
                   resumed_at=NULL,version=version+1 WHERE id=:run AND mode='exam'
                     AND status IN ('running','reviewing')"""),
                {"run": attempt["run_id"]},
            )
            return ResultEnvelope(
                data=ResultData(attempt_id=attempt_id, status="expired"), meta=meta(request)
            )
        if run["status"] not in {"running", "reviewing"}:
            raise auth.AuthError(409, "EXAM_EXPIRED")
        snapshot = (
            (
                await session.execute(
                    text("""SELECT id,content_hash FROM app.events WHERE run_id=:run
                       AND release_seq<=:cutoff ORDER BY release_seq"""),
                    {"run": attempt["run_id"], "cutoff": run["release_cursor"]},
                )
            )
            .mappings()
            .all()
        )
        evidence = validate_submission_evidence(
            body.evidence_event_ids, (row["id"] for row in snapshot)
        )
        dataset_hash = hashlib.sha256(
            ":".join(str(row["content_hash"]) for row in snapshot).encode()
        ).hexdigest()
        answer_hash = hashlib.sha256(
            json.dumps(
                {"answer": payload, "dataset_hash": dataset_hash},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        await session.execute(
            text("""INSERT INTO app.exam_answers
               (attempt_id,evidence_event_ids,severity,disposition,reason,release_cutoff,
                assessment_cutoff,dataset_hash,content_hash,frozen_at)
               VALUES (:attempt,CAST(:evidence AS jsonb),:severity,:disposition,:reason,
                :cutoff,:now,:dataset_hash,:hash,:now)"""),
            {
                "attempt": attempt_id,
                "evidence": json.dumps([str(item) for item in evidence]),
                "severity": body.severity,
                "disposition": body.disposition,
                "reason": body.reason,
                "cutoff": run["release_cursor"],
                "dataset_hash": dataset_hash,
                "hash": answer_hash,
                "now": now,
            },
        )
        elapsed = effective_ms(run, now)
        await session.execute(
            text("""UPDATE app.runs SET status='completed',resumed_at=NULL,elapsed_ms=:elapsed,
               completed_at=:now,version=version+1 WHERE id=:run AND mode='exam'"""),
            {"elapsed": elapsed, "now": now, "run": attempt["run_id"]},
        )
        await session.execute(
            text("""UPDATE app.exam_attempts SET status='needs_review',submitted_at=:now,
               version=version+1 WHERE id=:attempt"""),
            {"now": now, "attempt": attempt_id},
        )
        result_data = ResultData(attempt_id=attempt_id, status="needs_review")
        response_json = result_data.model_dump(mode="json")
        await session.execute(
            text("""INSERT INTO app.idempotency_keys
               (id,user_id,method,route_key,key,request_hash,status,response_status,response_json,
                resource_id,expires_at)
               VALUES (:id,:owner,'POST',:route,:key,:hash,'completed',200,
                CAST(:response AS jsonb),:attempt,:expires)"""),
            {
                "id": uuid4(),
                "owner": owner,
                "route": route,
                "key": key,
                "hash": digest,
                "response": json.dumps(response_json),
                "attempt": attempt_id,
                "expires": now + timedelta(days=30),
            },
        )
        await session.execute(
            text("""INSERT INTO app.audit_logs
               (id,actor_user_id,actor_role,action,entity_type,entity_id,request_id)
               VALUES (:id,:owner,'analyst','exam.submit','exam_attempt',:attempt,:request)"""),
            {
                "id": uuid4(),
                "owner": owner,
                "attempt": attempt_id,
                "request": request.state.request_id,
            },
        )
    return ResultEnvelope(data=result_data, meta=meta(request))


@router.get("/exam/attempts/{attempt_id}/result", response_model=ResultEnvelope)
async def get_result(attempt_id: UUID, request: Request) -> ResultEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        attempt = await _attempt_row(session, attempt_id, user["id"])
        if attempt["status"] == "in_progress":
            raise auth.AuthError(409, "RESULT_LOCKED")
        result = await _result(session, attempt)
    return ResultEnvelope(data=result, meta=meta(request))


@router.get("/admin/exam-attempts/{attempt_id}", response_model=InstructorAttemptEnvelope)
async def instructor_attempt(attempt_id: UUID, request: Request) -> InstructorAttemptEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        if user["role"] != "instructor":
            raise auth.AuthError(403, "FORBIDDEN")
        owner = await session.scalar(
            text("SELECT owner_user_id FROM app.exam_attempts WHERE id=:attempt"),
            {"attempt": attempt_id},
        )
        if owner is None:
            raise auth.AuthError(404, "NOT_FOUND")
        await auth.authorize_assignment(session, user, owner)
        attempt = (
            (
                await session.execute(
                    text("""SELECT id,owner_user_id,level_id,run_id,case_id,status,version,
                       started_at,expires_at,submitted_at FROM app.exam_attempts
                       WHERE id=:attempt"""),
                    {"attempt": attempt_id},
                )
            )
            .mappings()
            .one()
        )
        truth = await session.scalar(
            text("SELECT private.instructor_exam_truth(:actor,:attempt)"),
            {"actor": user["id"], "attempt": attempt_id},
        )
        if truth is None:
            raise auth.AuthError(404, "NOT_FOUND")
        answer = await _learner_answer(session, attempt_id)
        assert answer is not None
        events = await _event_rows(session, attempt["run_id"])
    return InstructorAttemptEnvelope(
        data=InstructorAttemptData(
            attempt=_view(attempt), events=events, answer=answer, private_truth=truth
        ),
        meta=meta(request),
    )


@router.get("/admin/exam-attempts")
async def instructor_exam_queue(request: Request) -> dict[str, object]:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        if user["role"] != "instructor":
            raise auth.AuthError(403, "FORBIDDEN")
        rows = (
            (
                await session.execute(
                    text("""SELECT a.id,a.owner_user_id,u.display_name,a.level_id,a.status,
                       a.version,a.started_at,a.submitted_at
                       FROM app.exam_attempts a JOIN app.users u ON u.id=a.owner_user_id
                       JOIN app.instructor_assignments ia ON ia.analyst_user_id=a.owner_user_id
                       WHERE ia.instructor_user_id=:instructor AND a.status IN
                       ('needs_review','passed','failed')
                       ORDER BY a.submitted_at DESC LIMIT 100"""),
                    {"instructor": user["id"]},
                )
            )
            .mappings()
            .all()
        )
    return {"data": [dict(row) for row in rows], "meta": meta(request).model_dump()}


def rubric_feedback(key: str, value: int | None) -> str:
    if value is None:
        return "ต้องตรวจทานเพิ่มเติม"
    if value == 2:
        return "ทำได้ตามเกณฑ์"
    if value == 1:
        return "มีส่วนที่ทำได้ ควรทบทวนเกณฑ์นี้"
    return "ควรทบทวนแนวทางของเกณฑ์นี้"


@router.post("/admin/exam-attempts/{attempt_id}/review", response_model=ResultEnvelope)
async def review_attempt(attempt_id: UUID, body: ReviewInput, request: Request) -> ResultEnvelope:
    await auth.rate_limit(request, "exam_review")
    async with auth.database(request).sessions() as session, session.begin():
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            raise auth.AuthError(415, "UNSUPPORTED_MEDIA_TYPE")
        await auth.csrf_check(session, request)
        user = await auth.require_user(session, request)
        if user["role"] != "instructor":
            raise auth.AuthError(403, "FORBIDDEN")
        owner = await session.scalar(
            text("SELECT owner_user_id FROM app.exam_attempts WHERE id=:attempt"),
            {"attempt": attempt_id},
        )
        if owner is None:
            raise auth.AuthError(404, "NOT_FOUND")
        await auth.authorize_assignment(session, user, owner)
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
            {"owner": str(owner)},
        )
        attempt_stub = await session.execute(
            text("SELECT run_id FROM app.exam_attempts WHERE id=:attempt"),
            {"attempt": attempt_id},
        )
        run_id = attempt_stub.scalar_one()
        await session.execute(
            text("SELECT id FROM app.runs WHERE id=:run AND mode='exam' FOR UPDATE"),
            {"run": run_id},
        )
        attempt = (
            (
                await session.execute(
                    text("""SELECT id,owner_user_id,level_id,run_id,case_id,status,version,
                       started_at,expires_at,submitted_at FROM app.exam_attempts
                       WHERE id=:attempt FOR UPDATE"""),
                    {"attempt": attempt_id},
                )
            )
            .mappings()
            .one()
        )
        if attempt["version"] != body.expected_version:
            raise auth.AuthError(409, "VERSION_CONFLICT")
        if attempt["status"] not in {"needs_review", "passed", "failed"}:
            raise auth.AuthError(409, "REVIEW_NOT_AVAILABLE")
        truth = await session.scalar(
            text("SELECT private.instructor_exam_truth(:actor,:attempt)"),
            {"actor": user["id"], "attempt": attempt_id},
        )
        if truth is None:
            raise auth.AuthError(404, "NOT_FOUND")
        if not body.reason.strip():
            raise auth.AuthError(422, "VALIDATION_ERROR")
        answer = await _learner_answer(session, attempt_id)
        if answer is None:
            raise auth.AuthError(409, "REVIEW_NOT_AVAILABLE")
        expected_keys = set(truth["expectedEvidenceKeys"])
        events = (
            (
                await session.execute(
                    text("""SELECT id,fixture_event_key FROM app.events WHERE run_id=:run"""),
                    {"run": run_id},
                )
            )
            .mappings()
            .all()
        )
        event_keys = {row["id"]: row["fixture_event_key"] for row in events}
        raw_selected_ids = answer["evidence_event_ids"]
        if not isinstance(raw_selected_ids, list):
            raise auth.AuthError(409, "INVALID_SUBMISSION")
        selected_ids = {UUID(str(item)) for item in raw_selected_ids}
        selected_keys = {event_keys[item] for item in selected_ids if item in event_keys}
        overlap = selected_keys & expected_keys
        evidence_score = 2 if selected_keys == expected_keys else (1 if overlap else 0)
        classification_score = (
            2
            if answer["severity"] == truth["expectedSeverity"]
            and answer["disposition"] == truth["expectedDisposition"]
            else 0
        )
        normalized_scores = dict(body.criterion_scores)
        normalized_scores.update(
            {"evidence": evidence_score, "classification": classification_score}
        )
        grade = score_rubric(normalized_scores)
        criteria = [
            {
                "key": criterion.key,
                "score": normalized_scores.get(criterion.key),
                "maximum": 2,
                "feedback": rubric_feedback(criterion.key, normalized_scores.get(criterion.key)),
            }
            for criterion in FOUNDATIONS_RUBRIC.criteria
        ]
        revision = int(
            await session.scalar(
                text(
                    "SELECT coalesce(max(revision),0)+1 FROM app.grading_revisions "
                    "WHERE attempt_id=:attempt"
                ),
                {"attempt": attempt_id},
            )
            or 1
        )
        grade_id = uuid4()
        await session.execute(
            text("""INSERT INTO app.grading_revisions
               (id,attempt_id,revision,source,rubric_version,status,score,criteria_json,
                reviewer_user_id,reason)
               VALUES (:id,:attempt,:revision,'instructor',:rubric,:status,:score,
                CAST(:criteria AS jsonb),:reviewer,:reason)"""),
            {
                "id": grade_id,
                "attempt": attempt_id,
                "revision": revision,
                "rubric": grade.rubric_version,
                "status": grade.status,
                "score": grade.score,
                "criteria": json.dumps(criteria),
                "reviewer": user["id"],
                "reason": body.reason.strip(),
            },
        )
        finalized = grade.status in {"passed", "failed"}
        await session.execute(
            text("""UPDATE app.exam_attempts SET status=:status,version=version+1,
               finalized_at=CASE WHEN :finalized THEN clock_timestamp() ELSE NULL END
               WHERE id=:attempt"""),
            {"status": grade.status, "finalized": finalized, "attempt": attempt_id},
        )
        if grade.status == "passed":
            cases = int(
                await session.scalar(
                    text("SELECT count(*) FROM app.exam_cases WHERE level_id=:level AND enabled"),
                    {"level": attempt["level_id"]},
                )
                or 0
            )
            passed_cases = int(
                await session.scalar(
                    text("""SELECT count(DISTINCT a.case_id) FROM app.exam_attempts a
                       JOIN app.grading_revisions g ON g.attempt_id=a.id
                       WHERE a.owner_user_id=:owner AND a.level_id=:level AND g.status='passed'
                         AND g.revision=(SELECT max(g2.revision) FROM app.grading_revisions g2
                           WHERE g2.attempt_id=a.id)"""),
                    {"owner": owner, "level": attempt["level_id"]},
                )
                or 0
            )
            if cases > 0 and cases == passed_cases:
                next_level = (
                    await session.execute(
                        text("""SELECT id FROM app.learning_levels
                           WHERE ordinal=(SELECT ordinal+1 FROM app.learning_levels WHERE id=:level)
                             AND enabled ORDER BY version DESC LIMIT 1"""),
                        {"level": attempt["level_id"]},
                    )
                ).scalar_one_or_none()
                if next_level is not None:
                    await session.execute(
                        text("""INSERT INTO app.level_unlocks
                           (user_id,level_id,earned_from_revision_id)
                           VALUES (:owner,:level,:revision)
                           ON CONFLICT(user_id,level_id) DO NOTHING"""),
                        {"owner": owner, "level": next_level, "revision": grade_id},
                    )
        await session.execute(
            text("""INSERT INTO app.audit_logs
               (id,actor_user_id,actor_role,action,entity_type,entity_id,reason,request_id)
               VALUES (:id,:actor,'instructor','exam.review','exam_attempt',
                       :attempt,:reason,:request)"""),
            {
                "id": uuid4(),
                "actor": user["id"],
                "attempt": attempt_id,
                "reason": body.reason,
                "request": request.state.request_id,
            },
        )
        updated = dict(attempt) | {"status": grade.status}
        result = await _result(session, updated)
    return ResultEnvelope(data=result, meta=meta(request))

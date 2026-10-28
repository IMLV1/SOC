import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.auth import service as auth
from app.auth.routes import json_only
from app.http_models import ErrorEnvelope, Meta
from app.learning.access import require_level
from app.learning.models import (
    LessonEnvelope,
    LessonView,
    LevelStatus,
    MePathData,
    MePathEnvelope,
    PathData,
    PathEnvelope,
    ProgressEnvelope,
    ProgressInput,
    ProgressView,
)
from app.learning.progress import apply_progress

router = APIRouter(
    prefix="/api/v1",
    tags=["Learning"],
    dependencies=[Depends(json_only)],
    include_in_schema=False,
    responses={status: {"model": ErrorEnvelope} for status in (401, 403, 404, 409, 422, 503)},
)


def _meta(request: Request) -> Meta:
    return Meta(request_id=request.state.request_id)


@router.get("/learning-path", response_model=PathEnvelope, operation_id="get_learning_path")
async def learning_path(request: Request) -> PathEnvelope:
    """Return level and lesson metadata without exposing lesson content."""
    async with auth.database(request).sessions() as session:
        rows = (
            (
                await session.execute(
                    text("""SELECT l.id,l.ordinal,l.title,
            coalesce(jsonb_agg(jsonb_build_object('id',s.id,'version',s.version,'title',s.title)
                ORDER BY s.id) FILTER (WHERE s.id IS NOT NULL),'[]'::jsonb) AS lessons
            FROM app.learning_levels l LEFT JOIN app.lessons s ON s.level_id=l.id
                AND s.published_at<=now() WHERE l.enabled
            GROUP BY l.id ORDER BY l.ordinal""")
                )
            )
            .mappings()
            .all()
        )
    return PathEnvelope(
        data=PathData.model_validate({"levels": [dict(row) for row in rows]}), meta=_meta(request)
    )


@router.get(
    "/me/learning-path",
    response_model=MePathEnvelope,
    operation_id="get_me_learning_path",
)
async def my_learning_path(request: Request) -> MePathEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        result = await session.execute(
            text(
                """SELECT lesson_id,lesson_version,CAST(completed_steps AS text) AS completed_steps,
                completed_at,version
                FROM app.user_lesson_progress WHERE user_id=:user ORDER BY updated_at DESC"""
            ),
            {"user": user["id"]},
        )
        items = [
            ProgressView(
                lesson_id=row["lesson_id"],
                lesson_version=row["lesson_version"],
                completed_steps=json.loads(row["completed_steps"]),
                completed_at=row["completed_at"],
                version=row["version"],
            )
            for row in result.mappings()
        ]
        statuses = (
            (
                await session.execute(
                    text("""SELECT l.id AS level_id,
                    (l.ordinal=1 OR EXISTS(SELECT 1 FROM app.level_unlocks u
                        WHERE u.user_id=:user AND u.level_id=l.id)) AS unlocked,
                    (EXISTS(SELECT 1 FROM app.lessons s WHERE s.level_id=l.id
                        AND s.published_at<=now()) AND NOT EXISTS(
                        SELECT 1 FROM app.lessons s WHERE s.level_id=l.id
                        AND s.published_at<=now() AND NOT EXISTS(
                            SELECT 1 FROM app.user_lesson_progress p
                            WHERE p.user_id=:user AND p.lesson_id=s.id
                            AND p.lesson_version=s.version AND p.completed_at IS NOT NULL)))
                        AS all_lessons_completed,
                    (SELECT count(*) FROM app.exam_cases c WHERE c.level_id=l.id
                        AND c.enabled) AS exam_case_count,
                    (SELECT count(DISTINCT a.case_id) FROM app.exam_attempts a
                        JOIN app.exam_cases c ON c.id=a.case_id AND c.enabled
                        JOIN app.grading_revisions g ON g.attempt_id=a.id
                        WHERE a.owner_user_id=:user AND a.level_id=l.id AND g.status='passed'
                        AND g.revision=(SELECT max(g2.revision)
                            FROM app.grading_revisions g2 WHERE g2.attempt_id=a.id))
                        AS passed_case_count
                    FROM app.learning_levels l WHERE l.enabled ORDER BY l.ordinal"""),
                    {"user": user["id"]},
                )
            )
            .mappings()
            .all()
        )
    next_action: Literal["continue_lesson", "review_lesson_exam_unavailable"] = (
        "review_lesson_exam_unavailable"
        if any(item.completed_at is not None for item in items)
        else "continue_lesson"
    )
    return MePathEnvelope(
        data=MePathData(
            lessons=items,
            next_action=next_action,
            level_statuses=[LevelStatus.model_validate(dict(row)) for row in statuses],
        ),
        meta=_meta(request),
    )


@router.get(
    "/lessons/{lesson_id}",
    response_model=LessonEnvelope,
    operation_id="get_lessons_lesson_id",
)
async def get_lesson(lesson_id: UUID, request: Request) -> LessonEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        # Authentication is required before reading lesson content; progress is
        # account-backed and must not be inferred from anonymous browser state.
        user = await auth.require_user(session, request)
        row = (
            (
                await session.execute(
                    text(
                        """SELECT CAST(content_json AS text) AS content_json FROM app.lessons
                    WHERE id=:id AND published_at<=now()"""
                    ),
                    {"id": lesson_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise auth.AuthError(404, "NOT_FOUND")
        content = json.loads(row["content_json"])
        await require_level(session, user["id"], UUID(content["level_id"]))
    return LessonEnvelope(data=LessonView.model_validate(content), meta=_meta(request))


async def _save_progress(
    lesson_id: UUID,
    request: Request,
    body: ProgressInput,
    *,
    step_id: str | None,
) -> ProgressEnvelope:
    await auth.rate_limit(request, "learning_progress")
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await auth.csrf_check(session, request)
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
            {"owner": str(user["id"])},
        )
        lesson = (
            (
                await session.execute(
                    text("""SELECT level_id,version,content_json FROM app.lessons
            WHERE id=:id AND published_at<=now()"""),
                    {"id": lesson_id},
                )
            )
            .mappings()
            .first()
        )
        if lesson is None:
            raise auth.AuthError(404, "NOT_FOUND")
        await require_level(session, user["id"], lesson["level_id"])
        # Earlier lessons in this level must be completed before moving on.
        incomplete = await session.scalar(
            text("""SELECT 1 FROM app.lessons l
            WHERE l.level_id=:level AND l.id<:lesson AND l.published_at<=now()
            AND NOT EXISTS(SELECT 1 FROM app.user_lesson_progress p
                WHERE p.user_id=:user AND p.lesson_id=l.id AND p.lesson_version=l.version
                AND p.completed_at IS NOT NULL) LIMIT 1"""),
            {"level": lesson["level_id"], "lesson": lesson_id, "user": user["id"]},
        )
        if incomplete:
            raise auth.AuthError(409, "PREVIOUS_LESSON_REQUIRED")
        step_ids = [step["id"] for step in lesson["content_json"]["steps"]]
        await session.execute(
            text(
                """INSERT INTO app.user_lesson_progress(user_id,lesson_id,lesson_version)
                VALUES (:user,:lesson,:lesson_version)
                ON CONFLICT(user_id,lesson_id) DO NOTHING"""
            ),
            {"user": user["id"], "lesson": lesson_id, "lesson_version": lesson["version"]},
        )
        query = text(
            """SELECT CAST(completed_steps AS text) AS completed_steps,
            completed_at,version,lesson_version
            FROM app.user_lesson_progress
            WHERE user_id=:user AND lesson_id=:lesson FOR UPDATE"""
        )
        params = {"user": user["id"], "lesson": lesson_id}
        row = (await session.execute(query, params)).mappings().one()
        # A lesson content version change invalidates an old step list rather
        # than silently applying stale completion state to the new lesson.
        if row["lesson_version"] != lesson["version"]:
            raise auth.AuthError(409, "LESSON_VERSION_CHANGED")
        steps, changed = apply_progress(
            json.loads(row["completed_steps"]),
            completed=row["completed_at"] is not None,
            current_version=row["version"],
            expected_version=body.expected_version,
            step_id=step_id,
            allowed_steps=step_ids,
        )
        is_complete = row["completed_at"] is not None or (
            step_id is None and len(steps) == len(step_ids)
        )
        if changed:
            # Progress and its optimistic version advance together inside this
            # transaction, so two tabs cannot overwrite each other's updates.
            await session.execute(
                text(
                    """UPDATE app.user_lesson_progress
                    SET completed_steps=CAST(:steps AS jsonb),
                    completed_at=CASE WHEN :complete THEN coalesce(completed_at,now())
                                      ELSE completed_at END,
                    version=version+1,updated_at=now()
                    WHERE user_id=:user AND lesson_id=:lesson"""
                ),
                {
                    "steps": json.dumps(steps),
                    "complete": is_complete,
                    **params,
                },
            )
            row = (await session.execute(query, params)).mappings().one()

        progress = ProgressView(
            lesson_id=lesson_id,
            lesson_version=row["lesson_version"],
            completed_steps=json.loads(row["completed_steps"]),
            completed_at=row["completed_at"],
            version=row["version"],
        )
        await auth.audit(session, "learning.progress", user["id"], request)
    return ProgressEnvelope(data=progress, meta=_meta(request))


@router.post(
    "/lessons/{lesson_id}/steps/{step_id}/complete",
    response_model=ProgressEnvelope,
    operation_id="complete_lesson_step",
)
async def complete_step(
    lesson_id: UUID,
    step_id: str,
    body: ProgressInput,
    request: Request,
) -> ProgressEnvelope:
    return await _save_progress(lesson_id, request, body, step_id=step_id)


@router.post(
    "/lessons/{lesson_id}/complete",
    response_model=ProgressEnvelope,
    operation_id="complete_lesson",
)
async def complete_lesson(
    lesson_id: UUID,
    body: ProgressInput,
    request: Request,
) -> ProgressEnvelope:
    return await _save_progress(lesson_id, request, body, step_id=None)

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.auth import service as auth
from app.auth.routes import json_only
from app.http_models import ErrorEnvelope, Meta
from app.learning.catalog import LESSON, LESSON_ID, LESSON_VERSION, LEVELS
from app.learning.models import (
    LessonEnvelope,
    LessonView,
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
    return PathEnvelope(data=PathData.model_validate({"levels": LEVELS}), meta=_meta(request))


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
    next_action: Literal["continue_lesson", "review_lesson_exam_unavailable"] = (
        "review_lesson_exam_unavailable"
        if any(item.completed_at is not None for item in items)
        else "continue_lesson"
    )
    return MePathEnvelope(
        data=MePathData(lessons=items, next_action=next_action), meta=_meta(request)
    )


@router.get(
    "/lessons/{lesson_id}",
    response_model=LessonEnvelope,
    operation_id="get_lessons_lesson_id",
)
async def get_lesson(lesson_id: UUID, request: Request) -> LessonEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        await auth.require_user(session, request)
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
    return LessonEnvelope(data=LessonView.model_validate(content), meta=_meta(request))


async def _save_progress(
    lesson_id: UUID,
    request: Request,
    body: ProgressInput,
    *,
    step_id: str | None,
) -> ProgressEnvelope:
    if lesson_id != LESSON_ID:
        raise auth.AuthError(404, "NOT_FOUND")
    step_ids = [step["id"] for step in LESSON["steps"]]

    await auth.rate_limit(request, "learning_progress")
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await auth.csrf_check(session, request)
        await session.execute(
            text(
                """INSERT INTO app.user_lesson_progress(user_id,lesson_id,lesson_version)
                VALUES (:user,:lesson,:lesson_version)
                ON CONFLICT(user_id,lesson_id) DO NOTHING"""
            ),
            {"user": user["id"], "lesson": lesson_id, "lesson_version": LESSON_VERSION},
        )
        query = text(
            """SELECT CAST(completed_steps AS text) AS completed_steps,
            completed_at,version,lesson_version
            FROM app.user_lesson_progress
            WHERE user_id=:user AND lesson_id=:lesson FOR UPDATE"""
        )
        params = {"user": user["id"], "lesson": lesson_id}
        row = (await session.execute(query, params)).mappings().one()
        if row["lesson_version"] != LESSON_VERSION:
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

"""Shared server-side level checks; never infer unlocks from browser progress."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth


async def require_level(session: AsyncSession, user_id: UUID, level_id: UUID) -> None:
    allowed = await session.scalar(
        text("""SELECT 1 FROM app.learning_levels l
        WHERE l.id=:level AND l.enabled AND (l.ordinal=1 OR EXISTS(
            SELECT 1 FROM app.level_unlocks u WHERE u.user_id=:user AND u.level_id=l.id))"""),
        {"level": level_id, "user": user_id},
    )
    if not allowed:
        raise auth.AuthError(404, "NOT_FOUND")


async def require_no_exam(session: AsyncSession, user_id: UUID) -> None:
    active = await session.scalar(
        text("""SELECT 1 FROM app.exam_attempts
        WHERE owner_user_id=:user AND status IN ('in_progress','submitted','needs_review')
        LIMIT 1"""),
        {"user": user_id},
    )
    if active:
        raise auth.AuthError(409, "EXAM_ATTEMPT_ACTIVE")

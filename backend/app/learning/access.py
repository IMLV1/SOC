"""Shared server-side level checks; never infer unlocks from browser progress."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth


async def materialize_level_unlock(
    session: AsyncSession, user_id: UUID, level_id: UUID
) -> bool:
    """Backfill an earned unlock from authoritative lesson and grading rows."""
    row = (
        await session.execute(
            text(
                """SELECT l.ordinal,
                    (SELECT count(*) FROM app.exam_cases c
                     WHERE c.level_id=previous.id AND c.enabled) AS case_count,
                    (SELECT count(DISTINCT a.id) FROM app.exam_attempts a
                     JOIN app.grading_revisions g ON g.attempt_id=a.id
                     WHERE a.owner_user_id=:user AND a.level_id=previous.id
                       AND a.status='passed'
                       AND g.status='passed'
                       AND g.revision=(SELECT max(g2.revision)
                         FROM app.grading_revisions g2 WHERE g2.attempt_id=a.id))
                     AS passed_count,
                    (SELECT g.id FROM app.exam_attempts a
                     JOIN app.grading_revisions g ON g.attempt_id=a.id
                     WHERE a.owner_user_id=:user AND a.level_id=previous.id
                       AND a.status='passed'
                       AND g.status='passed'
                       AND g.revision=(SELECT max(g2.revision)
                         FROM app.grading_revisions g2 WHERE g2.attempt_id=a.id)
                     ORDER BY g.created_at DESC LIMIT 1) AS earned_revision,
                    (previous.ordinal=1 OR EXISTS(
                      SELECT 1 FROM app.level_unlocks u
                      WHERE u.user_id=:user AND u.level_id=previous.id)) AS previous_unlocked,
                    (NOT EXISTS(SELECT 1 FROM app.lessons lesson
                      WHERE lesson.level_id=previous.id AND lesson.published_at<=now()
                        AND NOT EXISTS(SELECT 1 FROM app.user_lesson_progress p
                          WHERE p.user_id=:user AND p.lesson_id=lesson.id
                            AND p.lesson_version=lesson.version
                            AND p.completed_at IS NOT NULL))) AS lessons_completed
                   FROM app.learning_levels l
                   JOIN app.learning_levels previous ON previous.ordinal=l.ordinal-1
                   WHERE l.id=:level AND l.enabled AND previous.enabled"""
            ),
            {"user": user_id, "level": level_id},
        )
    ).mappings().first()
    if (
        row is None
        or row["case_count"] == 0
        or row["passed_count"] < row["case_count"]
        or not row["previous_unlocked"]
        or not row["lessons_completed"]
        or row["earned_revision"] is None
    ):
        return False

    await session.execute(
        text("""INSERT INTO app.level_unlocks(user_id,level_id,earned_from_revision_id)
            VALUES (:user,:level,:revision) ON CONFLICT(user_id,level_id) DO NOTHING"""),
        {"user": user_id, "level": level_id, "revision": row["earned_revision"]},
    )
    return True


async def require_level(session: AsyncSession, user_id: UUID, level_id: UUID) -> None:
    """Check a level and lazily materialize unlocks already earned before policy changes."""
    await materialize_level_unlock(session, user_id, level_id)
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

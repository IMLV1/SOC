"""Atomic daily logical AI request reservation shared by tutor and exams."""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthError


async def reserve_logical_request(session: AsyncSession, owner: UUID) -> None:
    """Consume one of the user's daily logical AI requests under locked ledgers."""
    quota = await session.scalar(
        text("SELECT daily_ai_requests FROM app.user_quotas WHERE user_id=:owner"),
        {"owner": owner},
    )
    if quota is None:
        raise AuthError(403, "FORBIDDEN")
    today = await session.scalar(text("SELECT (clock_timestamp() AT TIME ZONE 'UTC')::date"))
    for scope, user in (("system", None), (f"user:{owner}", owner)):
        await session.execute(
            text("""INSERT INTO app.quota_ledgers
            (id,scope_key,user_id,period_start) VALUES(:id,:scope,:user,:day)
            ON CONFLICT(scope_key,period_start) DO NOTHING"""),
            {"id": uuid4(), "scope": scope, "user": user, "day": today},
        )
        ledger = (
            (
                await session.execute(
                    text("""SELECT id,ai_request_count FROM app.quota_ledgers
                    WHERE scope_key=:scope AND period_start=:day FOR UPDATE"""),
                    {"scope": scope, "day": today},
                )
            )
            .mappings()
            .one()
        )
        if user is not None and ledger["ai_request_count"] >= quota:
            raise AuthError(429, "AI_QUOTA_EXCEEDED")
        await session.execute(
            text("""UPDATE app.quota_ledgers
            SET ai_request_count=ai_request_count+1,version=version+1 WHERE id=:id"""),
            {"id": ledger["id"]},
        )

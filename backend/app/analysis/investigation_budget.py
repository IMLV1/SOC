"""Tutor and investigation serialize the same USD ceiling; unknown holds never expire."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def committed_usd(session: AsyncSession) -> Decimal:
    return Decimal(
        await session.scalar(
            text("""SELECT coalesce(sum(cost),0) FROM (
        SELECT reserved_usd AS cost FROM app.tutor_questions
        WHERE usage_status IN ('reserved','unknown') OR (usage_status='reconciled'
          AND budget_day=(clock_timestamp() AT TIME ZONE 'UTC')::date)
        UNION ALL SELECT reserved_usd FROM app.investigation_calls
        WHERE usage_status='unknown' OR (usage_status='reconciled'
          AND budget_day=(clock_timestamp() AT TIME ZONE 'UTC')::date)
        ) costs""")
        )
    )


async def drifted(session: AsyncSession, release_hash: str) -> bool:
    return bool(
        await session.scalar(
            text("""SELECT EXISTS(
        SELECT 1 FROM app.investigation_calls WHERE release_hash=:release
          AND error_code='DIFY_WORKFLOW_VERSION_MISMATCH')"""),
            {"release": release_hash},
        )
    )


async def reserve_usd(session: AsyncSession, analysis_id: UUID, release: dict[str, Any]) -> bool:
    await session.execute(text("SELECT pg_advisory_xact_lock(73102007)"))
    cap = await session.scalar(text("SELECT daily_usd FROM app.tutor_policy WHERE id=1"))
    if (
        cap is None
        or await drifted(session, release["release_hash"])
        or await committed_usd(session) + Decimal(release["call_bound_usd"]) > cap
    ):
        return False
    return (
        await session.scalar(
            text("""INSERT INTO app.investigation_calls
        (analysis_id,release_hash,reserved_usd) VALUES(:id,:release,:cost)
        ON CONFLICT(analysis_id) DO NOTHING RETURNING analysis_id"""),
            {
                "id": analysis_id,
                "release": release["release_hash"],
                "cost": Decimal(release["call_bound_usd"]),
            },
        )
    ) is not None


async def settle_usd(
    session: AsyncSession, analysis_id: UUID, tokens: int | None, error: str | None
) -> None:
    await session.execute(text("SELECT pg_advisory_xact_lock(73102007)"))
    # A version mismatch is never reconciled from an unapproved execution.
    known = tokens is not None and error != "DIFY_WORKFLOW_VERSION_MISMATCH"
    await session.execute(
        text("""UPDATE app.investigation_calls SET
        usage_status=:status,reported_tokens=:tokens,error_code=:error
        WHERE analysis_id=:id"""),
        {
            "id": analysis_id,
            "status": "reconciled" if known else "unknown",
            "tokens": tokens,
            "error": error,
        },
    )

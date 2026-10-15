"""Serialize free-tier dispatch admission; unknown calls retain their full hold."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def reserve_call(
    session: AsyncSession,
    analysis_id: UUID,
    model: str,
    token_bound: int,
    experiment: bool = False,
) -> bool:
    column = "experiment_arm_id" if experiment else "analysis_id"
    policy = (
        (await session.execute(text("SELECT * FROM app.provider_policy WHERE id=1 FOR UPDATE")))
        .mappings()
        .one()
    )
    existing = await session.scalar(
        text(f"SELECT 1 FROM app.provider_calls WHERE {column}=:id"), {"id": analysis_id}
    )
    if existing:
        # A crash after admission may have sent the request. Never replay it.
        return False
    totals = (
        (
            await session.execute(
                text("""SELECT
        count(*) FILTER(WHERE dispatched_at >=
          date_trunc('day',clock_timestamp() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC') AS requests,
        coalesce(sum(CASE WHEN status='unknown'
          THEN greatest(reserved_tokens,coalesce(actual_tokens,0))
          WHEN status='consumed' AND dispatched_at >=
            date_trunc('day',clock_timestamp() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
          THEN actual_tokens ELSE 0 END),0) AS tokens,
        count(*) FILTER(WHERE dispatched_at>clock_timestamp()-interval '60 seconds') AS minute
        FROM app.provider_calls""")
            )
        )
        .mappings()
        .one()
    )
    cooling = await session.scalar(
        text("SELECT cooldown_until>clock_timestamp() FROM app.provider_policy WHERE id=1")
    )
    if (
        cooling
        or totals["requests"] >= policy["daily_requests"]
        or totals["tokens"] + token_bound > policy["daily_tokens"]
        or totals["minute"] >= policy["rpm"]
    ):
        return False
    await session.execute(
        text(f"""INSERT INTO app.provider_calls
        ({column},component,policy_version,model_id,reserved_tokens,status)
        VALUES(:id,'generation',:policy,:model,:tokens,'unknown')"""),
        {"id": analysis_id, "policy": policy["version"], "model": model, "tokens": token_bound},
    )
    return True


async def settle_call(
    session: AsyncSession,
    analysis_id: UUID,
    tokens: int,
    rejected: bool = False,
    cooldown: int = 0,
    experiment: bool = False,
) -> None:
    column = "experiment_arm_id" if experiment else "analysis_id"
    await session.execute(text("SELECT id FROM app.provider_policy WHERE id=1 FOR UPDATE"))
    await session.execute(
        text(f"""UPDATE app.provider_calls SET status=:status,
        actual_tokens=:tokens WHERE {column}=:id AND status='unknown'"""),
        {
            "id": analysis_id,
            "tokens": tokens if tokens else None,
            "status": "consumed" if tokens else "released" if rejected else "unknown",
        },
    )
    if cooldown:
        await session.execute(
            text("""UPDATE app.provider_policy SET cooldown_until=
            greatest(coalesce(cooldown_until,clock_timestamp()),
                clock_timestamp()+make_interval(secs=>:seconds)) WHERE id=1"""),
            {"seconds": cooldown},
        )

"""Domain transactions lock the run before the job; claims never wait on runs."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class LeaseLost(RuntimeError):
    pass


async def lock_domain(session: AsyncSession, job: dict[str, Any]) -> bool:
    # Lock the domain row first, then verify the job lease; all run workers use
    # this order so stale jobs cannot hold a job row while waiting on a run.
    if not await session.scalar(
        text("SELECT id FROM app.runs WHERE id=:run FOR UPDATE"), {"run": job["run_id"]}
    ):
        return False
    return bool(
        await session.scalar(
            text("""SELECT 1 FROM app.jobs WHERE id=:id AND run_id=:run
        AND status='running' AND lease_token=:token
        AND lease_expires_at>clock_timestamp() FOR UPDATE"""),
            {"id": job["id"], "run": job["run_id"], "token": job["lease_token"]},
        )
    )


async def require_lease(session: AsyncSession, job: dict[str, Any]) -> None:
    # Check again after domain work, including time spent waiting on locks; a
    # result is not committed if this worker's token expired or was replaced.
    if not await session.scalar(
        text("""SELECT 1 FROM app.jobs WHERE id=:id AND status='running'
        AND lease_token=:token AND lease_expires_at>clock_timestamp()"""),
        {"id": job["id"], "token": job["lease_token"]},
    ):
        raise LeaseLost("Worker lease lost")

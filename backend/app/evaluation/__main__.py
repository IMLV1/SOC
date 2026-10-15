"""Ground-truth isolated evaluator process."""

import argparse
import asyncio
import json
import signal
from uuid import uuid4

from sqlalchemy import text

from app.db.config import database_url
from app.db.health import check_database
from app.db.session import Database
from app.evaluation.worker import finalize
from app.worker.fencing import lock_domain, require_lease


async def process_one(database: Database, worker_id: str) -> bool:
    async with database.sessions() as session, session.begin():
        row = (
            (
                await session.execute(
                    text("""SELECT id FROM app.jobs WHERE type='finalize_run'
            AND attempts<3 AND ((status='queued' AND available_at<=clock_timestamp()) OR
            (status='running' AND lease_expires_at<=clock_timestamp()))
            ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT 1""")
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return False
        token = uuid4()
        job = (
            (
                await session.execute(
                    text("""UPDATE app.jobs SET status='running',attempts=attempts+1,
            locked_by=:worker,lease_token=:token,
            lease_expires_at=clock_timestamp()+interval '60 seconds'
                    WHERE id=:id RETURNING id,run_id,type,payload,attempts,lease_token"""),
                    {"worker": worker_id, "token": token, "id": row["id"]},
                )
            )
            .mappings()
            .one()
        )
        claimed = dict(job)

    async with database.sessions() as session, session.begin():
        # Domain lock precedes job-row lock to preserve run -> job lock ordering.
        if not await lock_domain(session, claimed):
            return True
        await finalize(session, claimed["run_id"])
        await require_lease(session, claimed)
        await session.execute(
            text("""UPDATE app.jobs SET status='succeeded',locked_by=NULL,lease_token=NULL,
            lease_expires_at=NULL,finished_at=clock_timestamp()
            WHERE id=:id AND lease_token=:token"""),
            {"id": claimed["id"], "token": claimed["lease_token"]},
        )
    return True


async def run(check: bool) -> int:
    database = Database(database_url("evaluator_runtime"))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    try:
        ready = await check_database(database, "evaluator_runtime")
        print(json.dumps({"component": "evaluator", "database_ready": ready}), flush=True)
        if check or not ready:
            return 0 if ready else 2
        while not stop.is_set():
            if await process_one(database, f"evaluator-{uuid4()}"):
                continue
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
            except TimeoutError:
                pass
        return 0
    finally:
        await database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SOC isolated evaluation worker")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.check))
    except Exception:
        print(json.dumps({"component": "evaluator", "database_ready": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

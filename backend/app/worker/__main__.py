import argparse
import asyncio
import json
import signal
from uuid import uuid4

from app.db.config import database_url
from app.db.health import check_database
from app.db.session import Database
from app.worker.jobs import heartbeat, process_one


async def run(check: bool) -> int:
    database = Database(database_url("worker_runtime"))
    worker_id = f"worker-{uuid4()}"
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    try:
        while True:
            ready = await check_database(database, "worker_runtime")
            print(
                json.dumps({"component": "worker", "database_ready": ready, "queue_ready": ready}),
                flush=True,
            )
            if check or not ready:
                return 0 if ready else 2
            await heartbeat(database, worker_id)
            if await process_one(database, worker_id):
                continue
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
                return 0
            except TimeoutError:
                continue
    finally:
        await database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SOC durable job worker")
    parser.add_argument(
        "--check", action="store_true", help="Check entrypoint without claiming jobs"
    )
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.check))
    except Exception:
        print(json.dumps({"component": "worker", "database_ready": False, "queue_ready": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

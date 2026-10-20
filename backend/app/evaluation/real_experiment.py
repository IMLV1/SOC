"""Dify experiment dispatch is unavailable until its frozen-result contract is integrated."""

import argparse
import asyncio
from uuid import UUID

from app.db.config import database_url
from app.db.session import Database


async def execute_arm(_database: Database, _arm: UUID) -> None:
    """Fail closed: the legacy implementation called Gemini directly."""
    raise RuntimeError("DIFY_EXPERIMENT_ADAPTER_UNAVAILABLE")


async def execute(arm: UUID) -> None:
    database = Database(database_url("worker_runtime"))
    try:
        await execute_arm(database, arm)
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", type=UUID, required=True)
    try:
        asyncio.run(execute(parser.parse_args().arm))
    except Exception:
        raise SystemExit("Experiment unavailable until Dify integration is ready") from None


if __name__ == "__main__":
    main()

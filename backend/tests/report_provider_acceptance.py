"""Print safe metadata only for the latest explicit synthetic C acceptance batch."""

import asyncio
import hashlib
import json

from sqlalchemy import text

from app.db.config import database_url
from app.db.session import Database


async def main() -> None:
    db = Database(database_url("migration_owner"))
    try:
        async with db.sessions() as session:
            row = (
                (
                    await session.execute(
                        text("""SELECT a.id,a.status,a.error_code,
                b.dataset_hash,a.config_snapshot,a.metrics_json,
                a.outputs_json->'triage'->'usage' AS usage,a.outputs_json,
                c.policy_version,c.reserved_tokens,c.actual_tokens,c.status AS usage_status,
                c.dispatched_at FROM app.experiment_arms a
                JOIN app.experiment_batches b ON b.id=a.batch_id
                JOIN app.provider_calls c ON c.experiment_arm_id=a.id
                ORDER BY c.dispatched_at DESC LIMIT 1""")
                    )
                )
                .mappings()
                .one()
            )
            baseline = await session.scalar(
                text("""SELECT b.metrics_json
                FROM app.experiment_arms c JOIN app.experiment_arms b
                  ON b.batch_id=c.batch_id AND b.mode='B' WHERE c.id=:id"""),
                {"id": row["id"]},
            )
            assert baseline == row["metrics_json"]
            payload = dict(row)
            payload["response_sha256"] = hashlib.sha256(
                json.dumps(payload.pop("outputs_json"), sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            print(
                json.dumps(
                    payload | {"detector_metrics_match_B": True}, default=str, sort_keys=True
                )
            )
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())

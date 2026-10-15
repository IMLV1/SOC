"""Explicit offline A/B fixture setup for a bounded real C acceptance call.

Run only after test_real_experiment in the isolated test database. No network here.
"""

import asyncio
import json
import os
from uuid import uuid4

from sqlalchemy import text

from app.db.config import database_url
from app.db.session import Database
from app.evaluation.experiments import compare


async def main() -> None:
    if not os.environ.get("DB_NAME", "").startswith("soc_test_"):
        raise ValueError("Isolated test database required")
    db = Database(database_url("migration_owner"))
    try:
        async with db.sessions() as session, session.begin():
            base = (
                (
                    await session.execute(
                        text("""SELECT b.*,e.release_cutoff
                FROM app.experiment_batches b JOIN app.evaluations e
                ON e.run_id=b.dataset_run_id ORDER BY b.created_at DESC LIMIT 1""")
                    )
                )
                .mappings()
                .one()
            )
            run = base["dataset_run_id"]
            events = (
                (
                    await session.execute(
                        text("""SELECT e.*,r.created_at,
                extract(epoch FROM(e.event_time-r.created_at))*1000 AS offset_ms
                FROM app.events e JOIN app.runs r ON r.id=e.run_id
                WHERE e.run_id=:run AND e.release_seq<=:cutoff ORDER BY e.release_seq"""),
                        {"run": run, "cutoff": base["release_cutoff"]},
                    )
                )
                .mappings()
                .all()
            )
            truths = (
                (
                    await session.execute(
                        text("""SELECT scenario_instance_id,incident_key,
                threat_label,expected_evidence_keys FROM private.evaluation_truth
                WHERE run_id=:run"""),
                        {"run": run},
                    )
                )
                .mappings()
                .all()
            )
            versions = (
                (
                    await session.execute(
                        text("""SELECT rule_version,baseline_version,
                correlation_version FROM app.run_versions WHERE run_id=:run"""),
                        {"run": run},
                    )
                )
                .mappings()
                .one()
            )
            outputs = compare([dict(e) for e in events], [dict(t) for t in truths], dict(versions))
            batch, arm = uuid4(), uuid4()
            await session.execute(
                text("""INSERT INTO app.experiment_batches
                (id,dataset_run_id,requested_by,dataset_hash,config_versions,truncated,status)
                VALUES(:id,:run,:user,:hash,CAST(:config AS jsonb),:truncated,'completed')"""),
                {
                    "id": batch,
                    "run": run,
                    "user": base["requested_by"],
                    "hash": base["dataset_hash"],
                    "config": json.dumps(dict(versions)),
                    "truncated": base["truncated"],
                },
            )
            for mode, data in outputs.items():
                await session.execute(
                    text("""INSERT INTO app.experiment_arms
                    (id,batch_id,mode,status,config_snapshot,outputs_json,metrics_json,error_code)
                    VALUES(:id,:batch,:mode,:status,CAST(:config AS jsonb),CAST(:outputs AS jsonb),
                        CAST(:metrics AS jsonb),:error)"""),
                    {
                        "id": arm if mode == "C" else uuid4(),
                        "batch": batch,
                        "mode": mode,
                        "status": data["status"],
                        "config": json.dumps(dict(versions)),
                        "outputs": json.dumps(data["findings"]),
                        "metrics": json.dumps(data["metrics"]),
                        "error": data.get("error_code"),
                    },
                )
            print(arm)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())

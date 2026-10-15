import asyncio
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from test_investigation_pipeline import prepare, release_all

from app.analysis.models import ProviderOutput, ProviderUsage
from app.analysis.provider import MockProvider
from app.db.session import Database
from app.evaluation.__main__ import process_one as process_evaluation
from app.evaluation.real_experiment import execute_arm
from app.runs.service import finish_run, start_run


@pytest.mark.integration
def test_c_uses_frozen_input_separate_outputs_budget_and_no_replay(migrated, monkeypatch):
    async def execute():
        user, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        evaluator = Database(migrated("evaluator_runtime"))
        owner = Database(migrated("migration_owner"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            run_id = UUID(run["id"])
            await release_all(api, worker, run_id)
            async with api.sessions() as session, session.begin():
                version = await session.scalar(
                    text("SELECT version FROM app.runs WHERE id=:id"), {"id": run_id}
                )
                await finish_run(session, run_id, user, version)
            assert await process_evaluation(evaluator, "experiment-test")
            instructor, batch, arm = uuid4(), uuid4(), uuid4()
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("""INSERT INTO app.users
                    (id,normalized_email,display_name,password_hash,role,status)
                    VALUES(:id,:email,'Instructor','$argon2id$fixture','instructor','active')"""),
                    {"id": instructor, "email": f"{instructor}@example.test"},
                )
                await session.execute(
                    text(
                        "INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests) "
                        "VALUES(:id,10,20)"
                    ),
                    {"id": instructor},
                )
                await session.execute(
                    text(
                        "INSERT INTO app.instructor_assignments"
                        "(instructor_user_id,analyst_user_id) "
                        "VALUES(:id,:user)"
                    ),
                    {"id": instructor, "user": user},
                )
                await session.execute(
                    text("""INSERT INTO app.experiment_batches
                    (id,dataset_run_id,requested_by,dataset_hash,config_versions,truncated,status)
                    SELECT :id,run_id,:user,dataset_hash,'{}',truncated,'completed'
                    FROM app.evaluations WHERE run_id=:run"""),
                    {"id": batch, "user": instructor, "run": run_id},
                )
                for mode in ["B", "C"]:
                    await session.execute(
                        text("""INSERT INTO app.experiment_arms
                        (id,batch_id,mode,status,config_snapshot,outputs_json,metrics_json)
                        VALUES(:id,:batch,:mode,:status,'{}','[]',CAST(:metrics AS jsonb))"""),
                        {
                            "id": arm if mode == "C" else uuid4(),
                            "batch": batch,
                            "mode": mode,
                            "status": "unavailable" if mode == "C" else "completed",
                            "metrics": json.dumps({"precision": None, "recall": None}),
                        },
                    )
            for key, value in {
                "SOC_AI_PROVIDER": "gemini_free",
                "GEMINI_PROJECT_TIER_CONFIRMED": "free_no_billing",
                "GEMINI_SYNTHETIC_DATA_ONLY": "true",
                "GEMINI_API_KEY_FILE": "not-read-in-test",
            }.items():
                monkeypatch.setenv(key, value)
            calls = []

            async def fake(self, data):
                calls.append(data)
                result = await MockProvider().analyze(data)
                return ProviderOutput(
                    result=result.result,
                    usage=ProviderUsage(
                        mode="real",
                        input_tokens=50,
                        output_tokens=20,
                        total_tokens=70,
                        pricing_tier="free",
                    ),
                )

            monkeypatch.setattr("app.evaluation.real_experiment.GeminiProvider.analyze", fake)
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("UPDATE app.users SET status='disabled' WHERE id=:id"), {"id": instructor}
                )
            with pytest.raises(ValueError, match="authorized"):
                await execute_arm(worker, arm)
            assert calls == []
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("UPDATE app.users SET status='active' WHERE id=:id"), {"id": instructor}
                )
            await execute_arm(worker, arm)
            with pytest.raises(ValueError):
                await execute_arm(worker, arm)
            assert len(calls) == 1
            async with owner.sessions() as session:
                row = (
                    (
                        await session.execute(
                            text("SELECT * FROM app.experiment_arms WHERE id=:id"), {"id": arm}
                        )
                    )
                    .mappings()
                    .one()
                )
                assert row["status"] == "completed"
                assert row["outputs_json"]["triage"]["usage"]["mode"] == "real"
                assert row["metrics_json"] == {"precision": None, "recall": None}
                assert (
                    await session.scalar(
                        text("""SELECT consumed_tokens
                    FROM app.quota_ledgers WHERE scope_key=:scope"""),
                        {"scope": f"user:{instructor}"},
                    )
                    == 70
                )
                assert (
                    await session.scalar(
                        text(
                            "SELECT actual_tokens FROM app.provider_calls "
                            "WHERE experiment_arm_id=:id"
                        ),
                        {"id": arm},
                    )
                    == 70
                )
        finally:
            for db in (api, worker, evaluator, owner):
                await db.close()

    asyncio.run(execute())

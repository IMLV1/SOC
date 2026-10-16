import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from test_investigation_pipeline import prepare

from app.analysis.budget import reserve_call, settle_call
from app.analysis.reconcile import reconcile
from app.db.session import Database
from app.runs.service import start_run


@pytest.mark.integration
def test_concurrent_global_token_hold_replay_and_unknown_across_days(migrated):
    async def execute():
        user, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        owner = Database(migrated("migration_owner"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            ids = [uuid4(), uuid4()]
            async with owner.sessions() as session, session.begin():
                for key in ids:
                    await session.execute(
                        text("""INSERT INTO app.analyses
                        (id,run_id,correlation_key,evidence_hash,attempt_group,
                         mode,model_id,prompt_version,status)
                        VALUES(:id,:run,'budget','hash',:id,'real','model','v1','queued')"""),
                        {"id": key, "run": UUID(run["id"])},
                    )

            async def reserve(key):
                async with worker.sessions() as session, session.begin():
                    return await reserve_call(session, key, "model", 150000)

            results = await asyncio.gather(*(reserve(key) for key in ids))
            assert sorted(results) == [False, True]
            admitted = ids[results.index(True)]
            denied = ids[results.index(False)]
            assert not await reserve(admitted)
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("UPDATE app.provider_calls SET dispatched_at=now()-interval '2 days'")
                )
            assert not await reserve(denied)
            async with worker.sessions() as session, session.begin():
                await settle_call(session, admitted, 100)
            assert await reserve(denied)
            with pytest.raises(ValueError, match="Active"):
                await reconcile(owner, denied, 25, "active resource rejected")
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("UPDATE app.analyses SET status='timed_out' WHERE id=:id"), {"id": denied}
                )
            await reconcile(owner, denied, 25, "confirmed test usage report")
            with pytest.raises(ValueError, match="No unknown"):
                await reconcile(owner, denied, 25, "duplicate reconciliation")
        finally:
            await api.close()
            await worker.close()
            await owner.close()

    asyncio.run(execute())


@pytest.mark.parametrize("tokens,reason", [(-1, "report"), (0, ""), (0, " "), (0, "x" * 501)])
def test_reconciliation_rejects_unconfirmed_or_invalid_usage(tokens, reason):
    with pytest.raises(ValueError, match="Confirmed"):
        asyncio.run(reconcile(None, uuid4(), tokens, reason))


@pytest.mark.integration
@pytest.mark.parametrize("limit_column", ["daily_requests", "rpm"])
def test_request_and_rolling_minute_caps_are_independent(migrated, limit_column):
    async def execute():
        user, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        owner = Database(migrated("migration_owner"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            ids = [uuid4(), uuid4()]
            async with owner.sessions() as session, session.begin():
                await session.execute(text(f"UPDATE app.provider_policy SET {limit_column}=1"))
                for key in ids:
                    await session.execute(
                        text("""INSERT INTO app.analyses
                        (id,run_id,correlation_key,evidence_hash,attempt_group,
                        mode,model_id,prompt_version,status)
                        VALUES(:id,:run,'cap','hash',:id,'real','model','v1','queued')"""),
                        {"id": key, "run": UUID(run["id"])},
                    )
            async with worker.sessions() as session, session.begin():
                assert await reserve_call(session, ids[0], "model", 1)
                await settle_call(session, ids[0], 0, rejected=True)
                assert not await reserve_call(session, ids[1], "model", 1)
        finally:
            for db in (api, worker, owner):
                await db.close()

    asyncio.run(execute())


@pytest.mark.integration
def test_429_releases_token_hold_but_cools_down_other_workers(migrated):
    async def execute():
        db = Database(migrated("worker_runtime"))
        try:
            async with db.sessions() as session, session.begin():
                await settle_call(session, uuid4(), 0, rejected=True, cooldown=60)
            async with db.sessions() as session, session.begin():
                assert not await reserve_call(session, uuid4(), "model", 1)
        finally:
            await db.close()

    asyncio.run(execute())


@pytest.mark.integration
def test_owner_operation_reconciliation_requires_confirmed_usage_and_audits(migrated):
    from app.analysis.reconcile import reconcile_operation

    async def run():
        worker = Database(migrated("worker_runtime"))
        owner = Database(migrated("migration_owner"))
        try:
            async with worker.sessions() as s, s.begin():
                assert await reserve_call(
                    s,
                    uuid4(),
                    "embedding-model",
                    100,
                    component="document_embedding",
                    operation_key="ci:ingest",
                )
            with pytest.raises(PermissionError):
                await reconcile_operation(worker, "ci:ingest", 15, "confirmed test report")
            with pytest.raises(ValueError):
                await reconcile_operation(owner, "ci:ingest", 15, "")
            await reconcile_operation(owner, "ci:ingest", 15, "confirmed synthetic test report")
            async with owner.sessions() as s:
                row = (
                    await s.execute(
                        text(
                            "SELECT status,actual_tokens,reconciliation_reason FROM "
                            "app.provider_calls WHERE operation_key='ci:ingest'"
                        )
                    )
                ).one()
                assert row.status == "consumed" and row.actual_tokens == 15
                assert (
                    await s.scalar(
                        text(
                            "SELECT count(*) FROM app.audit_logs WHERE "
                            "action='provider.operation_reconcile'"
                        )
                    )
                    == 1
                )
            with pytest.raises(ValueError):
                await reconcile_operation(owner, "ci:ingest", 15, "duplicate report")
        finally:
            await worker.close()
            await owner.close()

    asyncio.run(run())

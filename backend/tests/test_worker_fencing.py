import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.util import await_only
from test_runs import prepare

from app.analysis.service import enqueue_analysis
from app.analysis.worker import analyze_job
from app.db.session import Database
from app.detection.worker import detect_run
from app.runs.service import change_state, start_run
from app.worker.fencing import LeaseLost, require_lease
from app.worker.jobs import claim, extend_lease, release_events, settle

pytestmark = pytest.mark.integration


def test_release_wins_race_then_pause_blocks_every_later_release(migrated):
    async def execute():
        user, selection = await prepare(migrated)
        api, worker = Database(migrated("api_runtime")), Database(migrated("worker_runtime"))
        acquired, gate = asyncio.Event(), asyncio.Event()

        def hold_run(conn, cursor, statement, parameters, context, many):
            if statement.startswith("SELECT id FROM app.runs") and not acquired.is_set():
                acquired.set()
                await_only(gate.wait())

        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            run_id = UUID(run["id"])
            job = await claim(worker, "release-first")
            event.listen(worker.engine.sync_engine, "after_cursor_execute", hold_run)
            release = asyncio.create_task(release_events(worker, job))
            await asyncio.wait_for(acquired.wait(), 5)

            async def pause():
                async with api.sessions() as session, session.begin():
                    return await change_state(session, run_id, user, "pause", 1)

            pausing = asyncio.create_task(pause())
            async with api.sessions() as observer:
                for _ in range(100):
                    await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                    blocked = await observer.scalar(
                        text("""SELECT count(*) FROM pg_stat_activity
                        WHERE usename='api_runtime' AND wait_event_type='Lock'
                        AND query LIKE '%app.runs%FOR UPDATE%'""")
                    )
                    if blocked:
                        break
                    await asyncio.sleep(0.01)
                assert blocked and not pausing.done()
            gate.set()
            await asyncio.wait_for(release, 5)
            assert (await asyncio.wait_for(pausing, 5))["status"] == "paused"
            async with worker.sessions() as session:
                count = await session.scalar(text("SELECT count(*) FROM app.events"))
            assert count >= 1
            await release_events(worker, job)
            async with worker.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.events")) == count
        finally:
            gate.set()
            await api.close()
            await worker.close()

    asyncio.run(execute())


def test_lease_expires_inside_domain_transaction_rolls_back_writes(migrated):
    async def execute():
        user, selection = await prepare(migrated)
        api, worker = Database(migrated("api_runtime")), Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            job = await claim(worker, "expiry")
            with pytest.raises(LeaseLost):
                async with worker.sessions() as session, session.begin():
                    await session.execute(
                        text("SELECT id FROM app.runs WHERE id=:run FOR UPDATE"),
                        {"run": job["run_id"]},
                    )
                    await session.execute(
                        text("UPDATE app.runs SET elapsed_ms=123 WHERE id=:run"),
                        {"run": job["run_id"]},
                    )
                    await session.execute(
                        text(
                            "UPDATE app.jobs SET lease_expires_at="
                            "clock_timestamp()-interval '1 second' WHERE id=:id"
                        ),
                        {"id": job["id"]},
                    )
                    await require_lease(session, job)
            async with worker.sessions() as session:
                assert (
                    await session.scalar(
                        text("SELECT elapsed_ms FROM app.runs WHERE id=:run"),
                        {"run": job["run_id"]},
                    )
                    == 0
                )
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())


def test_pause_and_release_really_contend_and_pause_prevents_release(migrated):
    async def execute():
        user, selection = await prepare(migrated)
        api, worker = Database(migrated("api_runtime")), Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            run_id = UUID(run["id"])
            job = await claim(worker, "race-worker")
            assert job
            async with api.sessions() as session, session.begin():
                await session.execute(
                    text("SELECT id FROM app.runs WHERE id=:id FOR UPDATE"), {"id": run_id}
                )
                task = asyncio.create_task(release_events(worker, job))
                # Verify actual PostgreSQL lock contention, rather than timing a sleep.
                async with worker.sessions() as observer:
                    for _ in range(100):
                        await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                        blocked = await observer.scalar(
                            text("""SELECT count(*) FROM pg_stat_activity
                            WHERE usename='worker_runtime' AND wait_event_type='Lock'
                            AND query LIKE '%app.runs%FOR UPDATE%'""")
                        )
                        if blocked:
                            break
                        await asyncio.sleep(0.01)
                    assert blocked and not task.done()
                await change_state(session, run_id, user, "pause", 1)
            await asyncio.wait_for(task, 5)
            async with worker.sessions() as session:
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.events WHERE run_id=:run"), {"run": run_id}
                    )
                    == 0
                )
            assert await settle(worker, job)
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())


@pytest.mark.parametrize("replacement", [False, True])
def test_expired_and_replaced_workers_cannot_write_or_settle(migrated, replacement):
    async def execute():
        user, selection = await prepare(migrated)
        api, worker = Database(migrated("api_runtime")), Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            job = await claim(worker, "old")
            assert job
            async with worker.sessions() as session, session.begin():
                await session.execute(
                    text(
                        "UPDATE app.jobs SET lease_expires_at="
                        "clock_timestamp()-interval '1 second' "
                        "WHERE id=:id"
                    ),
                    {"id": job["id"]},
                )
            assert not await extend_lease(worker, job["id"], job["lease_token"])
            newer = await claim(worker, "new") if replacement else None
            if newer:
                assert newer["id"] == job["id"] and newer["lease_token"] != job["lease_token"]
            await release_events(worker, job)
            await detect_run(worker, job["run_id"], job=job)
            assert not await settle(worker, job)
            async with worker.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.events")) == 0
                assert await session.scalar(text("SELECT count(*) FROM app.detections")) == 0
            if newer:
                await release_events(worker, newer)
                assert await settle(worker, newer)
                async with worker.sessions() as session:
                    assert await session.scalar(text("SELECT count(*) FROM app.events")) == 1
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())


def test_analysis_losing_lease_during_provider_call_cannot_publish(migrated):
    async def execute():
        user, selection = await prepare(migrated)
        api, worker = Database(migrated("api_runtime")), Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            run_id = UUID(run["id"])
            release = await claim(worker, "release")
            await release_events(worker, release)
            await settle(worker, release)
            detection = await claim(worker, "detect")
            await detect_run(worker, run_id, job=detection)
            await settle(worker, detection)
            async with api.sessions() as session, session.begin():
                event = await session.scalar(
                    text("SELECT id FROM app.events WHERE run_id=:run"), {"run": run_id}
                )
                analysis = await enqueue_analysis(
                    session, run_id, user, "fencing", "snapshot", [event]
                )
            job = await claim(worker, "analysis-old")

            class ExpiringProvider:
                async def analyze(self, data):
                    async with worker.sessions() as session, session.begin():
                        await session.execute(
                            text(
                                "UPDATE app.jobs SET lease_expires_at="
                                "clock_timestamp()-interval '1 second' "
                                "WHERE id=:id"
                            ),
                            {"id": job["id"]},
                        )
                    return {}

            await analyze_job(worker, job, ExpiringProvider())
            assert not await settle(worker, job)
            async with worker.sessions() as session:
                row = (
                    await session.execute(
                        text("SELECT status,result_json FROM app.analyses WHERE id=:id"),
                        {"id": analysis},
                    )
                ).one()
                assert row.status == "running" and row.result_json is None
                assert (
                    await session.scalar(
                        text(
                            "SELECT count(*) FROM app.quota_reservations "
                            "WHERE analysis_id=:id AND status='reserved'"
                        ),
                        {"id": analysis},
                    )
                    > 0
                )
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())

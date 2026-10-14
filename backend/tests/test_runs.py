import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import service as auth
from app.auth.service import AuthError
from app.db.session import Database
from app.main import app
from app.runs.service import change_state, finish_run, start_run
from app.scenarios.models import TrainingSelection
from app.scenarios.seed import FIXTURES, load_seed, seed
from app.worker.jobs import claim, process_one, release_events, settle


async def prepare(pg):
    owner = Database(pg("migration_owner"))
    await seed(owner)
    user_id = uuid4()
    async with owner.sessions() as session, session.begin():
        await session.execute(
            text("""INSERT INTO app.users
            (id,normalized_email,display_name,password_hash,role,status)
            VALUES (:id,:email,'Runner','$argon2id$fixture','analyst','active')"""),
            {"id": user_id, "email": f"{user_id}@example.test"},
        )
        await session.execute(
            text("""INSERT INTO app.user_quotas
            (user_id,daily_runs,daily_ai_requests) VALUES (:id,10,20)"""),
            {"id": user_id},
        )
    await owner.close()
    scenario = next(item for item, _, _ in load_seed(FIXTURES) if item.stable_key == "S02")
    return user_id, TrainingSelection(scenario_ids=[scenario.id], seed=42)


@pytest.mark.integration
def test_concurrent_start_idempotency_and_quota(migrated):
    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        keys = [uuid4(), uuid4()]

        async def attempt(key):
            try:
                async with api.sessions() as session, session.begin():
                    return await start_run(session, user_id, selection, key)
            except AuthError as exc:
                return exc.code

        try:
            results = await asyncio.gather(*(attempt(key) for key in keys))
            assert sum(isinstance(result, tuple) for result in results) == 1
            assert "RUN_ALREADY_RUNNING" in results
            winner = next(result for result in results if isinstance(result, tuple))
            same = await attempt(keys[results.index(winner)])
            assert same[0]["id"] == winner[0]["id"] and same[1] is False
            async with api.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.runs")) == 1
                assert (
                    await session.scalar(text("SELECT sum(run_count) FROM app.quota_ledgers")) == 1
                )
        finally:
            await api.close()

    asyncio.run(execute())


@pytest.mark.integration
def test_event_api_filters_cursor_and_time_range(migrated, monkeypatch):
    async def setup():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        token = str(uuid4())
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
            run_id = UUID(run["id"])
            async with worker.sessions() as session, session.begin():
                await session.execute(text("""UPDATE app.runs SET
                    resumed_at=clock_timestamp()-interval '6 seconds' WHERE id=:run"""),
                    {"run": run_id})
            await process_one(worker, "filter-worker")
            owner = Database(migrated("migration_owner"))
            try:
                async with owner.sessions() as session, session.begin():
                    await session.execute(text("""INSERT INTO app.auth_sessions
                        (id,user_id,token_hash,csrf_hash,expires_at)
                        VALUES (:id,:user,:token,:csrf,clock_timestamp()+interval '1 day')"""),
                        {"id": uuid4(), "user": user_id, "token": auth.digest(token),
                         "csrf": auth.digest(auth.csrf(token))})
            finally:
                await owner.close()
            return run_id, token
        finally:
            await api.close()
            await worker.close()

    run_id, token = asyncio.run(setup())
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION, token)
        runs = client.get("/api/v1/runs", params={"status": "running", "limit": 1})
        assert runs.status_code == 200, runs.text
        assert [item["id"] for item in runs.json()["data"]] == [str(run_id)]
        assert runs.json()["meta"]["next_cursor"] is None
        assert client.get("/api/v1/runs", params={"cursor": "bad"}).status_code == 400
        base = f"/api/v1/runs/{run_id}/events"
        page = client.get(base, params={"limit": 2})
        assert page.status_code == 200, page.text
        assert len(page.json()["data"]) == 2
        cursor = page.json()["meta"]["next_cursor"]
        assert cursor
        following = client.get(base, params={"limit": 2, "cursor": cursor})
        assert following.status_code == 200
        assert following.json()["data"][0]["release_seq"] > page.json()["data"][-1]["release_seq"]
        assert client.get(base, params={"cursor": cursor, "source": "web"}).status_code == 400
        assert client.get(base, params={"after_seq": 1, "cursor": cursor}).status_code == 400
        filtered = client.get(base, params={"source": "authentication"})
        assert filtered.status_code == 200, filtered.text
        assert all(item["source"] == "authentication" for item in filtered.json()["data"])
        start = datetime.fromisoformat(page.json()["data"][0]["event_time"])
        bounded = client.get(base, params={"from": start.isoformat(),
                                           "to": (start + timedelta(seconds=2)).isoformat()})
        assert bounded.status_code == 200, bounded.text
        assert all(start <= datetime.fromisoformat(item["event_time"]) <
                   start + timedelta(seconds=2) for item in bounded.json()["data"])
        assert client.get(base, params={"from": datetime.now(UTC).isoformat(),
                                        "to": start.isoformat()}).status_code == 422


@pytest.mark.integration
def test_release_pause_resume_and_reclaim_without_duplicates(migrated):
    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
            run_id = UUID(str(run["id"]))
            job = await claim(worker, "test-worker")
            assert job is not None
            # Simulate crash before commit: no events have been written yet.
            async with worker.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.events")) == 0
            await release_events(worker, job)
            # Simulate crash after domain commit but before job completion.
            await release_events(worker, job)
            assert await settle(worker, job)
            async with worker.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.events")) == 1
            async with api.sessions() as session, session.begin():
                paused = await change_state(session, run_id, user_id, "pause", 1)
            assert paused["status"] == "paused"
            async with api.sessions() as session, session.begin():
                resumed = await change_state(session, run_id, user_id, "resume", 2)
            assert resumed["status"] == "running"
            assert await process_one(worker, "restart-worker")
            async with worker.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.events")) == 1
                assert (
                    await session.scalar(text("SELECT count(DISTINCT release_seq) FROM app.events"))
                    == 1
                )
                # An immediate resume wake-up can be too early for the next event.
                # It must queue a second wake-up at the same cursor, not collide
                # with its own idempotency key and strand the run.
                assert await session.scalar(text("""SELECT count(*) FROM app.jobs
                    WHERE run_id=:run AND type='release_events' AND status='queued'
                    AND dedupe_key LIKE :prefix"""),
                    {"run": run_id, "prefix": f"release:{run_id}:3:1:%"}) >= 1
            async with worker.sessions() as session, session.begin():
                await session.execute(text("""UPDATE app.runs SET
                    resumed_at=clock_timestamp()-interval '5 seconds' WHERE id=:run"""),
                    {"run": run_id})
                await session.execute(text("""UPDATE app.jobs SET available_at=clock_timestamp()
                    WHERE run_id=:run AND type='release_events' AND status='queued'"""),
                    {"run": run_id})
            for _ in range(10):
                if not await process_one(worker, "restart-worker"):
                    break
            async with worker.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.events")) > 1
                assert await session.scalar(text("""SELECT count(*)-count(DISTINCT release_seq)
                    FROM app.events WHERE run_id=:run"""), {"run": run_id}) == 0
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())


@pytest.mark.integration
def test_finish_freezes_cutoff_without_fake_score(migrated):
    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
            await process_one(worker, "worker")
            run_id = UUID(str(run["id"]))
            async with api.sessions() as session, session.begin():
                result = await finish_run(session, run_id, user_id, 1)
            assert result["status"] == "completing"
            async with api.sessions() as session, session.begin():
                repeated = await finish_run(session, run_id, user_id, 1)
            assert repeated["status"] == "completing"
            async with api.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.run_completions")) == 1
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.jobs WHERE type='finalize_run'")
                    )
                    == 1
                )
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.runs WHERE status='completed'")
                    )
                    == 0
                )
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())

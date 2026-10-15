# ruff: noqa: E501
import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.analysis.worker import analyze_job
from app.auth import service as auth
from app.auth.service import AuthError
from app.db.session import Database
from app.evaluation.__main__ import process_one as process_evaluation
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
                await session.execute(
                    text("""UPDATE app.runs SET
                    resumed_at=clock_timestamp()-interval '6 seconds' WHERE id=:run"""),
                    {"run": run_id},
                )
            await process_one(worker, "filter-worker")
            owner = Database(migrated("migration_owner"))
            try:
                async with owner.sessions() as session, session.begin():
                    await session.execute(
                        text("""INSERT INTO app.auth_sessions
                        (id,user_id,token_hash,csrf_hash,expires_at)
                        VALUES (:id,:user,:token,:csrf,clock_timestamp()+interval '1 day')"""),
                        {
                            "id": uuid4(),
                            "user": user_id,
                            "token": auth.digest(token),
                            "csrf": auth.digest(auth.csrf(token)),
                        },
                    )
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
        bounded = client.get(
            base,
            params={"from": start.isoformat(), "to": (start + timedelta(seconds=2)).isoformat()},
        )
        assert bounded.status_code == 200, bounded.text
        assert all(
            start <= datetime.fromisoformat(item["event_time"]) < start + timedelta(seconds=2)
            for item in bounded.json()["data"]
        )
        assert (
            client.get(
                base, params={"from": datetime.now(UTC).isoformat(), "to": start.isoformat()}
            ).status_code
            == 422
        )


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
                assert (
                    await session.scalar(
                        text("""SELECT count(*) FROM app.jobs
                    WHERE run_id=:run AND type='release_events' AND status='queued'
                    AND dedupe_key LIKE :prefix"""),
                        {"run": run_id, "prefix": f"release:{run_id}:3:1:%"},
                    )
                    >= 1
                )
            async with worker.sessions() as session, session.begin():
                await session.execute(
                    text("""UPDATE app.runs SET
                    resumed_at=clock_timestamp()-interval '5 seconds' WHERE id=:run"""),
                    {"run": run_id},
                )
                await session.execute(
                    text("""UPDATE app.jobs SET available_at=clock_timestamp()
                    WHERE run_id=:run AND type='release_events' AND status='queued'"""),
                    {"run": run_id},
                )
            for _ in range(10):
                if not await process_one(worker, "restart-worker"):
                    break
            async with worker.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.events")) > 1
                assert (
                    await session.scalar(
                        text("""SELECT count(*)-count(DISTINCT release_seq)
                    FROM app.events WHERE run_id=:run"""),
                        {"run": run_id},
                    )
                    == 0
                )
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


@pytest.mark.integration
def test_finish_evaluator_completes_immutable_snapshot_and_cancels_late_jobs(migrated, monkeypatch):
    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        evaluator = Database(migrated("evaluator_runtime"))
        owner = Database(migrated("migration_owner"))
        analyst_token = str(uuid4())
        instructor_token = str(uuid4())
        unassigned_token = str(uuid4())
        try:
            instructor_id = uuid4()
            unassigned_id = uuid4()
            async with owner.sessions() as session, session.begin():
                for account_id, label in ((instructor_id, "reviewer"), (unassigned_id, "observer")):
                    await session.execute(
                        text("""INSERT INTO app.users
                            (id,normalized_email,display_name,password_hash,role,status)
                            VALUES (:id,:email,:name,'$argon2id$fixture','instructor','active')"""),
                        {"id": account_id, "email": f"{account_id}@example.test", "name": label},
                    )
                    await session.execute(
                        text(
                            "INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests) VALUES (:id,10,20)"
                        ),
                        {"id": account_id},
                    )
                await session.execute(
                    text("""INSERT INTO app.instructor_assignments
                        (instructor_user_id,analyst_user_id) VALUES (:instructor,:analyst)"""),
                    {"instructor": instructor_id, "analyst": user_id},
                )
                for account_id, token in (
                    (user_id, analyst_token),
                    (instructor_id, instructor_token),
                    (unassigned_id, unassigned_token),
                ):
                    await session.execute(
                        text("""INSERT INTO app.auth_sessions
                            (id,user_id,token_hash,csrf_hash,expires_at)
                            VALUES (:id,:user,:token,:csrf,clock_timestamp()+interval '1 day')"""),
                        {
                            "id": uuid4(),
                            "user": account_id,
                            "token": auth.digest(token),
                            "csrf": auth.digest(auth.csrf(token)),
                        },
                    )
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
                run_id = UUID(str(run["id"]))
            async with api.sessions() as session:
                locked_truth = await session.scalar(
                    text("SELECT count(*) FROM private.owner_training_truth(:user,:run)"),
                    {"user": user_id, "run": run_id},
                )
                instructor_truth = await session.scalar(
                    text("SELECT count(*) FROM private.assigned_training_truth(:user,:run)"),
                    {"user": instructor_id, "run": run_id},
                )
            assert locked_truth == 0
            assert instructor_truth > 0
            async with api.sessions() as session, session.begin():
                result = await finish_run(session, run_id, user_id, 1)
            assert result["status"] == "completing"
            assert await process_evaluation(evaluator, "evaluator-test")
            async with api.sessions() as session:
                state = await session.scalar(
                    text("SELECT status FROM app.runs WHERE id=:run"), {"run": run_id}
                )
                evaluation = (
                    (
                        await session.execute(
                            text(
                                "SELECT status,metrics_json,snapshot_json FROM app.evaluations WHERE run_id=:run"
                            ),
                            {"run": run_id},
                        )
                    )
                    .mappings()
                    .one()
                )
                canceled = await session.scalar(
                    text("SELECT count(*) FROM app.jobs WHERE run_id=:run AND status='cancelled'"),
                    {"run": run_id},
                )
            assert state == "completed"
            assert evaluation["status"] == "completed"
            assert evaluation["metrics_json"]["precision"] is None
            assert evaluation["metrics_json"]["recall"] == 0
            assert evaluation["metrics_json"]["precision_null_reason"] == "NO_POSITIVE_CANDIDATES"
            assert evaluation["snapshot_json"]["events"] == []
            assert canceled >= 1  # pre-cutoff release wake-up cannot mutate the completed run
            async with api.sessions() as session:
                visible_truth = await session.scalar(
                    text("SELECT count(*) FROM private.assigned_evaluation_truth(:user,:run)"),
                    {"user": instructor_id, "run": run_id},
                )
                hidden_truth = await session.scalar(
                    text("SELECT count(*) FROM private.assigned_evaluation_truth(:user,:run)"),
                    {"user": unassigned_id, "run": run_id},
                )
                with pytest.raises(DBAPIError):
                    await session.execute(text("SELECT * FROM private.ground_truth"))
            assert visible_truth > 0
            assert hidden_truth == 0
            async with owner.sessions() as session, session.begin():
                with pytest.raises(DBAPIError, match="IMMUTABLE_RECORD"):
                    await session.execute(
                        text(
                            "UPDATE app.evaluations SET metrics_json='{}'::jsonb WHERE run_id=:run"
                        ),
                        {"run": run_id},
                    )

            monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
            monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
            monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
            with TestClient(app, headers={"Origin": "http://testserver"}) as client:
                client.cookies.set(auth.SESSION, instructor_token)
                assert client.get("/api/v1/admin/runs").status_code == 200
                assert client.get(f"/api/v1/admin/runs/{run_id}/evaluation").status_code == 200
                truth_response = client.get(f"/api/v1/admin/runs/{run_id}/ground-truth")
                assert truth_response.status_code == 200 and truth_response.json()["data"]
                csrf = auth.csrf(instructor_token)
                note_write = client.post(
                    f"/api/v1/runs/{run_id}/tickets/{uuid4()}/notes",
                    json={"body": "Instructor cannot replace a learner note", "evidence_ids": []},
                    headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())},
                )
                assert note_write.status_code == 403
                comment = client.post(
                    f"/api/v1/admin/runs/{run_id}/comments",
                    json={"body": "Review completed snapshot"},
                    headers={"X-CSRF-Token": csrf},
                )
                assert comment.status_code == 201
                assert len(client.get(f"/api/v1/admin/runs/{run_id}/comments").json()["data"]) == 1
                experiment = client.post(
                    f"/api/v1/admin/runs/{run_id}/experiments",
                    headers={"X-CSRF-Token": csrf},
                )
                assert experiment.status_code == 201, experiment.text
                arms = experiment.json()["data"]["arms"]
                assert arms["A"]["status"] == arms["B"]["status"] == "completed"
                assert arms["C"]["status"] == "unavailable"
                assert arms["C"]["metrics"] is None
                client.cookies.set(auth.SESSION, unassigned_token)
                assert client.get(f"/api/v1/admin/runs/{run_id}/evaluation").status_code == 404
                assert client.get(f"/api/v1/admin/runs/{run_id}/ground-truth").status_code == 404
                client.cookies.set(auth.SESSION, analyst_token)
                learner_truth = client.get(f"/api/v1/runs/{run_id}/ground-truth")
                assert learner_truth.status_code == 200 and learner_truth.json()["data"]
                exported = client.get(f"/api/v1/runs/{run_id}/export")
                assert exported.status_code == 200
                exported_json = exported.json()
                assert exported_json["run_id"] == str(run_id)
                assert len(exported_json["dataset_hash"]) == 64
                assert exported_json["snapshot"]["detections"] == []
        finally:
            await api.close()
            await evaluator.close()
            await owner.close()

    asyncio.run(execute())


@pytest.mark.integration
def test_late_analysis_result_is_fenced_after_drain_deadline(migrated):
    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        evaluator = Database(migrated("evaluator_runtime"))
        owner = Database(migrated("migration_owner"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
                run_id = UUID(str(run["id"]))
            analysis_id = uuid4()
            async with worker.sessions() as session, session.begin():
                await session.execute(
                    text(
                        "UPDATE app.jobs SET status='failed' WHERE run_id=:run AND type='release_events'"
                    ),
                    {"run": run_id},
                )
                await session.execute(
                    text("""INSERT INTO app.analyses
                        (id,run_id,correlation_key,evidence_hash,attempt_group,mode,model_id,prompt_version,status)
                        VALUES (:id,:run,'late-test','frozen-hash',:group,'mock','mock','prompt-v1','queued')"""),
                    {"id": analysis_id, "run": run_id, "group": uuid4()},
                )
                await session.execute(
                    text("""INSERT INTO app.jobs(id,run_id,type,dedupe_key,payload)
                        VALUES (:id,:run,'analyze_evidence',:dedupe,CAST(:payload AS jsonb))"""),
                    {
                        "id": uuid4(),
                        "run": run_id,
                        "dedupe": f"late-analysis:{analysis_id}",
                        "payload": json.dumps({"analysis_id": str(analysis_id)}),
                    },
                )
            claimed = await claim(worker, "late-worker")
            assert claimed and claimed["type"] == "analyze_evidence"
            async with api.sessions() as session, session.begin():
                await finish_run(session, run_id, user_id, 1)
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("""UPDATE app.run_completions SET drain_deadline=clock_timestamp()-interval '1 second'
                        WHERE run_id=:run"""),
                    {"run": run_id},
                )
            assert await process_evaluation(evaluator, "evaluator-test")
            await analyze_job(worker, claimed)
            async with api.sessions() as session:
                state = await session.scalar(
                    text("SELECT status FROM app.runs WHERE id=:run"), {"run": run_id}
                )
                analysis = (
                    await session.execute(
                        text("SELECT status,result_json FROM app.analyses WHERE id=:id"),
                        {"id": analysis_id},
                    )
                ).one()
                job_state = await session.scalar(
                    text("SELECT status FROM app.jobs WHERE id=:id"), {"id": claimed["id"]}
                )
            assert state == "completed"
            assert analysis.status == "queued" and analysis.result_json is None
            assert job_state == "cancelled"
        finally:
            await api.close()
            await worker.close()
            await evaluator.close()
            await owner.close()

    asyncio.run(execute())


@pytest.mark.integration
def test_deleted_automatic_ticket_does_not_remove_detector_denominator(migrated):
    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        evaluator = Database(migrated("evaluator_runtime"))
        owner = Database(migrated("migration_owner"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
                run_id = UUID(str(run["id"]))
            async with owner.sessions() as session:
                instance = (
                    (
                        await session.execute(
                            text(
                                "SELECT id,scenario_id FROM app.scenario_instances WHERE run_id=:run"
                            ),
                            {"run": run_id},
                        )
                    )
                    .mappings()
                    .one()
                )
                truth = (
                    (
                        await session.execute(
                            text("""SELECT incident_key,threat_label,expected_evidence_keys
                            FROM private.ground_truth WHERE scenario_id=:scenario
                            ORDER BY incident_key LIMIT 1"""),
                            {"scenario": instance["scenario_id"]},
                        )
                    )
                    .mappings()
                    .one()
                )
            event_id, detection_id, alert_id, ticket_id = (uuid4() for _ in range(4))
            event_key = truth["expected_evidence_keys"][0]
            async with worker.sessions() as session, session.begin():
                await session.execute(
                    text("UPDATE app.runs SET release_cursor=1 WHERE id=:run"), {"run": run_id}
                )
                await session.execute(
                    text("""INSERT INTO app.events
                        (id,run_id,scenario_instance_id,fixture_event_key,release_seq,event_time,source,
                         asset_id,username,request_json,response_json,log_json,content_hash)
                        VALUES (:id,:run,:instance,:key,1,clock_timestamp(),'web','web-01','synthetic',
                                '{}'::jsonb,'{}'::jsonb,'{}'::jsonb,:hash)"""),
                    {
                        "id": event_id,
                        "run": run_id,
                        "instance": instance["id"],
                        "key": event_key,
                        "hash": "a" * 64,
                    },
                )
                await session.execute(
                    text("""INSERT INTO app.detections
                        (id,run_id,detector_type,detector_version,correlation_key,evidence_snapshot_hash,
                         severity,explanation) VALUES (:id,:run,'rule','test-v1','test-correlation',:hash,
                         'medium','synthetic detection')"""),
                    {"id": detection_id, "run": run_id, "hash": "b" * 64},
                )
                await session.execute(
                    text(
                        "INSERT INTO app.detection_evidence(run_id,detection_id,event_id) VALUES (:run,:detection,:event)"
                    ),
                    {"run": run_id, "detection": detection_id, "event": event_id},
                )
                await session.execute(
                    text(
                        "INSERT INTO app.alerts(id,run_id,detection_id,severity) VALUES (:id,:run,:detection,'medium')"
                    ),
                    {"id": alert_id, "run": run_id, "detection": detection_id},
                )
                await session.execute(
                    text("""INSERT INTO app.tickets
                        (id,run_id,origin,correlation_key,title,severity) VALUES
                        (:id,:run,'automatic','test-correlation','Synthetic ticket','medium')"""),
                    {"id": ticket_id, "run": run_id},
                )
                await session.execute(
                    text(
                        "INSERT INTO app.ticket_alerts(run_id,ticket_id,alert_id) VALUES (:run,:ticket,:alert)"
                    ),
                    {"run": run_id, "ticket": ticket_id, "alert": alert_id},
                )
                await session.execute(
                    text(
                        "INSERT INTO app.ticket_events(run_id,ticket_id,event_id) VALUES (:run,:ticket,:event)"
                    ),
                    {"run": run_id, "ticket": ticket_id, "event": event_id},
                )
                await session.execute(
                    text("""UPDATE app.tickets SET deleted_at=clock_timestamp(),deleted_by=:user,
                        delete_reason='denominator regression' WHERE id=:ticket"""),
                    {"user": user_id, "ticket": ticket_id},
                )
            async with api.sessions() as session, session.begin():
                await finish_run(session, run_id, user_id, 1)
            assert await process_evaluation(evaluator, "evaluator-test")
            async with api.sessions() as session:
                result = (
                    (
                        await session.execute(
                            text(
                                "SELECT metrics_json,snapshot_json FROM app.evaluations WHERE run_id=:run"
                            ),
                            {"run": run_id},
                        )
                    )
                    .mappings()
                    .one()
                )
            assert result["metrics_json"]["tp"] + result["metrics_json"]["fp"] == 1
            assert result["snapshot_json"]["detections"][0]["ticket_deleted_at_cutoff"] is True
        finally:
            await api.close()
            await worker.close()
            await evaluator.close()
            await owner.close()

    asyncio.run(execute())

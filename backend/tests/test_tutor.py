import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_database_training import configure, prepare
from test_dify_workflow import hashes, outputs

from app.auth import service as auth
from app.db.session import Database
from app.knowledge.dify_client import DifyUnavailable
from app.knowledge.dify_workflow import WorkflowReply
from app.main import app
from app.tutor.release import activate
from app.tutor.service import NO_MATCH_ANSWER
from app.tutor.worker import process_question
from app.worker.fencing import LeaseLost
from app.worker.jobs import claim, settle


@pytest.mark.integration
def test_operator_activation_is_audited_version_checked_and_not_runtime_accessible(migrated):
    from test_tutor_release import review

    async def check():
        owner = Database(migrated("migration_owner"))
        worker = Database(migrated("worker_runtime"))
        try:
            assert await activate(owner, review(), 1) == 2
            with pytest.raises(ValueError, match="version changed"):
                await activate(owner, review(), 1)
            with pytest.raises(ValueError, match="operator role"):
                await activate(worker, review(), 2)
            combined = review() | {
                "status": "approved_for_tutor_and_grade",
                "grade_mode_verified": True,
                "grade_call_bound_usd": "0.010000",
            }
            assert await activate(owner, combined, 2, enable_grade=True) == 3
        finally:
            await owner.close()
            await worker.close()

    asyncio.run(check())
    events = asyncio.run(sql(migrated, "SELECT action FROM app.audit_logs"))
    assert [event["action"] for event in events] == [
        "tutor.release.activate",
        "tutor.release.activate",
    ]


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["no_match", "false_no_match", "version_changed"])
def test_empty_retrieval_and_version_drift_do_not_become_answers(
    migrated, monkeypatch, tmp_path, mode
):
    users, tokens, payload = fixture(migrated, monkeypatch, tmp_path)

    async def fake(*args):
        if mode == "version_changed":
            raise DifyUnavailable("DIFY_WORKFLOW_VERSION_MISMATCH")
        return WorkflowReply(
            {"answer": NO_MATCH_ANSWER, "sources": []}, 0 if mode == "no_match" else 1, "run"
        )

    monkeypatch.setattr("app.tutor.worker.run_workflow", fake)
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        response = client.post(
            "/api/v1/tutor/questions",
            json=payload,
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": auth.csrf(tokens[0]),
                "Idempotency-Key": str(uuid4()),
            },
        )
        assert response.status_code == 202

        async def work():
            database = Database(migrated("worker_runtime"))
            try:
                job = await claim(database, "no-match-test")
                await process_question(database, job)
                assert await settle(database, job)
            finally:
                await database.close()

        asyncio.run(work())
        row = asyncio.run(sql(migrated, "SELECT * FROM app.tutor_questions"))[0]
        assert row["result_json"] is None
        assert row["status"] == ("unavailable" if mode == "no_match" else "needs_review")
        assert row["usage_status"] == ("unknown" if mode == "version_changed" else "reconciled")
        if mode == "version_changed":
            availability = client.get("/api/v1/tutor/availability").json()["data"]
            assert not availability["available"]
            assert availability["reason"] == "DIFY_WORKFLOW_VERSION_MISMATCH"
            assert (
                client.post(
                    "/api/v1/tutor/questions",
                    json=payload,
                    headers={
                        "Origin": "http://testserver",
                        "X-CSRF-Token": auth.csrf(tokens[0]),
                        "Idempotency-Key": str(uuid4()),
                    },
                ).status_code
                == 503
            )


async def setup(url, users):
    db = Database(url("migration_owner"))
    try:
        async with db.sessions() as session, session.begin():
            for owner in users:
                await session.execute(
                    text("""INSERT INTO app.user_quotas
                    (user_id,daily_runs,daily_ai_requests) VALUES(:id,10,20)
                    ON CONFLICT(user_id) DO NOTHING"""),
                    {"id": owner},
                )
            await session.execute(
                text("""UPDATE app.tutor_policy SET enabled=true,
                cost_bound_verified=true,workflow_id='version-test',corpus_revision='test-only',
                document_ids='["approved-document"]'::jsonb,
                chunk_hashes=CAST(:hashes AS jsonb) WHERE id=1"""),
                {"hashes": json.dumps(hashes())},
            )
            return await session.scalar(text("SELECT id FROM app.lessons ORDER BY id LIMIT 1"))
    finally:
        await db.close()


async def sql(url, statement):
    db = Database(url("migration_owner"))
    try:
        async with db.sessions() as session, session.begin():
            result = await session.execute(text(statement))
            return result.mappings().all() if result.returns_rows else []
    finally:
        await db.close()


def fixture(migrated, monkeypatch, tmp_path):
    users, tokens, _, _ = asyncio.run(prepare(migrated))
    configure(monkeypatch, migrated)
    secret = tmp_path / "fake-key"
    secret.write_text("fake-key-never-dispatched", encoding="utf8")
    monkeypatch.setenv("DIFY_APP_KEY_FILE", str(secret))
    lesson = asyncio.run(setup(migrated, users))
    return users, tokens, {"lesson_id": str(lesson), "question": "HTTP 403 คืออะไร"}


@pytest.mark.integration
def test_tutor_auth_idempotency_owner_and_worker_persistence(migrated, monkeypatch, tmp_path):
    users, tokens, payload = fixture(migrated, monkeypatch, tmp_path)
    calls = []

    async def fake(*args):
        calls.append(args)
        return WorkflowReply(outputs(), 123, "fake-run")

    monkeypatch.setattr("app.tutor.worker.run_workflow", fake)
    key = str(uuid4())
    headers = {
        "Origin": "http://testserver",
        "X-CSRF-Token": auth.csrf(tokens[0]),
        "Idempotency-Key": key,
    }
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/tutor/questions", json=payload, headers=headers).status_code == 401
        )
        client.cookies.set(auth.SESSION, tokens[0])
        assert (
            client.post(
                "/api/v1/tutor/questions", json=payload, headers={"Idempotency-Key": key}
            ).status_code
            == 403
        )
        result = client.post("/api/v1/tutor/questions", json=payload, headers=headers)
        assert result.status_code == 202, result.text
        question = result.json()["data"]["id"]
        assert (
            client.post("/api/v1/tutor/questions", json=payload, headers=headers).json()["data"][
                "id"
            ]
            == question
        )
        assert (
            client.post(
                "/api/v1/tutor/questions", json=payload | {"question": "changed"}, headers=headers
            ).status_code
            == 409
        )
        client.cookies.set(auth.SESSION, tokens[1])
        assert client.get(f"/api/v1/tutor/questions/{question}").status_code == 404
        client.cookies.set(auth.SESSION, tokens[0])

        async def work():
            db = Database(migrated("worker_runtime"))
            try:
                job = await claim(db, "test-tutor")
                assert job["type"] == "tutor_question"
                with pytest.raises(LeaseLost):
                    await process_question(db, job | {"lease_token": uuid4()})
                await process_question(db, job)
                await process_question(db, job)  # crash after result commit, before job settle
                assert await settle(db, job)
            finally:
                await db.close()

        asyncio.run(work())
        assert len(calls) == 1
        usage = asyncio.run(
            sql(migrated, "SELECT usage_status,reserved_usd FROM app.tutor_questions")
        )
        assert usage[0]["usage_status"] == "reconciled"
        assert str(usage[0]["reserved_usd"]) == "0.025000"
        view = client.get(f"/api/v1/tutor/questions/{question}").json()["data"]
        assert view["status"] == "succeeded" and view["result"]["sources"][0]["section_ids"] == [
            "SOC-003"
        ]
        assert len(client.get("/api/v1/tutor/questions").json()["data"]) == 1
        # Hundreds of known, conservatively accounted requests on a past UTC day
        # are not a lifetime limit. Today's user quota still applies normally.
        asyncio.run(sql(migrated, "UPDATE app.tutor_questions SET budget_day=budget_day-1"))
        asyncio.run(
            sql(
                migrated,
                """INSERT INTO app.tutor_questions
            (id,owner_user_id,lesson_id,question,idempotency_key,request_hash,
             policy_version,workflow_id,corpus_revision,reserved_usd,budget_day,usage_status)
            SELECT gen_random_uuid(),owner_user_id,lesson_id,question,
             gen_random_uuid(),request_hash,
             policy_version,workflow_id,corpus_revision,reserved_usd,budget_day,'reconciled'
            FROM app.tutor_questions CROSS JOIN generate_series(1,201)""",
            )
        )
        assert (
            client.post(
                "/api/v1/tutor/questions",
                json=payload,
                headers=headers | {"Idempotency-Key": str(uuid4())},
            ).status_code
            == 202
        )
        asyncio.run(
            sql(migrated, "UPDATE app.tutor_policy SET enabled=false,version=version+1 WHERE id=1")
        )
        assert client.get(f"/api/v1/tutor/questions/{question}").json()["data"]["result"] is None
        assert (
            client.post(
                "/api/v1/tutor/questions",
                json=payload,
                headers=headers | {"Idempotency-Key": str(uuid4())},
            ).status_code
            == 503
        )


@pytest.mark.integration
def test_concurrent_quota_and_unknown_dispatch_never_retries(migrated, monkeypatch, tmp_path):
    users, tokens, payload = fixture(migrated, monkeypatch, tmp_path)
    headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.csrf(tokens[0])}
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(
                pool.map(
                    lambda _: (
                        client.post(
                            "/api/v1/tutor/questions",
                            json=payload,
                            headers=headers | {"Idempotency-Key": str(uuid4())},
                        ).status_code
                    ),
                    range(12),
                )
            )
        assert codes.count(202) == 12
        totals = asyncio.run(
            sql(migrated, "SELECT sum(reserved_usd) AS usd FROM app.tutor_questions")
        )
        assert str(totals[0]["usd"]) == "0.300000"
        asyncio.run(
            sql(
                migrated,
                "UPDATE app.tutor_questions SET budget_day=budget_day-1,usage_status='unknown'",
            )
        )
        assert (
            client.post(
                "/api/v1/tutor/questions",
                json=payload,
                headers=headers | {"Idempotency-Key": str(uuid4())},
            ).status_code
            == 202
        )

    calls = []

    async def crash(*args):
        calls.append(1)
        raise RuntimeError("simulated crash after dispatch")

    monkeypatch.setattr("app.tutor.worker.run_workflow", crash)

    async def work():
        db = Database(migrated("worker_runtime"))
        try:
            job = await claim(db, "crash-test")
            with pytest.raises(RuntimeError):
                await process_question(db, job)
            await process_question(db, job)  # reclaim simulates restart after admission commit
            assert await settle(db, job)
            async with db.sessions() as session:
                row = (
                    (
                        await session.execute(
                            text("SELECT * FROM app.tutor_questions WHERE id=:id"),
                            {"id": UUID(job["payload"]["question_id"])},
                        )
                    )
                    .mappings()
                    .one()
                )
                assert row["status"] == "needs_review" and row["usage_status"] == "unknown"
        finally:
            await db.close()

    asyncio.run(work())
    assert len(calls) == 1


@pytest.mark.integration
def test_invalid_citations_and_outage_do_not_change_learning_or_create_fake_score(
    migrated, monkeypatch, tmp_path
):
    users, tokens, payload = fixture(migrated, monkeypatch, tmp_path)
    headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.csrf(tokens[0])}
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        for failure in (False, True):

            async def fake(*args, failure=failure):
                if failure:
                    raise DifyUnavailable("DIFY_TIMEOUT")
                return WorkflowReply({"answer": "SOC-403"}, None, "fake")

            monkeypatch.setattr("app.tutor.worker.run_workflow", fake)
            response = client.post(
                "/api/v1/tutor/questions",
                json=payload,
                headers=headers | {"Idempotency-Key": str(uuid4())},
            )
            assert response.status_code == 202

            async def work():
                db = Database(migrated("worker_runtime"))
                try:
                    job = await claim(db, "invalid-test")
                    await process_question(db, job)
                    await settle(db, job)
                finally:
                    await db.close()

            asyncio.run(work())
            view = client.get(f"/api/v1/tutor/questions/{response.json()['data']['id']}").json()[
                "data"
            ]
            assert view["status"] == "needs_review" and view["result"] is None
        assert (
            asyncio.run(sql(migrated, "SELECT count(*) AS total FROM app.level_unlocks"))[0][
                "total"
            ]
            == 0
        )

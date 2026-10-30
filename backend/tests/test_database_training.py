"""Real PostgreSQL/runtimes; never reset the managed Supabase database."""

import asyncio
import hashlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.auth import service as auth
from app.db.migrate import migrate
from app.db.session import Database
from app.learning.practice_models import PracticeAnswer, PracticeCase, WrittenInput
from app.learning.seed_full import seed
from app.main import app


def test_bank_has_thirty_distinct_cases_and_ten_questions_per_level():
    from operator_content.training_bank import QUESTIONS, cases, identifier

    levels = {index: identifier(f"level-{index}") for index in (1, 2, 3)}
    bank = cases(levels)
    assert len(bank) == len({item["id"] for item in bank}) == 30
    assert Counter(item["level_id"] for item in bank) == {value: 10 for value in levels.values()}
    assert {item["category"] for item in bank} == {
        "authentication",
        "web",
        "access",
        "evidence",
        "change",
        "data",
        "anomaly",
        "availability",
    }
    assert [len(QUESTIONS[level]) for level in (1, 2, 3)] == [10, 10, 10]
    assert len({question for values in QUESTIONS.values() for question in values}) == 30
    for case in bank:
        public = case["content"]
        view = PracticeCase.model_validate(
            {
                **{
                    key: case[key]
                    for key in ("id", "stable_key", "level_id", "category", "title", "version")
                },
                "level": next(key for key, value in levels.items() if value == case["level_id"]),
                "available": True,
                **public,
            }
        )
        assert len(view.events) >= 1
        assert case["truth"]["explanation"] and case["truth"]["limitation"]
        assert set(case["truth"]["evidence_ids"]) == {str(event.id) for event in view.events}
        assert "expected_severity" not in view.model_dump_json()


def test_answers_reject_blank_reason_duplicate_evidence_and_client_scores():
    payload = {
        "evidence_ids": [uuid4()],
        "severity": "low",
        "disposition": "undetermined",
        "reason": "x",
    }
    for invalid in (
        payload | {"reason": "   "},
        payload | {"score": 10},
        payload | {"evidence_ids": payload["evidence_ids"] * 2},
    ):
        with pytest.raises(ValidationError):
            PracticeAnswer.model_validate(invalid)
    with pytest.raises(ValidationError):
        WrittenInput.model_validate({"answers": []})


async def prepare(url):
    owner = Database(url("migration_owner"))
    tokens = [str(uuid4()), str(uuid4())]
    users = [uuid4(), uuid4()]
    try:
        await seed(owner)
        await seed(owner)  # published content and keys must remain idempotent
        async with owner.sessions() as session, session.begin():
            for user, token in zip(users, tokens, strict=True):
                await session.execute(
                    text("""INSERT INTO app.users
                    (id,normalized_email,display_name,password_hash,role,status)
                    VALUES (:id,:email,'Learner','$argon2id$fixture','analyst','active')"""),
                    {"id": user, "email": f"{user}@example.test"},
                )
                await session.execute(
                    text("""INSERT INTO app.auth_sessions
                    (id,user_id,token_hash,csrf_hash,expires_at)
                    VALUES (:id,:user,:token,:csrf,now()+interval '1 day')"""),
                    {
                        "id": uuid4(),
                        "user": user,
                        "token": auth.digest(token),
                        "csrf": auth.digest(auth.csrf(token)),
                    },
                )
            counts = {
                table: await session.scalar(text(f"SELECT count(*) FROM app.{table}"))
                for table in ("lessons", "practice_cases", "written_questions")
            }
            assert counts == {"lessons": 9, "practice_cases": 30, "written_questions": 30}
            case_id = await session.scalar(
                text("SELECT id FROM app.practice_cases WHERE stable_key='TR-L1-02'")
            )
            truth = (
                (
                    await session.execute(
                        text("SELECT * FROM private.practice_truths WHERE case_id=:id"),
                        {"id": case_id},
                    )
                )
                .mappings()
                .one()
            )
            return users, tokens, case_id, dict(truth)
    finally:
        await owner.close()


def configure(monkeypatch, migrated):
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")


@pytest.mark.integration
def test_practice_persistence_feedback_replay_races_and_permissions(migrated, monkeypatch):
    users, tokens, case_id, truth = asyncio.run(prepare(migrated))
    configure(monkeypatch, migrated)
    path = f"/api/v1/practice/cases/{case_id}"
    payload = {
        "evidence_ids": truth["evidence_ids"],
        "severity": truth["severity"],
        "disposition": truth["disposition"],
        "reason": "ยังไม่พบ session ที่สร้างสำเร็จ",
    }
    headers = {"X-CSRF-Token": auth.csrf(tokens[0])}
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        assert client.get(path).status_code == 401
        client.cookies.set(auth.SESSION, tokens[0])
        catalog = client.get("/api/v1/practice/cases").json()["data"]
        assert len(catalog) == 30
        assert sum(item["available"] for item in catalog) == 10
        locked = next(item for item in catalog if not item["available"])
        assert client.get(f"/api/v1/practice/cases/{locked['id']}").status_code == 404
        public = client.get(path)
        assert public.status_code == 200
        for secret in ("truth", "explanation", "expected_severity", "feedback_json"):
            assert secret not in public.json()["data"]
        assert (
            client.post(
                path + "/answers", json=payload, headers={"Idempotency-Key": str(uuid4())}
            ).status_code
            == 403
        )
        invalid = client.post(
            path + "/answers",
            json=payload | {"evidence_ids": [str(uuid4())]},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert invalid.status_code == 422
        saved = client.patch(
            path + "/draft", json={"expected_version": 0, "answer": payload}, headers=headers
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["data"]["draft_version"] == 1
        assert client.get(path).json()["data"]["draft"]["reason"] == payload["reason"]

        def edit():
            return client.patch(
                path + "/draft", json={"expected_version": 1, "answer": payload}, headers=headers
            )

        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(lambda _: edit(), range(2)))
        assert sorted(response.status_code for response in responses) == [200, 409]
        key = str(uuid4())

        def submit():
            return client.post(
                path + "/answers", json=payload, headers=headers | {"Idempotency-Key": key}
            )

        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(lambda _: submit(), range(2)))
        assert [response.status_code for response in responses] == [201, 201]
        assert responses[0].json()["data"] == responses[1].json()["data"]
        feedback = responses[0].json()["data"]["feedback"]
        assert feedback["classification_correct"] and feedback["evidence_correct"]
        assert feedback["reason_review_status"] == "unavailable"
        assert feedback["is_exam_result"] is False
        changed = client.post(
            path + "/answers",
            json=payload | {"severity": "critical"},
            headers=headers | {"Idempotency-Key": key},
        )
        assert changed.status_code == 409
        incorrect = client.post(
            path + "/answers",
            json=payload | {"severity": "critical"},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert incorrect.status_code == 201
        assert incorrect.json()["data"]["feedback"]["classification_correct"] is False
        assert len(client.get(path + "/answers").json()["data"]) == 2
    # A new HTTP client confirms data survives browser refresh, not client memory.
    with TestClient(app) as refreshed:
        refreshed.cookies.set(auth.SESSION, tokens[0])
        assert len(refreshed.get(path + "/answers").json()["data"]) == 2
        refreshed.cookies.set(auth.SESSION, tokens[1])
        assert refreshed.get(path + "/answers").json()["data"] == []
        assert refreshed.get(path).json()["data"]["draft"] is None

    async def grants():
        db = Database(migrated("api_runtime"))
        try:
            async with db.sessions() as session:
                with pytest.raises(DBAPIError):
                    await session.execute(text("SELECT * FROM private.practice_truths"))
            async with db.sessions() as session:
                with pytest.raises(DBAPIError):
                    await session.execute(text("UPDATE app.practice_answers SET answer_json='{}'"))
            async with db.sessions() as session:
                answer_id = await session.scalar(
                    text("SELECT id FROM app.practice_answers LIMIT 1")
                )
                assert (
                    await session.scalar(
                        text("SELECT private.review_practice(:user,:id)"),
                        {"user": users[1], "id": answer_id},
                    )
                    is None
                )
        finally:
            await db.close()

    asyncio.run(grants())
    # Re-running the wrapper after application use does not change the ledger or answers.
    asyncio.run(migrate(migrated("migration_owner"), "training-test-repeat"))


@pytest.mark.integration
def test_practice_ai_requires_submitted_owned_answer_and_persists_validated_reply(
    migrated, monkeypatch
):
    from app.knowledge.dify_workflow import WorkflowReply
    from app.worker.jobs import process_one

    users, tokens, case_id, truth = asyncio.run(prepare(migrated))
    configure(monkeypatch, migrated)
    monkeypatch.setattr("app.tutor.service.readiness", lambda policy: None)
    context = "## SOC-003\n403 หมายถึงเซิร์ฟเวอร์ปฏิเสธคำขอ"
    document = "00000000-0000-4000-8000-000000000003"

    async def prepare_policy():
        db = Database(migrated("migration_owner"))
        try:
            async with db.sessions() as session, session.begin():
                for user_id in users:
                    await session.execute(
                        text("INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests) VALUES(:user,10,20)"),
                        {"user": user_id},
                    )
                await session.execute(
                    text("""UPDATE app.tutor_policy SET enabled=true,
                    cost_bound_verified=true,practice_enabled=true,
                    practice_call_bound_usd=0.01,workflow_id=:workflow,
                    corpus_revision='practice-test',document_ids=CAST(:documents AS jsonb),
                    chunk_hashes=CAST(:hashes AS jsonb) WHERE id=1"""),
                    {
                        "workflow": str(uuid4()),
                        "documents": f'["{document}"]',
                        "hashes": f'["{hashlib.sha256(context.encode()).hexdigest()}"]',
                    },
                )
        finally:
            await db.close()

    class FakeConfig:
        @classmethod
        def from_env(cls):
            return cls()

        def read_api_key(self):
            return "test-only"

    async def fake_workflow(config, workflow, question, user, mode):
        assert mode == "practice" and "response" in question
        return WorkflowReply(
            {"answer": "พบคำขอถูกปฏิเสธ ยังสรุปการอ่านข้อมูลไม่ได้ SOC-003", "sources": [
                {"title": "คู่มือ", "content": context, "metadata": {"document_id": document}}
            ]},
            42,
            "synthetic-run",
        )

    asyncio.run(prepare_policy())
    monkeypatch.setattr("app.learning.practice_ai_worker.DifyConfig", FakeConfig)
    monkeypatch.setattr("app.learning.practice_ai_worker.run_workflow", fake_workflow)
    path = f"/api/v1/practice/cases/{case_id}"
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        headers = {"X-CSRF-Token": auth.csrf(tokens[0]), "Idempotency-Key": str(uuid4())}
        rejected = client.post(path + "/ai-questions", json={"answer_id": str(uuid4()), "question": "403 คืออะไร"}, headers=headers)
        assert rejected.status_code == 404
        assert client.get("/api/v1/practice/ai-availability").json()["data"]["available"]
        answer = client.post(path + "/answers", json={
            "evidence_ids": truth["evidence_ids"], "severity": truth["severity"],
            "disposition": truth["disposition"], "reason": "ตรวจหลักฐานก่อนสรุป",
        }, headers=headers | {"Idempotency-Key": str(uuid4())})
        assert answer.status_code == 201, answer.text
        body = {"answer_id": answer.json()["data"]["id"], "question": "403 คืออะไร"}
        queued = client.post(path + "/ai-questions", json=body, headers=headers)
        assert queued.status_code == 202, queued.text
        repeat = client.post(path + "/ai-questions", json=body, headers=headers)
        assert repeat.status_code == 202
        assert repeat.json()["data"]["id"] == queued.json()["data"]["id"]
        client.cookies.set(auth.SESSION, tokens[1])
        assert client.get(path + "/ai-questions").json()["data"] == []
        assert client.post(path + "/ai-questions", json=body, headers={
            "X-CSRF-Token": auth.csrf(tokens[1]), "Idempotency-Key": str(uuid4()),
        }).status_code == 404

    worker = Database(migrated("worker_runtime"))
    try:
        assert asyncio.run(process_one(worker, "practice-ai-test"))
    finally:
        asyncio.run(worker.close())
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        history = client.get(path + "/ai-questions")
        assert history.status_code == 200
        result = history.json()["data"][0]
        assert result["status"] == "succeeded"
        assert result["result"]["sources"][0]["section_ids"] == ["SOC-003"]


@pytest.mark.integration
def test_full_curriculum_order_gates_and_written_submission_snapshot(migrated, monkeypatch):
    users, tokens, _, _ = asyncio.run(prepare(migrated))
    configure(monkeypatch, migrated)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        levels = client.get("/api/v1/learning-path").json()["data"]["levels"]
        assert [len(level["lessons"]) for level in levels] == [3, 3, 3]
        level = levels[0]
        headers = {"X-CSRF-Token": auth.csrf(tokens[0])}
        base = f"/api/v1/learning/levels/{level['id']}"
        assert client.get(base + "/written-questions").status_code == 409
        assert client.get(f"/api/v1/lessons/{levels[1]['lessons'][0]['id']}").status_code == 404
        second = client.get(f"/api/v1/lessons/{level['lessons'][1]['id']}").json()["data"]
        out_of_order = client.post(
            f"/api/v1/lessons/{second['id']}/steps/{second['steps'][0]['id']}/complete",
            json={"expected_version": 0},
            headers=headers,
        )
        assert out_of_order.status_code == 409
        for summary in level["lessons"]:
            lesson = client.get(f"/api/v1/lessons/{summary['id']}").json()["data"]
            version = 0
            for step in lesson["steps"]:
                response = client.post(
                    f"/api/v1/lessons/{lesson['id']}/steps/{step['id']}/complete",
                    json={"expected_version": version},
                    headers=headers,
                )
                assert response.status_code == 200, response.text
                version = response.json()["data"]["version"]
            response = client.post(
                f"/api/v1/lessons/{lesson['id']}/complete",
                json={"expected_version": version},
                headers=headers,
            )
            assert response.status_code == 200
        # 19 writes above (one rejected ordering request + 3*6 saves).
        # The dedicated 60/min lesson limit is still enforced; auth limits are unchanged.
        first = client.get(f"/api/v1/lessons/{level['lessons'][0]['id']}").json()["data"]
        for _ in range(41):
            replay = client.post(
                f"/api/v1/lessons/{first['id']}/steps/{first['steps'][0]['id']}/complete",
                json={"expected_version": 0},
                headers=headers,
            )
            assert replay.status_code == 200
        limited = client.post(
            f"/api/v1/lessons/{first['id']}/steps/{first['steps'][0]['id']}/complete",
            json={"expected_version": 0},
            headers=headers,
        )
        assert limited.status_code == 429
        questions = client.get(base + "/written-questions").json()["data"]
        assert len(questions) == 10
        payload = {
            "answers": [
                {"question_id": question["id"], "answer": "หลักฐานมีข้อจำกัด ต้องตรวจผลตอบกลับและบริบท"}
                for question in questions
            ]
        }
        key = str(uuid4())
        post_headers = headers | {"Idempotency-Key": key}
        result = client.post(base + "/written-submissions", json=payload, headers=post_headers)
        assert result.status_code == 201, result.text
        assert result.json()["data"]["status"] == "needs_review"
        assert "score" not in result.json()["data"]
        replay = client.post(base + "/written-submissions", json=payload, headers=post_headers)
        assert replay.json()["data"] == result.json()["data"]
        duplicate = {"answers": [payload["answers"][0]] * 10}
        assert (
            client.post(
                base + "/written-submissions",
                json=duplicate,
                headers=headers | {"Idempotency-Key": str(uuid4())},
            ).status_code
            == 422
        )
        assert len(client.get(base + "/written-submissions").json()["data"]) == 1
        demo = client.get("/api/v1/demo/events")
        assert demo.status_code == 200 and len(demo.json()["data"]) == 2
        client.cookies.set(auth.SESSION, tokens[1])
        assert client.get(base + "/written-submissions").json()["data"] == []

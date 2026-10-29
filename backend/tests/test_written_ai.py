import asyncio
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_database_training import configure, prepare
from test_dify_workflow import hashes, outputs

from app.auth import service as auth
from app.db.session import Database
from app.grading.written_ai import validate_feedback
from app.knowledge.dify_workflow import WorkflowReply
from app.main import app
from app.worker.jobs import process_one


def result_for(snapshot):
    return {
        "items": [
            {
                "question_id": item["id"],
                "verdict": "insufficient",
                "explanation": "ยังไม่มีหลักฐานยืนยันผลตาม SOC-003",
                "section_ids": ["SOC-003"],
            }
            for item in snapshot
        ]
    }


def test_grade_feedback_requires_frozen_ids_and_approved_sources():
    snapshot = [{"id": str(uuid4())} for _ in range(10)]
    submission = {"question_snapshot": snapshot}
    policy = {"document_ids": ["approved-document"], "chunk_hashes": hashes()}
    payload = {"answer": json.dumps(result_for(snapshot)), "sources": outputs()["sources"]}
    valid = validate_feedback(payload, submission, policy)
    assert len(valid.items) == 10 and valid.sources[0].section_ids == ["SOC-003"]
    for invalid in (
        payload | {"sources": []},
        payload | {"answer": json.dumps({"items": result_for(snapshot)["items"][:-1]})},
        payload | {"answer": json.dumps({"items": result_for(snapshot)["items"], "score": 10})},
        payload
        | {
            "answer": json.dumps(
                {"items": result_for(snapshot)["items"][:-1] + [result_for(snapshot)["items"][0]]}
            )
        },
    ):
        with pytest.raises(ValueError):
            validate_feedback(invalid, submission, policy)
    with pytest.raises(ValueError):
        validate_feedback(payload, submission, policy | {"chunk_hashes": ["x" * 64]})


async def setup(migrated, users):
    db = Database(migrated("migration_owner"))
    submission_id = uuid4()
    try:
        async with db.sessions() as session, session.begin():
            level = await session.scalar(
                text("SELECT id FROM app.learning_levels ORDER BY ordinal LIMIT 1")
            )
            questions = (
                (
                    await session.execute(
                        text(
                            "SELECT id,ordinal,version,prompt,category FROM app.written_questions "
                            "WHERE level_id=:level ORDER BY ordinal"
                        ),
                        {"level": level},
                    )
                )
                .mappings()
                .all()
            )
            snapshot = [dict(item) | {"id": str(item["id"])} for item in questions]
            answers = [
                {"question_id": item["id"], "answer": "ควรตรวจหลักฐานเพิ่มเติม"} for item in snapshot
            ]
            await session.execute(
                text("""INSERT INTO app.written_submissions
                (id,owner_user_id,level_id,idempotency_key,request_hash,answers_json,question_snapshot)
                VALUES(:id,:owner,:level,:key,:hash,
                  CAST(:answers AS jsonb),CAST(:snapshot AS jsonb))"""),
                {
                    "id": submission_id,
                    "owner": users[0],
                    "level": level,
                    "key": uuid4(),
                    "hash": "a" * 64,
                    "answers": json.dumps(answers),
                    "snapshot": json.dumps(snapshot),
                },
            )
            for user in users:
                await session.execute(
                    text("""INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests)
                    VALUES(:user,10,20) ON CONFLICT(user_id) DO NOTHING"""),
                    {"user": user},
                )
            await session.execute(
                text("""UPDATE app.tutor_policy SET enabled=true,grade_enabled=true,
                cost_bound_verified=true,grade_call_bound_usd=0.01,
                workflow_id='grade-test',corpus_revision='test',
                document_ids='["approved-document"]'::jsonb,
                chunk_hashes=CAST(:hashes AS jsonb) WHERE id=1"""),
                {"hashes": json.dumps(hashes())},
            )
        return level, submission_id, snapshot
    finally:
        await db.close()


@pytest.mark.integration
def test_written_grade_uses_same_dify_workflow_after_submit_and_never_unlocks(
    migrated, monkeypatch, tmp_path
):
    users, tokens, _, _ = asyncio.run(prepare(migrated))
    configure(monkeypatch, migrated)
    secret = tmp_path / "fake-dify-key"
    secret.write_text("fake-key", encoding="utf8")
    monkeypatch.setenv("DIFY_APP_KEY_FILE", str(secret))
    level, submission_id, snapshot = asyncio.run(setup(migrated, users))
    calls = []

    async def fake(config, workflow_id, question, user, *, mode):
        calls.append((workflow_id, mode, question))
        assert mode == "grade" and workflow_id == "grade-test"
        assert len(json.loads(question)["questions"]) == 10
        return WorkflowReply(
            {"answer": json.dumps(result_for(snapshot)), "sources": outputs()["sources"]},
            100,
            "run",
        )

    monkeypatch.setattr("app.grading.written_ai.run_workflow", fake)
    path = f"/api/v1/learning/levels/{level}/written-submissions/{submission_id}/feedback"
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        headers = {"X-CSRF-Token": auth.csrf(tokens[0])}
        assert client.get(path).status_code == 404
        assert client.post(path, json={"role": "instructor"}, headers=headers).status_code == 422
        first = client.post(path, json={}, headers=headers)
        assert first.status_code == 202, first.text
        assert first.json()["data"]["status"] == "queued"
        assert client.post(path, json={}, headers=headers).status_code == 202
        client.cookies.set(auth.SESSION, tokens[1])
        assert client.get(path).status_code == 404
        assert (
            client.post(path, json={}, headers={"X-CSRF-Token": auth.csrf(tokens[1])}).status_code
            == 404
        )
        client.cookies.set(auth.SESSION, tokens[0])

        async def work():
            db = Database(migrated("worker_runtime"))
            try:
                assert await process_one(db, "written-feedback-test")
            finally:
                await db.close()

        asyncio.run(work())
        assert len(calls) == 1
        result = client.get(path)
        assert result.status_code == 200, result.text
        assert result.json()["data"]["status"] == "succeeded"
        assert len(result.json()["data"]["result"]["items"]) == 10
        assert "score" not in result.text and "passed" not in result.text
        assert client.post(path, json={}, headers=headers).status_code == 202
        assert len(calls) == 1

    async def verify():
        db = Database(migrated("migration_owner"))
        try:
            async with db.sessions() as session:
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.level_unlocks WHERE user_id=:owner"),
                        {"owner": users[0]},
                    )
                    == 0
                )
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.jobs WHERE type='written_feedback'")
                    )
                    == 1
                )
        finally:
            await db.close()

    asyncio.run(verify())

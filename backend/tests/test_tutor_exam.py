import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_database_training import configure
from test_exam_integration import prepare_exam
from test_tutor import setup

from app.auth import service as auth
from app.db.session import Database
from app.learning.catalog import LEVEL_ID
from app.main import app
from app.tutor.worker import process_question
from app.worker.jobs import claim


@pytest.mark.integration
def test_exam_start_blocks_new_questions_history_and_previously_queued_dispatch(
    migrated, monkeypatch, tmp_path
):
    users, tokens = asyncio.run(prepare_exam(migrated))
    configure(monkeypatch, migrated)
    secret = tmp_path / "fake-key"
    secret.write_text("fake-key-never-sent", encoding="utf8")
    monkeypatch.setenv("DIFY_APP_KEY_FILE", str(secret))
    lesson = asyncio.run(setup(migrated, users[:2]))

    async def forbidden(*args):
        pytest.fail("AI must not dispatch during an exam")

    monkeypatch.setattr("app.tutor.worker.run_workflow", forbidden)
    headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.csrf(tokens[0])}
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        payload = {"lesson_id": str(lesson), "question": "HTTP request คืออะไร"}
        created = client.post(
            "/api/v1/tutor/questions",
            json=payload,
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert created.status_code == 202
        started = client.post(
            f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
            json={"expected_progress_version": 1},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert started.status_code == 201, started.text
        assert (
            client.get("/api/v1/tutor/availability").json()["data"]["reason"]
            == "EXAM_ATTEMPT_ACTIVE"
        )
        assert client.get("/api/v1/tutor/questions").status_code == 409
        assert (
            client.post(
                "/api/v1/tutor/questions",
                json=payload,
                headers=headers | {"Idempotency-Key": str(uuid4())},
            ).status_code
            == 409
        )

        async def work():
            db = Database(migrated("worker_runtime"))
            try:
                # Tutor was queued before the exam's release job.
                job = await claim(db, "exam-race-test")
                assert job["type"] == "tutor_question"
                await process_question(db, job)
            finally:
                await db.close()

        asyncio.run(work())

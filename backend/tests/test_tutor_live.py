"""Explicit opt-in smoke: disposable local-auth DB plus the real Dify workflow."""

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_database_training import configure, prepare

from app.auth import service as auth
from app.db.session import Database
from app.main import app
from app.tutor.release import activate
from app.tutor.worker import process_question
from app.worker.jobs import claim, settle


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("SOC_DIFY_LIVE_SMOKE") != "yes", reason="Explicit live opt-in required"
)
def test_real_dify_through_auth_api_database_and_worker(migrated, monkeypatch):
    users, tokens, _, _ = asyncio.run(prepare(migrated))
    configure(monkeypatch, migrated)
    review = json.loads(Path(os.environ["SOC_DIFY_REVIEW_FILE"]).read_text())

    async def enable():
        database = Database(migrated("migration_owner"))
        try:
            async with database.sessions() as session, session.begin():
                for user in users:
                    await session.execute(
                        text("""INSERT INTO app.user_quotas
                        (user_id,daily_runs,daily_ai_requests) VALUES(:user,10,20)"""),
                        {"user": user},
                    )
            await activate(database, review, 1)
            async with database.sessions() as session:
                return await session.scalar(text("SELECT id FROM app.lessons ORDER BY id LIMIT 1"))
        finally:
            await database.close()

    lesson = asyncio.run(enable())
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION, tokens[0])
        assert client.get("/api/v1/tutor/availability").json()["data"]["available"]
        for question, expected in (
            ("HTTP 403 ยืนยันว่าข้อมูลถูกขโมยสำเร็จไหม อ้างหัวข้อคู่มือ", "succeeded"),
            ("zzqv_no_match_938274", "unavailable"),
        ):
            headers = {
                "Origin": "http://testserver",
                "X-CSRF-Token": auth.csrf(tokens[0]),
                "Idempotency-Key": str(uuid4()),
            }
            payload = {"lesson_id": str(lesson), "question": question}
            response = client.post("/api/v1/tutor/questions", json=payload, headers=headers)
            assert response.status_code == 202
            identity = response.json()["data"]["id"]
            assert (
                client.post("/api/v1/tutor/questions", json=payload, headers=headers).json()[
                    "data"
                ]["id"]
                == identity
            )

            async def work():
                database = Database(migrated("worker_runtime"))
                try:
                    job = await claim(database, "explicit-live-tutor-smoke")
                    assert job["type"] == "tutor_question"
                    await process_question(database, job)
                    assert await settle(database, job)
                finally:
                    await database.close()

            asyncio.run(work())
            view = client.get(f"/api/v1/tutor/questions/{identity}").json()["data"]
            assert view["status"] == expected, view["error_code"]
            if expected == "succeeded":
                assert view["result"]["sources"]
                assert "<think>" not in view["result"]["answer"]
            else:
                assert view["error_code"] == "DIFY_NO_MATCH"
                assert view["result"] is None
        assert len(client.get("/api/v1/tutor/questions").json()["data"]) == 2
        client.cookies.set(auth.SESSION, tokens[1])
        assert client.get(f"/api/v1/tutor/questions/{identity}").status_code == 404

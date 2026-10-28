"""Nine independent practical exams exercise earned unlocks across all three levels."""

import asyncio
import json
from collections import Counter
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import service as auth
from app.db.session import Database
from app.exams.seed import ROOT, load_bank, seed_all_levels
from app.learning.seed_full import seed as seed_full
from app.main import app
from app.worker.jobs import process_one
from tests.test_exam_integration import prepare_exam


def test_three_level_banks_are_disjoint_from_training_and_each_other():
    banks = [
        load_bank(ROOT),
        load_bank(ROOT.parent / "exam-middle"),
        load_bank(ROOT.parent / "exam-advanced"),
    ]
    assert [len(bank) for bank in banks] == [3, 3, 3]
    cases = [case for bank in banks for case, _, _ in bank]
    assert len({case.id for case in cases}) == 9
    assert Counter(case.difficulty for case in cases) == {
        "beginner": 3,
        "intermediate": 3,
        "advanced": 3,
    }
    for bank in banks:
        for case, fixture, truth in bank:
            assert fixture.purpose == case.purpose == "exam"
            assert set(truth.expected_evidence_keys) <= {event.key for event in fixture.events}
            assert "expected_severity" not in fixture.model_dump_json()
            assert not any(event.asset_id.startswith("TRAIN-") for event in fixture.events)


@pytest.mark.integration
def test_all_levels_require_lessons_and_earned_unlocks_and_can_finish_with_assigned_review(
    migrated, monkeypatch
):
    users, tokens = asyncio.run(prepare_exam(migrated))
    analyst = users[0]
    learner_token, instructor_token = tokens[0], tokens[2]
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")

    async def setup():
        owner = Database(migrated("migration_owner"))
        try:
            await seed_full(owner)
            await seed_all_levels(owner)
            await seed_all_levels(owner)
            async with owner.sessions() as session:
                return (
                    (
                        await session.execute(
                            text("SELECT id FROM app.learning_levels ORDER BY ordinal")
                        )
                    )
                    .scalars()
                    .all()
                )
        finally:
            await owner.close()

    levels = asyncio.run(setup())

    async def study(level):
        # Fixture precondition only; ordered lesson saves are tested through real API elsewhere.
        owner = Database(migrated("migration_owner"))
        try:
            async with owner.sessions() as session, session.begin():
                lessons = (
                    (
                        await session.execute(
                            text("SELECT id,content_json FROM app.lessons WHERE level_id=:level"),
                            {"level": level},
                        )
                    )
                    .mappings()
                    .all()
                )
                for lesson in lessons:
                    await session.execute(
                        text("""INSERT INTO app.user_lesson_progress
                        (user_id,lesson_id,lesson_version,completed_steps,completed_at,version)
                        VALUES (:user,:lesson,1,CAST(:steps AS jsonb),now(),1)
                        ON CONFLICT(user_id,lesson_id) DO NOTHING"""),
                        {
                            "user": analyst,
                            "lesson": lesson["id"],
                            "steps": json.dumps(
                                [step["id"] for step in lesson["content_json"]["steps"]]
                            ),
                        },
                    )
        finally:
            await owner.close()

    async def release_and_answer(run_id, attempt_id):
        owner, worker = Database(migrated("migration_owner")), Database(migrated("worker_runtime"))
        try:
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("UPDATE app.runs SET resumed_at=now()-interval '60 seconds' WHERE id=:id"),
                    {"id": run_id},
                )
            for index in range(4):
                await process_one(worker, f"three-level-worker-{index}")
            async with owner.sessions() as session:
                truth = (
                    (
                        await session.execute(
                            text("""SELECT t.expected_evidence_keys,
                                t.expected_severity,t.expected_disposition
                    FROM app.exam_attempts a JOIN private.exam_case_truths t ON t.case_id=a.case_id
                    WHERE a.id=:id"""),
                            {"id": attempt_id},
                        )
                    )
                    .mappings()
                    .one()
                )
                events = (
                    await session.execute(
                        text("SELECT id,fixture_event_key FROM app.events WHERE run_id=:id"),
                        {"id": run_id},
                    )
                ).all()
                return {
                    "evidence_event_ids": [
                        str(row[0]) for row in events if row[1] in truth["expected_evidence_keys"]
                    ],
                    "severity": truth["expected_severity"],
                    "disposition": truth["expected_disposition"],
                }
        finally:
            await owner.close()
            await worker.close()

    with TestClient(app, headers={"Origin": "http://testserver"}) as learner:
        learner.cookies.set(auth.SESSION, learner_token)
        locked = learner.post(
            f"/api/v1/learning/levels/{levels[1]}/attempts",
            json={"expected_progress_version": 1},
            headers={"X-CSRF-Token": auth.csrf(learner_token), "Idempotency-Key": str(uuid4())},
        )
        assert locked.status_code == 404
    for level in levels:
        asyncio.run(study(level))
        for case_number in range(3):
            with TestClient(app, headers={"Origin": "http://testserver"}) as learner:
                learner.cookies.set(auth.SESSION, learner_token)
                started = learner.post(
                    f"/api/v1/learning/levels/{level}/attempts",
                    json={"expected_progress_version": 1},
                    headers={
                        "X-CSRF-Token": auth.csrf(learner_token),
                        "Idempotency-Key": str(uuid4()),
                    },
                )
                assert started.status_code == 201, started.text
                attempt = started.json()["data"]
                answer = asyncio.run(
                    release_and_answer(UUID(attempt["run_id"]), UUID(attempt["id"]))
                )
                submitted = learner.post(
                    f"/api/v1/exam/attempts/{attempt['id']}/submit",
                    json={**answer, "expected_version": 1, "reason": "อ้างอิงหลักฐานที่ส่งพร้อมระบุข้อจำกัด"},
                    headers={
                        "X-CSRF-Token": auth.csrf(learner_token),
                        "Idempotency-Key": str(uuid4()),
                    },
                )
                assert submitted.status_code == 200, submitted.text
                assert submitted.json()["data"]["status"] == "needs_review"
            with TestClient(app, headers={"Origin": "http://testserver"}) as reviewer:
                reviewer.cookies.set(auth.SESSION, instructor_token)
                reviewed = reviewer.post(
                    f"/api/v1/admin/exam-attempts/{attempt['id']}/review",
                    json={
                        "expected_version": 2,
                        "criterion_scores": {"analysis": 2, "reasoning": 2},
                        "reason": "Assigned instructor verified evidence and reasoning.",
                    },
                    headers={"X-CSRF-Token": auth.csrf(instructor_token)},
                )
                assert reviewed.status_code == 200, reviewed.text
                assert reviewed.json()["data"]["status"] == "passed"
            with TestClient(app) as learner:
                learner.cookies.set(auth.SESSION, learner_token)
                statuses = learner.get("/api/v1/me/learning-path").json()["data"]["level_statuses"]
                current = next(item for item in statuses if item["level_id"] == str(level))
                assert current["passed_case_count"] == case_number + 1
                assert current["exam_case_count"] == 3
                assert current["all_lessons_completed"] and current["unlocked"]
                learner.cookies.set(auth.SESSION, tokens[1])
                others = learner.get("/api/v1/me/learning-path").json()["data"]["level_statuses"]
                assert all(item["passed_case_count"] == 0 for item in others)

    async def verify():
        owner = Database(migrated("migration_owner"))
        try:
            async with owner.sessions() as session:
                assert (
                    await session.scalar(
                        text(
                            "SELECT count(*) FROM app.exam_attempts "
                            "WHERE owner_user_id=:user AND status='passed'"
                        ),
                        {"user": analyst},
                    )
                    == 9
                )
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.level_unlocks WHERE user_id=:user"),
                        {"user": analyst},
                    )
                    == 2
                )
        finally:
            await owner.close()

    asyncio.run(verify())

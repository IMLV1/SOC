"""PostgreSQL acceptance for the blind exam lifecycle and assignment boundary."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import service as auth
from app.db.session import Database
from app.exams.seed import seed as seed_exam
from app.learning.catalog import LESSON, LESSON_ID, LEVEL_ID
from app.learning.seed import seed as seed_learning
from app.main import app
from app.scenarios.seed import seed as seed_scenarios
from app.worker.jobs import process_one


async def prepare_exam(pg):
    owner = Database(pg("migration_owner"))
    analyst, other, instructor, unassigned = (uuid4() for _ in range(4))
    analyst_token, other_token, instructor_token, unassigned_token = (
        str(uuid4()) for _ in range(4)
    )
    try:
        await seed_scenarios(owner)
        await seed_learning(owner)
        await seed_exam(owner)
        async with owner.sessions() as session, session.begin():
            # The catalog currently publishes only the starter level. Add the
            # next enabled level as test state so this verifies the unlock
            # transition without inventing production lesson content.
            await session.execute(
                text("""INSERT INTO app.learning_levels(id,ordinal,title,version)
                   VALUES ('15000000-0000-4000-8000-000000000002',2,'ต่อยอด',1)""")
            )
            for user_id, role, label in (
                (analyst, "analyst", "exam-analyst"),
                (other, "analyst", "exam-other"),
                (instructor, "instructor", "exam-instructor"),
                (unassigned, "instructor", "exam-unassigned"),
            ):
                await session.execute(
                    text("""INSERT INTO app.users
                       (id,normalized_email,display_name,password_hash,role,status)
                       VALUES (:id,:email,:name,'$argon2id$fixture',:role,'active')"""),
                    {
                        "id": user_id,
                        "email": f"{user_id}@example.test",
                        "name": label,
                        "role": role,
                    },
                )
                if role == "analyst":
                    await session.execute(
                        text(
                            "INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests) "
                            "VALUES (:id,10,20)"
                        ),
                        {"id": user_id},
                    )
            await session.execute(
                text("""INSERT INTO app.user_lesson_progress
                   (user_id,lesson_id,lesson_version,completed_steps,completed_at,version)
                   VALUES (:user,:lesson,1,CAST(:steps AS jsonb),clock_timestamp(),1)"""),
                {
                    "user": analyst,
                    "lesson": LESSON_ID,
                    "steps": json.dumps([s["id"] for s in LESSON["steps"]]),
                },
            )
            await session.execute(
                text("""INSERT INTO app.instructor_assignments
                   (instructor_user_id,analyst_user_id) VALUES (:instructor,:analyst)"""),
                {"instructor": instructor, "analyst": analyst},
            )
            for user_id, token in (
                (analyst, analyst_token),
                (other, other_token),
                (instructor, instructor_token),
                (unassigned, unassigned_token),
            ):
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
    return (analyst, other, instructor, unassigned), (
        analyst_token,
        other_token,
        instructor_token,
        unassigned_token,
    )


@pytest.mark.integration
def test_exam_start_freeze_replay_owner_boundary_and_assigned_review(migrated, monkeypatch):
    async def process_releases(run_id):
        owner = Database(migrated("migration_owner"))
        worker = Database(migrated("worker_runtime"))
        try:
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("""UPDATE app.runs SET resumed_at=clock_timestamp()-interval '60 seconds'
                       WHERE id=:run AND mode='exam'"""),
                    {"run": run_id},
                )
            for index in range(4):
                if not await process_one(worker, f"exam-test-worker-{index}"):
                    break
        finally:
            await owner.close()
            await worker.close()

    async def truth_evidence(attempt_id):
        owner = Database(migrated("migration_owner"))
        try:
            async with owner.sessions() as session:
                row = (
                    (
                        await session.execute(
                            text("""SELECT t.expected_evidence_keys,t.expected_severity,
                                  t.expected_disposition,a.run_id
                           FROM app.exam_attempts a JOIN private.exam_case_truths t
                             ON t.case_id=a.case_id
                           WHERE a.id=:attempt ORDER BY t.version DESC LIMIT 1"""),
                            {"attempt": attempt_id},
                        )
                    )
                    .mappings()
                    .one()
                )
                events = (
                    (
                        await session.execute(
                            text(
                                """SELECT id,fixture_event_key FROM app.events WHERE run_id=:run"""
                            ),
                            {"run": row["run_id"]},
                        )
                    )
                    .mappings()
                    .all()
                )
            keys = set(row["expected_evidence_keys"])
            evidence_ids = [
                str(event["id"]) for event in events if event["fixture_event_key"] in keys
            ]
            return (
                evidence_ids,
                row["expected_severity"],
                row["expected_disposition"],
            )
        finally:
            await owner.close()

    users, tokens = asyncio.run(prepare_exam(migrated))
    analyst, other, instructor, unassigned = users
    analyst_token, other_token, instructor_token, unassigned_token = tokens
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with TestClient(app, headers={"Origin": "http://testserver"}) as learner:
        learner.cookies.set(auth.SESSION, analyst_token)
        idempotency_key = str(uuid4())
        started = learner.post(
            f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
            json={"expected_progress_version": 1},
            headers={"X-CSRF-Token": auth.csrf(analyst_token), "Idempotency-Key": idempotency_key},
        )
        assert started.status_code == 201, started.text
        attempt = started.json()["data"]
        attempt_id = UUID(attempt["id"])
        assert "case_id" not in attempt and "private_truth" not in attempt
        replay = learner.post(
            f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
            json={"expected_progress_version": 1},
            headers={"X-CSRF-Token": auth.csrf(analyst_token), "Idempotency-Key": idempotency_key},
        )
        assert replay.status_code == 201 and replay.json()["data"]["id"] == attempt["id"]
        asyncio.run(process_releases(UUID(attempt["run_id"])))
        view = learner.get(f"/api/v1/exam/attempts/{attempt_id}")
        assert view.status_code == 200 and view.json()["data"]["events"]
        assert "private_truth" not in view.text and "expectedEvidenceKeys" not in view.text
        evidence, expected_severity, expected_disposition = asyncio.run(truth_evidence(attempt_id))
        csrf = auth.csrf(analyst_token)
        submit_key = str(uuid4())
        submit_path = f"/api/v1/exam/attempts/{attempt_id}/submit"
        submit_payload = {
            "expected_version": attempt["version"],
            "evidence_event_ids": evidence,
            "severity": expected_severity,
            "disposition": expected_disposition,
            "reason": "Evidence linked to a protected resource request.",
        }

        invalid_keys = []
        for change in (
            {"reason": " \t\n "},
            {"reason": "invalid\x00text"},
            {"expected_version": True},
            {"expected_version": "1"},
            {"evidence_event_ids": [evidence[0], evidence[0]]},
            {"evidence_event_ids": [str(uuid4())]},
        ):
            invalid_key = uuid4()
            invalid_keys.append(invalid_key)
            invalid = learner.post(
                submit_path,
                json=submit_payload | change,
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(invalid_key)},
            )
            assert invalid.status_code == 422, invalid.text
            assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
        unchanged = learner.get(f"/api/v1/exam/attempts/{attempt_id}").json()["data"]
        assert unchanged["status"] == "in_progress"
        assert unchanged["version"] == attempt["version"]
        assert unchanged["answer"] is None

        async def assert_no_partial_submission():
            database = Database(migrated("migration_owner"))
            try:
                async with database.sessions() as session:
                    assert (
                        await session.scalar(
                            text("SELECT count(*) FROM app.exam_answers WHERE attempt_id=:id"),
                            {"id": attempt_id},
                        )
                        == 0
                    )
                    assert (
                        await session.scalar(
                            text("SELECT count(*) FROM app.idempotency_keys WHERE key=ANY(:keys)"),
                            {"keys": invalid_keys},
                        )
                        == 0
                    )
            finally:
                await database.close()

        asyncio.run(assert_no_partial_submission())

        def post_submit():
            return learner.post(
                submit_path,
                json=submit_payload,
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": submit_key},
            )

        with ThreadPoolExecutor(2) as pool:
            submissions = list(pool.map(lambda _: post_submit(), range(2)))
        assert [response.status_code for response in submissions] == [200, 200]
        assert submissions[0].json()["data"] == submissions[1].json()["data"]
        submitted = submissions[0]
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["data"]["status"] == "needs_review"
        same_submit = learner.post(
            f"/api/v1/exam/attempts/{attempt_id}/submit",
            json={
                **submit_payload,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": submit_key},
        )
        assert same_submit.status_code == 200
        assert same_submit.json()["data"] == submitted.json()["data"]
        with TestClient(app, headers={"Origin": "http://testserver"}) as other_client:
            other_client.cookies.set(auth.SESSION, other_token)
            assert other_client.get(f"/api/v1/exam/attempts/{attempt_id}").status_code == 404
            assert other_client.get(f"/api/v1/exam/attempts/{attempt_id}/result").status_code == 404

    with TestClient(app, headers={"Origin": "http://testserver"}) as reviewer:
        reviewer.cookies.set(auth.SESSION, unassigned_token)
        assert reviewer.get(f"/api/v1/admin/exam-attempts/{attempt_id}").status_code == 404
        reviewer.cookies.set(auth.SESSION, instructor_token)
        assigned = reviewer.get(f"/api/v1/admin/exam-attempts/{attempt_id}")
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["data"]["private_truth"]["expectedEvidenceKeys"]
        review_path = f"/api/v1/admin/exam-attempts/{attempt_id}/review"
        review_payload = {
            "expected_version": 2,
            "criterion_scores": {"analysis": 2, "reasoning": 2},
            "reason": "Review confirms the answer is supported by the submitted evidence.",
        }

        def post_review():
            return reviewer.post(
                review_path,
                json=review_payload,
                headers={"X-CSRF-Token": auth.csrf(instructor_token)},
            )

        with ThreadPoolExecutor(2) as pool:
            reviews = list(pool.map(lambda _: post_review(), range(2)))
        assert sorted(response.status_code for response in reviews) == [200, 409]
        graded = next(response for response in reviews if response.status_code == 200)
        assert graded.status_code == 200, graded.text
        assert graded.json()["data"]["status"] == "passed"
        assert graded.json()["data"]["score"] == 8

    async def unlock_count():
        owner = Database(migrated("migration_owner"))
        try:
            async with owner.sessions() as session:
                return await session.scalar(
                    text("SELECT count(*) FROM app.level_unlocks WHERE user_id=:user"),
                    {"user": analyst},
                )
        finally:
            await owner.close()

    assert asyncio.run(unlock_count()) == 0

    # Passing a subset of the level's cases cannot unlock the next level.
    # Complete the remaining distinct cases; the third passing review must
    # create the level unlock once.
    for _ in range(2):
        with TestClient(app, headers={"Origin": "http://testserver"}) as learner:
            learner.cookies.set(auth.SESSION, analyst_token)
            started = learner.post(
                f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
                json={"expected_progress_version": 1},
                headers={
                    "X-CSRF-Token": auth.csrf(analyst_token),
                    "Idempotency-Key": str(uuid4()),
                },
            )
            assert started.status_code == 201, started.text
            attempt_data = started.json()["data"]
            current_attempt = UUID(attempt_data["id"])
            asyncio.run(process_releases(UUID(attempt_data["run_id"])))
            evidence, severity, disposition = asyncio.run(truth_evidence(current_attempt))
            submitted = learner.post(
                f"/api/v1/exam/attempts/{current_attempt}/submit",
                json={
                    "expected_version": attempt_data["version"],
                    "evidence_event_ids": evidence,
                    "severity": severity,
                    "disposition": disposition,
                    "reason": "The released events support this classification.",
                },
                headers={
                    "X-CSRF-Token": auth.csrf(analyst_token),
                    "Idempotency-Key": str(uuid4()),
                },
            )
            assert submitted.status_code == 200, submitted.text
            assert submitted.json()["data"]["status"] == "needs_review"

        with TestClient(app, headers={"Origin": "http://testserver"}) as reviewer:
            reviewer.cookies.set(auth.SESSION, instructor_token)
            result = reviewer.post(
                f"/api/v1/admin/exam-attempts/{current_attempt}/review",
                json={
                    "expected_version": 2,
                    "criterion_scores": {"analysis": 2, "reasoning": 2},
                    "reason": "Review confirms the answer is supported by the submitted evidence.",
                },
                headers={"X-CSRF-Token": auth.csrf(instructor_token)},
            )
            assert result.status_code == 200, result.text
            assert result.json()["data"]["status"] == "passed"

    assert asyncio.run(unlock_count()) == 1

    # Instructor overrides append a new grading revision and do not revoke an
    # unlock that was already earned from the earlier passed revisions.
    with TestClient(app, headers={"Origin": "http://testserver"}) as reviewer:
        reviewer.cookies.set(auth.SESSION, instructor_token)
        overridden = reviewer.post(
            f"/api/v1/admin/exam-attempts/{attempt_id}/review",
            json={
                "expected_version": 3,
                "criterion_scores": {"analysis": 0, "reasoning": 0},
                "reason": "Override after review found the analysis criterion was unsupported.",
            },
            headers={"X-CSRF-Token": auth.csrf(instructor_token)},
        )
        assert overridden.status_code == 200, overridden.text
        assert overridden.json()["data"]["status"] == "failed"

    async def history_and_unlock():
        owner = Database(migrated("migration_owner"))
        try:
            async with owner.sessions() as session:
                revisions = await session.scalar(
                    text("SELECT count(*) FROM app.grading_revisions WHERE attempt_id=:attempt"),
                    {"attempt": attempt_id},
                )
                unlocks = await session.scalar(
                    text("SELECT count(*) FROM app.level_unlocks WHERE user_id=:user"),
                    {"user": analyst},
                )
                return revisions, unlocks
        finally:
            await owner.close()

    assert asyncio.run(history_and_unlock()) == (2, 1)


@pytest.mark.integration
def test_learning_progress_persists_across_refresh_and_is_owner_scoped(migrated, monkeypatch):
    async def prepare_users():
        owner = Database(migrated("migration_owner"))
        learner, other = uuid4(), uuid4()
        learner_token, other_token = str(uuid4()), str(uuid4())
        try:
            await seed_learning(owner)
            await seed_exam(owner)
            async with owner.sessions() as session, session.begin():
                for user_id, token, label in (
                    (learner, learner_token, "learning-learner"),
                    (other, other_token, "learning-other"),
                ):
                    await session.execute(
                        text("""INSERT INTO app.users
                           (id,normalized_email,display_name,password_hash,role,status)
                           VALUES (:id,:email,:name,'$argon2id$fixture','analyst','active')"""),
                        {"id": user_id, "email": f"{user_id}@example.test", "name": label},
                    )
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
        return (learner_token, other_token)

    learner_token, other_token = asyncio.run(prepare_users())
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    lesson_url = f"/api/v1/lessons/{LESSON_ID}"
    path_url = "/api/v1/me/learning-path"
    steps = [item["id"] for item in LESSON["steps"]]

    with TestClient(app, headers={"Origin": "http://testserver"}) as guest:
        assert guest.get(lesson_url).status_code == 401
        assert guest.get("/api/v1/learning-path").status_code == 200

    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, learner_token)
        assert client.get(lesson_url).status_code == 200
        assert client.get(path_url).json()["data"]["lessons"] == []
        blocked_exam = client.post(
            f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
            json={"expected_progress_version": 1},
            headers={
                "X-CSRF-Token": auth.csrf(learner_token),
                "Idempotency-Key": str(uuid4()),
            },
        )
        assert blocked_exam.status_code == 409
        completed = client.post(
            f"/api/v1/lessons/{LESSON_ID}/steps/{steps[0]}/complete",
            json={"expected_version": 0},
            headers={"X-CSRF-Token": auth.csrf(learner_token)},
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["data"]["completed_steps"] == [steps[0]]
        assert completed.json()["data"]["version"] == 1

    # A fresh client models a browser refresh/new session reading server state.
    with TestClient(app, headers={"Origin": "http://testserver"}) as refreshed:
        refreshed.cookies.set(auth.SESSION, learner_token)
        saved = refreshed.get(path_url)
        assert saved.status_code == 200
        assert saved.json()["data"]["lessons"][0]["completed_steps"] == [steps[0]]
        assert saved.json()["data"]["lessons"][0]["version"] == 1
        stale = refreshed.post(
            f"/api/v1/lessons/{LESSON_ID}/steps/{steps[1]}/complete",
            json={"expected_version": 0},
            headers={"X-CSRF-Token": auth.csrf(learner_token)},
        )
        assert stale.status_code == 409
        with TestClient(app, headers={"Origin": "http://testserver"}) as another_user:
            another_user.cookies.set(auth.SESSION, other_token)
            assert another_user.get(path_url).json()["data"]["lessons"] == []


@pytest.mark.integration
def test_retake_rotates_cases_and_caps_three_attempts_per_case(migrated, monkeypatch):
    users, tokens = asyncio.run(prepare_exam(migrated))
    analyst, analyst_token = users[0], tokens[0]
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    started_case_ids = []

    async def fail_attempt(attempt_id):
        database = Database(migrated("migration_owner"))
        try:
            async with database.sessions() as session, session.begin():
                await session.execute(
                    text("""UPDATE app.exam_attempts SET status='failed',
                       started_at=clock_timestamp()-interval '2 hours',
                       submitted_at=clock_timestamp()-interval '2 hours',
                       finalized_at=clock_timestamp()-interval '2 hours'
                       WHERE id=:attempt AND owner_user_id=:owner"""),
                    {"attempt": attempt_id, "owner": analyst},
                )
                await session.execute(
                    text("""UPDATE app.runs SET status='failed',resumed_at=NULL,
                       failure_code='EXAM_TEST_FAILED' WHERE id=(
                         SELECT run_id FROM app.exam_attempts WHERE id=:attempt)"""),
                    {"attempt": attempt_id},
                )
                return await session.scalar(
                    text("SELECT case_id FROM app.exam_attempts WHERE id=:attempt"),
                    {"attempt": attempt_id},
                )
        finally:
            await database.close()

    with TestClient(app, headers={"Origin": "http://testserver"}) as learner:
        learner.cookies.set(auth.SESSION, analyst_token)
        headers = {"X-CSRF-Token": auth.csrf(analyst_token)}
        for _ in range(9):
            response = learner.post(
                f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
                json={"expected_progress_version": 1},
                headers={**headers, "Idempotency-Key": str(uuid4())},
            )
            assert response.status_code == 201, response.text
            case_id = asyncio.run(fail_attempt(UUID(response.json()["data"]["id"])))
            started_case_ids.append(str(case_id))
        assert len(set(started_case_ids)) == 3
        capped = learner.post(
            f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
            json={"expected_progress_version": 1},
            headers={**headers, "Idempotency-Key": str(uuid4())},
        )
        assert capped.status_code == 429
        assert capped.json()["error"]["code"] == "EXAM_ATTEMPT_QUOTA_EXCEEDED"

        latest = learner.get("/api/v1/exam/attempts/latest/result")
        assert latest.status_code == 200, latest.text
        assert latest.json()["data"]["status"] == "failed"
        assert latest.json()["data"]["attempt_id"] == response.json()["data"]["id"]
        with TestClient(app, headers={"Origin": "http://testserver"}) as another:
            another.cookies.set(auth.SESSION, tokens[1])
            assert another.get("/api/v1/exam/attempts/latest/result").status_code == 404


@pytest.mark.integration
def test_concurrent_retake_start_creates_only_one_active_attempt(migrated, monkeypatch):
    users, tokens = asyncio.run(prepare_exam(migrated))
    analyst = users[0]
    analyst_token = tokens[0]
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")

    with TestClient(app, headers={"Origin": "http://testserver"}) as learner:
        learner.cookies.set(auth.SESSION, analyst_token)
        csrf = auth.csrf(analyst_token)

        # Establish a genuine retake state: a previous attempt has failed and
        # the policy cooldown has elapsed before the two new starts race.
        first = learner.post(
            f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
            json={"expected_progress_version": 1},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())},
        )
        assert first.status_code == 201, first.text

        async def expire_cooldown():
            database = Database(migrated("migration_owner"))
            try:
                async with database.sessions() as session, session.begin():
                    await session.execute(
                        text("""UPDATE app.exam_attempts SET status='failed',
                           submitted_at=clock_timestamp()-interval '2 hours',
                           finalized_at=clock_timestamp()-interval '2 hours'
                           WHERE id=:attempt AND owner_user_id=:owner"""),
                        {"attempt": first.json()["data"]["id"], "owner": analyst},
                    )
                    await session.execute(
                        text("""UPDATE app.runs SET status='failed',resumed_at=NULL,
                           failure_code='EXAM_TEST_FAILED' WHERE id=:run"""),
                        {"run": first.json()["data"]["run_id"]},
                    )
            finally:
                await database.close()

        asyncio.run(expire_cooldown())
        latest = learner.get("/api/v1/exam/attempts/latest/result")
        assert latest.status_code == 200
        assert latest.json()["data"]["status"] == "failed"

        def start(key):
            return learner.post(
                f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
                json={"expected_progress_version": 1},
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(key)},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(start, (uuid4(), uuid4())))

        assert sorted(response.status_code for response in responses) == [201, 409]
        conflict = next(response for response in responses if response.status_code == 409)
        assert conflict.json()["error"]["code"] == "EXAM_ATTEMPT_ACTIVE"
        active = learner.get("/api/v1/exam/attempts/active")
        assert active.status_code == 200
        assert active.json()["data"]["status"] == "in_progress"

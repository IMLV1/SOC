import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.analysis.models import AnalysisResult
from app.analysis.provider import validate_citations
from app.analysis.service import enqueue_analysis
from app.analysis.worker import analyze_job
from app.auth import service as auth
from app.auth.service import AuthError
from app.db.session import Database
from app.detection.policy import evaluate
from app.detection.worker import detect_run
from app.investigation.models import DeleteInput, NoteCreate, NotePatch, TicketCreate, TicketPatch
from app.investigation.service import (
    create_note,
    create_ticket,
    delete_or_restore_ticket,
    mutate_note,
    patch_ticket,
)
from app.main import app
from app.runs.service import finish_run, start_run
from app.scenarios.fixtures import load_training_fixture
from app.scenarios.models import TrainingSelection
from app.scenarios.seed import FIXTURES, load_seed, seed
from app.worker.jobs import claim, process_one, settle


def fixture_rows(key):
    fixture = load_training_fixture(FIXTURES / f"events/training/{key.lower()}-v1.json")
    return [
        dict(
            id=uuid4(),
            source=item.source,
            username=item.username,
            src_ip=item.src_ip,
            response_json=item.response.model_dump(),
            log_json=item.log.model_dump(exclude_none=True),
        )
        for item in fixture.events
    ]


def test_detectors_cover_s01_to_s05_without_truth_or_success_from_blocked():
    one = evaluate(fixture_rows("S01"))
    two = evaluate(fixture_rows("S02"))
    three = evaluate(fixture_rows("S03"))
    four = evaluate(fixture_rows("S04"))
    five = evaluate(fixture_rows("S05"))
    assert any(
        item.correlation_key.startswith("auth:") and item.severity == "medium" for item in one
    )
    assert any(item.correlation_key.startswith("auth:") and item.severity == "high" for item in two)
    assert any(item.severity == "low" and "ยังไม่มีหลักฐาน" in item.explanation for item in three)
    assert any(item.severity == "low" and "อนุมัติ" in item.explanation for item in four)
    assert any(item.detector_type == "anomaly" for item in five)
    assert evaluate(fixture_rows("S02")[:1]) == []


def test_citation_must_be_inside_frozen_snapshot():
    allowed = uuid4()
    foreign = uuid4()
    base = {
        "summary": "mock",
        "hypotheses": [{"text": "test", "evidence_refs": [str(foreign)]}],
        "evidence_refs": [str(allowed)],
        "observed_impact": "unknown",
        "potential_impact": "unknown",
        "suggested_severity": {"level": "low", "reason": "test"},
        "confidence": {"level": "low", "reason": "test"},
        "unknowns": [],
        "recommended_checks": [],
    }
    with pytest.raises(ValueError):
        validate_citations(AnalysisResult.model_validate(base), {allowed})


@pytest.mark.integration
def test_mock_analysis_timeout_invalid_output_and_retry_snapshot(migrated):
    class SlowProvider:
        async def analyze(self, data):
            await asyncio.sleep(0.05)
            return {}

    class InvalidProvider:
        async def analyze(self, data):
            return {"summary": "not a structured result"}

    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
            run_id = UUID(run["id"])
            await process_one(worker, "analysis-test")
            while await process_one(worker, "analysis-test"):
                pass
            async with api.sessions() as session:
                event_id = await session.scalar(text("SELECT id FROM app.events LIMIT 1"))
            assert event_id is not None
            async with api.sessions() as session, session.begin():
                first = await enqueue_analysis(
                    session, run_id, user_id, "test:timeout", "frozen-hash", [event_id]
                )
            job = await claim(worker, "analysis-test")
            assert job is not None and job["type"] == "analyze_evidence"
            await analyze_job(worker, job, SlowProvider(), timeout=0.001)
            assert await settle(worker, job)
            async with api.sessions() as session:
                row = (
                    await session.execute(
                        text("SELECT status,error_code,version FROM app.analyses WHERE id=:id"),
                        {"id": first},
                    )
                ).one()
                assert row.status == "timed_out" and row.error_code == "PROVIDER_TIMEOUT"
                released = await session.scalar(text("""SELECT count(*) FROM app.quota_reservations
                    WHERE analysis_id=:id AND status='released'"""), {"id": first})
                assert released == 2
            async with api.sessions() as session, session.begin():
                retry = await enqueue_analysis(
                    session, run_id, user_id, "test:timeout", "frozen-hash", [event_id],
                    retry_of=first,
                )
            job = await claim(worker, "analysis-test")
            assert job is not None and job["type"] == "analyze_evidence"
            await analyze_job(worker, job, InvalidProvider())
            assert await settle(worker, job)
            async with api.sessions() as session:
                retry_row = (
                    await session.execute(text("""SELECT status,error_code,retry_of,result_json
                        FROM app.analyses WHERE id=:id"""), {"id": retry})
                ).one()
                assert retry_row.status == "invalid_output"
                assert retry_row.error_code == "INVALID_PROVIDER_OUTPUT"
                assert retry_row.retry_of == first and retry_row.result_json is None
                refs = await session.scalar(text("""SELECT count(*) FROM app.analysis_evidence
                    WHERE analysis_id=:id AND event_id=:event"""),
                    {"id": retry, "event": event_id})
                assert refs == 1
                assert await session.scalar(text("SELECT count(*) FROM app.assessments")) == 0
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())


async def prepare(pg):
    owner = Database(pg("migration_owner"))
    await seed(owner)
    user_id = uuid4()
    async with owner.sessions() as session, session.begin():
        await session.execute(
            text("""INSERT INTO app.users
            (id,normalized_email,display_name,password_hash,role,status)
            VALUES (:id,:email,'Analyst','$argon2id$fixture','analyst','active')"""),
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


async def issue_session(pg, user_id):
    token = str(uuid4())
    owner = Database(pg("migration_owner"))
    try:
        async with owner.sessions() as session, session.begin():
            await session.execute(text("""INSERT INTO app.auth_sessions
                (id,user_id,token_hash,csrf_hash,expires_at)
                VALUES (:id,:user,:token,:csrf,clock_timestamp()+interval '1 day')"""),
                {"id": uuid4(), "user": user_id, "token": auth.digest(token),
                 "csrf": auth.digest(auth.csrf(token))})
    finally:
        await owner.close()
    return token


@pytest.mark.integration
def test_http_retry_keeps_old_analysis_and_snapshot(migrated, monkeypatch):
    class InvalidProvider:
        async def analyze(self, data):
            return {"summary": "invalid"}

    async def setup():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
            run_id = UUID(run["id"])
            await process_one(worker, "http-retry")
            while await process_one(worker, "http-retry"):
                pass
            async with api.sessions() as session:
                event_id = await session.scalar(text("SELECT id FROM app.events LIMIT 1"))
            async with api.sessions() as session, session.begin():
                analysis_id = await enqueue_analysis(
                    session, run_id, user_id, "test:http-retry", "snapshot-v1", [event_id]
                )
            job = await claim(worker, "http-retry")
            assert job is not None and job["type"] == "analyze_evidence"
            await analyze_job(worker, job, InvalidProvider())
            assert await settle(worker, job)
            token = await issue_session(migrated, user_id)
            return run_id, analysis_id, event_id, token
        finally:
            await api.close()
            await worker.close()

    run_id, analysis_id, event_id, token = asyncio.run(setup())
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, token)
        detail = client.get(f"/api/v1/runs/{run_id}/analyses/{analysis_id}")
        assert detail.status_code == 200
        assert detail.json()["data"]["status"] == "invalid_output"
        key = str(uuid4())
        path = f"/api/v1/runs/{run_id}/analyses/{analysis_id}/retry"
        headers = {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"],
                   "Idempotency-Key": key}
        result = client.post(path, json={"expected_version": detail.json()["data"]["version"]},
                             headers=headers)
        assert result.status_code == 202, result.text
        new = result.json()["data"]
        assert new["retry_of"] == str(analysis_id) and new["status"] == "queued"
        assert new["evidence_ids"] == [str(event_id)]
        repeated = client.post(path, json={"expected_version": detail.json()["data"]["version"]},
                               headers=headers)
        assert repeated.status_code == 202 and repeated.json()["data"]["id"] == new["id"]
        page = client.get(f"/api/v1/runs/{run_id}/analyses", params={"limit": 1})
        assert page.status_code == 200 and page.json()["meta"]["next_cursor"]
        next_page = client.get(f"/api/v1/runs/{run_id}/analyses",
                               params={"limit": 1, "cursor": page.json()["meta"]["next_cursor"]})
        assert next_page.status_code == 200
        assert next_page.json()["data"][0]["id"] != page.json()["data"][0]["id"]
        mixed = client.get(f"/api/v1/runs/{run_id}/analyses",
                           params={"status": "succeeded",
                                   "cursor": page.json()["meta"]["next_cursor"]})
        assert mixed.status_code == 400
        old = client.get(f"/api/v1/runs/{run_id}/analyses/{analysis_id}")
        assert old.json()["data"]["status"] == "invalid_output"


@pytest.mark.integration
def test_instructor_ticket_scope_and_no_disposition_forgery(migrated, monkeypatch):
    async def setup():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        owner = Database(migrated("migration_owner"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
            run_id = UUID(run["id"])
            await process_one(worker, "instructor-test")
            async with api.sessions() as session:
                event_id = await session.scalar(text("SELECT id FROM app.events LIMIT 1"))
            async with api.sessions() as session, session.begin():
                ticket = await create_ticket(
                    session, run_id, user_id,
                    TicketCreate(title="Instructor review", severity="low",
                                 evidence_ids=[event_id], reason="manual review"),
                    uuid4(),
                )
            for number in (1, 2):
                async with api.sessions() as session, session.begin():
                    await create_note(session, run_id, ticket["id"], user_id,
                        NoteCreate(body=f"Observation {number}", evidence_ids=[event_id]),
                        uuid4())
            assigned, unrelated = uuid4(), uuid4()
            async with owner.sessions() as session, session.begin():
                for identity in (assigned, unrelated):
                    await session.execute(text("""INSERT INTO app.users
                        (id,normalized_email,display_name,password_hash,role,status)
                        VALUES (:id,:email,'Instructor','$argon2id$fixture',
                                'instructor','active')"""),
                        {"id": identity, "email": f"{identity}@example.test"})
                await session.execute(text("""INSERT INTO app.instructor_assignments
                    (instructor_user_id,analyst_user_id) VALUES (:teacher,:student)"""),
                    {"teacher": assigned, "student": user_id})
            return (run_id, ticket["id"], user_id,
                    await issue_session(migrated, user_id),
                    await issue_session(migrated, assigned),
                    await issue_session(migrated, unrelated))
        finally:
            await api.close()
            await worker.close()
            await owner.close()

    run_id, ticket_id, analyst_id, analyst_token, assigned_token, unrelated_token = (
        asyncio.run(setup())
    )
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    path = f"/api/v1/admin/runs/{run_id}/tickets/{ticket_id}"
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, analyst_token)
        tickets = client.get(f"/api/v1/runs/{run_id}/tickets",
                             params={"q": "Instructor", "severity": "low", "status": "open"})
        assert tickets.status_code == 200, tickets.text
        assert [item["id"] for item in tickets.json()["data"]] == [str(ticket_id)]
        assert tickets.json()["meta"]["next_cursor"] is None
        notes_path = f"/api/v1/runs/{run_id}/tickets/{ticket_id}/notes"
        notes_page = client.get(notes_path, params={"limit": 1})
        assert notes_page.status_code == 200, notes_page.text
        assert notes_page.json()["meta"]["next_cursor"]
        note_cursor = notes_page.json()["meta"]["next_cursor"]
        notes_next = client.get(notes_path, params={"limit": 1, "cursor": note_cursor})
        assert notes_next.status_code == 200 and len(notes_next.json()["data"]) == 1
        note_id = notes_page.json()["data"][0]["id"]
        versions = client.get(f"{notes_path}/{note_id}/versions", params={"limit": 1})
        assert versions.status_code == 200 and len(versions.json()["data"]) == 1
        timeline = client.get(f"/api/v1/runs/{run_id}/tickets/{ticket_id}/timeline",
                              params={"limit": 1})
        assert timeline.status_code == 200, timeline.text
        assert timeline.json()["data"][0]["kind"] in {"audit", "event"}
        assert timeline.json()["meta"]["next_cursor"]
        more = client.get(f"/api/v1/runs/{run_id}/tickets/{ticket_id}/timeline",
                          params={"limit": 1,
                                  "cursor": timeline.json()["meta"]["next_cursor"]})
        assert more.status_code == 200 and more.json()["data"]
        assert client.get(f"/api/v1/runs/{run_id}/tickets",
                          params={"severity": "critical"}).json()["data"] == []
        client.cookies.set(auth.SESSION, unrelated_token)
        assert client.get(path).status_code == 404
        client.cookies.set(auth.SESSION, assigned_token)
        assert client.get(path).status_code == 200
        assert client.get(f"/api/v1/runs/{run_id}/tickets/{ticket_id}").status_code == 404
        assert client.get(f"/api/v1/runs/{run_id}/tickets").status_code == 404
        csrf = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
        headers = {"X-CSRF-Token": csrf}
        raised = client.patch(path, json={"expected_version": 1, "severity": "high",
                                          "reason": "prioritize"}, headers=headers)
        assert raised.status_code == 200, raised.text
        assert raised.json()["data"]["severity"] == "high"
        investigating = client.patch(path, json={"expected_version": 2,
                                                 "status": "investigating",
                                                 "reason": "review"}, headers=headers)
        assert investigating.status_code == 200, investigating.text
        denied = client.patch(path, json={"expected_version": 3, "status": "resolved",
                                          "reason": "no learner conclusion"}, headers=headers)
        assert denied.status_code == 422
        assert denied.json()["error"]["code"] == "ASSESSMENT_REQUIRED"
    async def assess_and_finish():
        api = Database(migrated("api_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                await patch_ticket(session, run_id, ticket_id, analyst_id,
                    TicketPatch(expected_version=3, disposition="undetermined",
                                reason="need more evidence"))
        finally:
            await api.close()
    asyncio.run(assess_and_finish())
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, analyst_token)
        history = client.get(f"/api/v1/runs/{run_id}/tickets/{ticket_id}/assessments",
                             params={"limit": 1})
        assert history.status_code == 200 and history.json()["data"][0]["revision"] == 1
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, assigned_token)
        headers = {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]}
        resolved = client.patch(path, json={"expected_version": 4, "status": "resolved",
                                            "reason": "human assessment present"}, headers=headers)
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["data"]["latest_assessment"]["disposition"] == "undetermined"
    async def finish():
        api = Database(migrated("api_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                await finish_run(session, run_id, analyst_id, 1)
        finally:
            await api.close()
    asyncio.run(finish())
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, assigned_token)
        headers = {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]}
        locked = client.patch(path, json={"expected_version": 5, "severity": "low",
                                          "reason": "too late"}, headers=headers)
        assert locked.status_code == 409 and locked.json()["error"]["code"] == "RUN_READ_ONLY"


async def release_all(api, worker, run_id):
    # Explicit DB clock advance in isolated test DB only; production clock stays server-owned.
    async with worker.sessions() as session, session.begin():
        await session.execute(
            text("""UPDATE app.runs SET resumed_at=clock_timestamp()-interval '76 seconds'
            WHERE id=:run"""),
            {"run": run_id},
        )
        await session.execute(
            text("""UPDATE app.jobs SET available_at=clock_timestamp()
            WHERE run_id=:run AND type='release_events' AND status='queued'"""),
            {"run": run_id},
        )
    for _ in range(50):
        if not await process_one(worker, "integration-worker"):
            break


@pytest.mark.integration
def test_detection_is_idempotent_and_mock_never_edits_human_answer(migrated):
    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
            run_id = UUID(run["id"])
            await release_all(api, worker, run_id)
            async with api.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.events")) == 15
                assert await session.scalar(text("SELECT count(*) FROM app.alerts")) > 0
                assert await session.scalar(text("SELECT count(*) FROM app.tickets")) == 1
                assert await session.scalar(text("SELECT count(*) FROM app.analyses")) > 0
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.analyses WHERE status='succeeded'")
                    )
                    > 0
                )
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.jobs WHERE status='failed'")
                    )
                    == 0
                )
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.quota_reservations WHERE status='consumed'")
                    )
                    > 0
                )
                assert await session.scalar(text("SELECT count(*) FROM app.assessments")) == 0
                ticket_id = await session.scalar(text("SELECT id FROM app.tickets LIMIT 1"))
                before = await session.scalar(text("SELECT count(*) FROM app.detections"))
            await detect_run(worker, run_id)
            async with api.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.detections")) == before
            async with api.sessions() as session, session.begin():
                ticket = await delete_or_restore_ticket(
                    session,
                    run_id,
                    ticket_id,
                    user_id,
                    DeleteInput(expected_version=1, reason="review"),
                    False,
                )
            assert ticket["deleted_at"] is not None
            await detect_run(worker, run_id)
            async with api.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.tickets")) == 1
            # Composite run references reject cross-run evidence at the database boundary.
            async with api.sessions() as session, session.begin():
                second, _ = await start_run(session, user_id, selection, uuid4())
            second_id = UUID(second["id"])
            async with api.sessions() as session:
                foreign_event = await session.scalar(text("SELECT id FROM app.events LIMIT 1"))
            with pytest.raises(IntegrityError):
                async with api.sessions() as session, session.begin():
                    await session.execute(
                        text("""INSERT INTO app.ticket_events
                        (run_id,ticket_id,event_id) VALUES (:run,:ticket,:event)"""),
                        {"run": second_id, "ticket": ticket_id, "event": foreign_event},
                    )
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())


@pytest.mark.integration
def test_ticket_note_history_conflict_and_finish_lock(migrated):
    async def execute():
        user_id, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        try:
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user_id, selection, uuid4())
            run_id = UUID(run["id"])
            await process_one(worker, "worker")
            async with api.sessions() as session:
                event_id = await session.scalar(text("SELECT id FROM app.events LIMIT 1"))
            async with api.sessions() as session, session.begin():
                ticket = await create_ticket(
                    session,
                    run_id,
                    user_id,
                    TicketCreate(
                        title="Review evidence",
                        severity="low",
                        evidence_ids=[event_id],
                        reason="manual review",
                    ),
                    uuid4(),
                )
            ticket_id = ticket["id"]
            async with api.sessions() as session, session.begin():
                note = await create_note(
                    session,
                    run_id,
                    ticket_id,
                    user_id,
                    NoteCreate(body="First observation", evidence_ids=[event_id]),
                    uuid4(),
                )
            note_id = note["id"]
            async with api.sessions() as session, session.begin():
                changed = await mutate_note(
                    session,
                    run_id,
                    ticket_id,
                    note_id,
                    user_id,
                    "edit",
                    NotePatch(
                        expected_version=1,
                        body="Updated observation",
                        evidence_ids=[event_id],
                        reason="clarify",
                    ),
                )
            assert changed["version"] == 2
            with pytest.raises(AuthError) as wrong_owner:
                async with api.sessions() as session, session.begin():
                    await mutate_note(
                        session, run_id, ticket_id, note_id, uuid4(), "delete",
                        DeleteInput(expected_version=2, reason="not owner"),
                    )
            assert wrong_owner.value.status == 404
            with pytest.raises(AuthError) as conflict:
                async with api.sessions() as session, session.begin():
                    await mutate_note(
                        session,
                        run_id,
                        ticket_id,
                        note_id,
                        user_id,
                        "edit",
                        NotePatch(
                            expected_version=1, body="stale", evidence_ids=[], reason="stale"
                        ),
                    )
            assert conflict.value.code == "VERSION_CONFLICT"
            async with api.sessions() as session, session.begin():
                ticket = await patch_ticket(
                    session,
                    run_id,
                    ticket_id,
                    user_id,
                    TicketPatch(
                        expected_version=1,
                        status="investigating",
                        disposition="undetermined",
                        reason="need more evidence",
                    ),
                )
            assert ticket["latest_assessment"]["revision"] == 1
            async with api.sessions() as session, session.begin():
                deleted = await delete_or_restore_ticket(
                    session, run_id, ticket_id, user_id,
                    DeleteInput(expected_version=ticket["version"], reason="review parent"), False,
                )
            with pytest.raises(AuthError) as deleted_parent:
                async with api.sessions() as session, session.begin():
                    await mutate_note(
                        session, run_id, ticket_id, note_id, user_id, "delete",
                        DeleteInput(expected_version=2, reason="parent removed"),
                    )
            assert deleted_parent.value.code == "TICKET_DELETED"
            async with api.sessions() as session, session.begin():
                await delete_or_restore_ticket(
                    session, run_id, ticket_id, user_id,
                    DeleteInput(expected_version=deleted["version"], reason="restore parent"), True,
                )
            async with api.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.note_versions")) == 2
            async with api.sessions() as session, session.begin():
                await finish_run(session, run_id, user_id, 1)
            with pytest.raises(AuthError) as locked:
                async with api.sessions() as session, session.begin():
                    await mutate_note(
                        session,
                        run_id,
                        ticket_id,
                        note_id,
                        user_id,
                        "delete",
                        DeleteInput(expected_version=2, reason="late"),
                    )
            assert locked.value.code == "RUN_READ_ONLY"
        finally:
            await api.close()
            await worker.close()

    asyncio.run(execute())

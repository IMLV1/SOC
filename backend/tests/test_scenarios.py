import asyncio
import json
import os
import shutil
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.auth.service import AuthError
from app.db.session import Database
from app.main import app
from app.scenarios.exam_policy import ExamProjectionDenied, project_exam
from app.scenarios.fixtures import EventFixture, load_training_fixture
from app.scenarios.models import TrainingSelection
from app.scenarios.routes import select_training
from app.scenarios.seed import FIXTURES, load_seed, seed


def test_five_versioned_fixtures_and_truth_refs_are_consistent():
    items = load_seed(FIXTURES)
    assert {item.stable_key for item, _, _ in items} == {f"S0{i}" for i in range(1, 6)}
    assert [item.stable_key for item, _, _ in items if item.enabled] == ["S02"]
    for item, digest, truths in items:
        assert len(digest) == 64
        assert any(not truth.threat_label for truth in truths)
        fixture = load_training_fixture(
            FIXTURES / "events/training" / f"{item.stable_key.lower()}-v1.json"
        )
        serialized = fixture.model_dump_json()
        for forbidden in ("threat_label", "explanation", "rubric", "severity", "ai_brief"):
            assert forbidden not in serialized
        assert any(event.log.event_type == "page_view" for event in fixture.events)
    s02 = load_training_fixture(FIXTURES / "events/training/s02-v1.json")
    failed = [event for event in s02.events if event.log.event_type == "login_failed"]
    assert len(failed) == 10
    success = next(event for event in s02.events if event.log.event_type == "session_created")
    read = next(event for event in s02.events if event.log.event_type == "records_read")
    assert failed[-1].release_offset_ms < success.release_offset_ms < read.release_offset_ms
    assert success.username == read.username and success.log.session_id == read.log.session_id


def test_fixture_validation_rejects_exam_and_invalid_schedules(tmp_path):
    original = json.loads((FIXTURES / "events/training/s02-v1.json").read_text())
    for mutate in (
        lambda value: value.update(purpose="exam"),
        lambda value: value["events"].append(value["events"][0]),
        lambda value: value["events"][0].update(release_offset_ms=80000),
        lambda value: value["events"][0].update(event_offset_ms=500),
        lambda value: value["events"][0]["log"].update(threat_label=True),
    ):
        value = json.loads(json.dumps(original))
        mutate(value)
        target = tmp_path / "fixture.json"
        target.write_text(json.dumps(value))
        with pytest.raises(ValueError):
            load_training_fixture(target)
    exam = {**original, "purpose": "exam", "scenario_id": str(uuid4())}
    assert EventFixture.model_validate(exam).purpose == "exam"  # common format, separate loader


def test_training_input_cannot_supply_exam_controls():
    valid = {"scenario_ids": [str(uuid4())]}
    for field in ("mode", "attempt_id", "owner_user_id", "passed", "exam_case_id"):
        with pytest.raises(ValidationError):
            TrainingSelection.model_validate({**valid, field: "exam"})
    for ids in ([], valid["scenario_ids"] * 2, [str(uuid4()) for _ in range(6)]):
        with pytest.raises(ValidationError):
            TrainingSelection.model_validate({"scenario_ids": ids})


@pytest.mark.parametrize("status", ["running", "completing", "completed", "failed"])
def test_exam_projection_never_falls_back_to_training(status):
    source = {
        "id": str(uuid4()),
        "run_id": str(uuid4()),
        "mode": "exam",
        "status": status,
        "version": 1,
        "elapsed_ms": 7,
        "evidence_ids": [str(uuid4())],
        "title": "PRIVATE-ANSWER",
        "severity": "critical",
        "label": "PRIVATE-ANSWER",
        "ai_brief": {"secret": "PRIVATE-ANSWER"},
        "rubric": "PRIVATE-ANSWER",
        "initial_severity": "PRIVATE-ANSWER",
        "ground_truth": "PRIVATE-ANSWER",
        "future_events": ["PRIVATE-ANSWER"],
        "config_hash": "PRIVATE-ANSWER",
    }
    assert set(project_exam("run", source).model_dump()) == {
        "id",
        "mode",
        "status",
        "version",
        "elapsed_ms",
    }
    assert "PRIVATE-ANSWER" not in project_exam("alert", source).model_dump_json()
    ticket = project_exam("ticket", {**source, "status": "open"})
    assert ticket.model_dump()["title"] == "Investigation"
    assert "PRIVATE-ANSWER" not in ticket.model_dump_json()
    for surface in (
        "events",
        "overview",
        "analysis",
        "questions",
        "sources",
        "retry",
        "rubric",
        "audit",
        "history",
        "evaluation",
        "export",
        "ground_truth",
        "result",
        "new_surface",
    ):
        with pytest.raises(ExamProjectionDenied, match="^Exam projection unavailable$"):
            project_exam(surface, source)
    with pytest.raises(ExamProjectionDenied, match="^Exam projection unavailable$"):
        project_exam("alert", {**source, "evidence_ids": [{"answer_key": "PRIVATE-ANSWER"}]})


@pytest.mark.integration
def test_seed_repeat_concurrency_and_private_grants(migrated):
    async def scenario():
        owner = Database(migrated("migration_owner"))
        try:
            assert await asyncio.gather(seed(owner), seed(owner)) == [5, 5]
            assert await seed(owner) == 5
            async with owner.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.scenarios")) == 5
                assert await session.scalar(text("SELECT count(*) FROM private.ground_truth")) == 10
            for role in ("api_runtime", "worker_runtime", "evaluator_runtime"):
                db = Database(migrated(role))
                try:
                    async with db.sessions() as session:
                        if role == "evaluator_runtime":
                            assert (
                                await session.scalar(
                                    text("SELECT count(*) FROM private.ground_truth")
                                )
                                == 10
                            )
                        else:
                            with pytest.raises(DBAPIError):
                                await session.execute(text("SELECT * FROM private.ground_truth"))
                    for sql in (
                        "UPDATE app.scenarios SET enabled=true",
                        "DELETE FROM private.ground_truth",
                    ):
                        async with db.sessions() as session:
                            with pytest.raises(DBAPIError):
                                await session.execute(text(sql))
                    if role == "api_runtime":
                        async with db.sessions() as session:
                            with pytest.raises(DBAPIError):
                                await session.execute(
                                    text("SELECT fixture_hash FROM app.scenarios")
                                )
                finally:
                    await db.close()
        finally:
            await owner.close()

    asyncio.run(scenario())


@pytest.mark.integration
def test_seed_conflict_rolls_back_and_exam_import_is_rejected(migrated, tmp_path):
    shutil.copytree(FIXTURES, tmp_path / "fixtures")
    directory = tmp_path / "fixtures"

    async def scenario():
        db = Database(migrated("migration_owner"))
        try:
            await seed(db)
            path = directory / "ground-truth/training.json"
            rows = json.loads(path.read_text())
            rows[-1]["explanation"] = "changed without version"
            path.write_text(json.dumps(rows))
            with pytest.raises(ValueError, match="Truth version conflict"):
                await seed(db, directory)
            path.write_text((FIXTURES / "ground-truth/training.json").read_text())
            path = directory / "catalog.json"
            rows = json.loads(path.read_text())
            rows[0]["purpose"] = "exam"
            path.write_text(json.dumps(rows))
            with pytest.raises(ValidationError):
                await seed(db, directory)
            async with db.sessions() as session:
                assert await session.scalar(text("SELECT count(*) FROM app.scenarios")) == 5
                assert await session.scalar(text("SELECT count(*) FROM private.ground_truth")) == 10
                with pytest.raises(DBAPIError):
                    await session.execute(text("UPDATE app.scenarios SET purpose='exam'"))
        finally:
            await db.close()

    asyncio.run(scenario())


@pytest.mark.integration
def test_catalog_and_selection_cannot_admit_disabled_demo_or_exam(migrated, monkeypatch):
    async def setup():
        db = Database(migrated("migration_owner"))
        try:
            await seed(db)
        finally:
            await db.close()
        db = Database(migrated("api_runtime"))
        try:
            items = load_seed(FIXTURES)
            enabled = next(item.id for item, _, _ in items if item.enabled)
            disabled = next(item.id for item, _, _ in items if not item.enabled)
            async with db.sessions() as session:
                assert (
                    len(await select_training(session, TrainingSelection(scenario_ids=[enabled])))
                    == 1
                )
                for identity in (disabled, uuid4(), UUID("00000000-0000-4000-8000-000000000001")):
                    with pytest.raises(AuthError) as error:
                        await select_training(
                            session, TrainingSelection(scenario_ids=[enabled, identity])
                        )
                    assert error.value.code == "INVALID_SCENARIO_SELECTION"
            return enabled
        finally:
            await db.close()

    enabled = asyncio.run(setup())
    url = migrated("api_runtime")
    for key, value in {
        "DB_HOST": url.host,
        "DB_PORT": str(url.port),
        "DB_NAME": url.database,
        "DB_PASSWORD_FILE": str(Path(os.environ["SOC_TEST_SECRETS_DIR"]) / "api_runtime.txt"),
    }.items():
        monkeypatch.setenv(key, value)
    with TestClient(app) as client:
        for query in ("?cursor=PRIVATE-ANSWER", "?limit=101", "?limit=0"):
            error = client.get("/api/v1/scenarios" + query)
            assert error.status_code in (400, 422)
            assert "PRIVATE-ANSWER" not in error.text
        response = client.get("/api/v1/scenarios")
        assert response.status_code == 200
        assert response.json()["data"][0]["id"] == str(enabled)
        assert len(response.json()["data"]) == 1
        assert response.json()["meta"]["next_cursor"] is None
        assert client.get(f"/api/v1/scenarios?cursor={enabled}").json()["data"] == []
        assert set(response.json()["data"][0]) == {
            "id",
            "version",
            "title",
            "difficulty",
            "duration_ms",
            "learning_objectives",
        }
        for forbidden in (
            "fixture",
            "threat_label",
            "rubric",
            "e001",
            "SIM-T-204",
            "records/export",
        ):
            assert forbidden not in response.text
        for path in ("/api/v1/runs", f"/api/v1/levels/{uuid4()}/attempts"):
            reply = client.post(
                path, json={"scenario_ids": [str(enabled)], "mode": "exam", "answer_key": "NO-ECHO"}
            )
            assert reply.status_code == 404 and "NO-ECHO" not in reply.text
        assert client.post("/api/v1/scenarios", json={}).status_code == 405
        for path in (
            "/fixtures/ground-truth/training.json",
            "/fixtures/events/training/s02-v1.json",
            "/api/v1/scenarios/../private/ground_truth",
        ):
            assert client.get(path).status_code == 404

        async def enable_all():
            db = Database(migrated("migration_owner"))
            try:
                async with db.sessions() as session, session.begin():
                    await session.execute(text("UPDATE app.scenarios SET enabled=true"))
            finally:
                await db.close()

        asyncio.run(enable_all())
        ids = []
        cursor = ""
        while True:
            body = client.get("/api/v1/scenarios?limit=2" + cursor).json()
            assert len(body["data"]) <= 2
            ids.extend(item["id"] for item in body["data"])
            if body["meta"]["next_cursor"] is None:
                break
            cursor = "&cursor=" + body["meta"]["next_cursor"]
        assert len(ids) == len(set(ids)) == 5
        assert ids == sorted(ids)

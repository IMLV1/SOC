"""Destructive tests require explicit opt-in and a separate soc_test_* database."""

import asyncio
import os
import secrets
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.bootstrap import bootstrap
from app.db.health import check_database
from app.db.migrate import MIGRATION_LOCK, expected_head, migrate, revision_hashes
from app.db.provision import PASSWORDS, assign, provision_user
from app.db.session import Database
from app.main import app

pytestmark = pytest.mark.integration


async def sql(url, statement, values=None):
    engine = create_async_engine(url, hide_parameters=True)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(statement), values or {})
            return result.fetchall() if result.returns_rows else []
    finally:
        await engine.dispose()


def test_fresh_migration_is_atomic_and_retryable(pg, monkeypatch):
    from app.db import migrate as module

    real_upgrade = module.command.upgrade

    def fail_after_ddl(*args):
        real_upgrade(*args)
        raise RuntimeError("simulated failure after DDL")

    async def scenario():
        monkeypatch.setattr(module.command, "upgrade", fail_after_ddl)
        with pytest.raises(RuntimeError, match="simulated failure"):
            await migrate(pg("migration_owner"))
        tables = await sql(
            pg("postgres"), "SELECT count(*) FROM pg_tables WHERE schemaname IN ('app','ops')"
        )
        assert tables[0][0] == 0
        monkeypatch.setattr(module.command, "upgrade", real_upgrade)
        await migrate(pg("migration_owner"))
        assert (await sql(pg("api_runtime"), "SELECT version_num FROM ops.alembic_version"))[0][
            0
        ] == expected_head()

    asyncio.run(scenario())


def test_concurrent_repeat_migrations_have_one_row_per_revision(pg):
    async def scenario():
        await asyncio.gather(migrate(pg("migration_owner")), migrate(pg("migration_owner")))
        await migrate(pg("migration_owner"))
        rows = await sql(pg("api_runtime"), "SELECT version,checksum FROM ops.schema_migrations")
        assert {row[0]: row[1] for row in rows} == revision_hashes()
        tables = await sql(
            pg("api_runtime"), "SELECT tablename FROM pg_tables WHERE schemaname='app'"
        )
        assert {row[0] for row in tables} == {
            "users",
            "auth_sessions",
            "auth_challenges",
            "google_identities",
            "google_flows",
            "supabase_identities",
            "supabase_sessions",
            "supabase_flows",
            "practice_cases",
            "demo_events",
            "practice_drafts",
            "practice_answers",
            "written_questions",
            "written_submissions",
            "written_feedback",
            "tutor_policy",
            "tutor_questions",
            "user_quotas",
            "quota_ledgers",
            "instructor_assignments",
            "audit_logs",
            "auth_rate_limits",
            "scenarios",
            "runs",
            "scenario_instances",
            "run_versions",
            "run_completions",
            "events",
            "jobs",
            "worker_heartbeats",
            "idempotency_keys",
            "detections",
            "detection_evidence",
            "alerts",
            "tickets",
            "ticket_events",
            "ticket_alerts",
            "assessments",
            "notes",
            "note_evidence",
            "note_versions",
            "note_version_evidence",
            "analyses",
            "analysis_evidence",
            "analysis_attempts",
            "quota_reservations",
            "ticket_analyses",
            "evaluations",
            "evaluation_items",
            "instructor_run_comments",
            "experiment_batches",
            "experiment_arms",
            "provider_policy",
            "provider_calls",
            "retrievals",
            "retrieval_items",
            "analysis_knowledge_refs",
            "quota_components",
            "learning_levels",
            "lessons",
            "user_lesson_progress",
            "exam_cases",
            "exam_attempts",
            "exam_answers",
            "grading_revisions",
            "level_unlocks",
        }

    asyncio.run(scenario())


@pytest.mark.parametrize("previous", ["0001_auth_foundation", "0002_auth_rate_limits"])
def test_upgrade_from_auth_foundation_preserves_accounts(pg, monkeypatch, previous):
    from app.db import migrate as module

    real_upgrade = module.command.upgrade
    hashes = revision_hashes()

    async def scenario():
        monkeypatch.setattr(
            module,
            "revision_hashes",
            lambda: {key: value for key, value in hashes.items() if key <= previous},
        )
        monkeypatch.setattr(
            module.command,
            "upgrade",
            lambda config, target: real_upgrade(config, previous),
        )
        await migrate(pg("migration_owner"), "previous")
        db = Database(pg("migration_owner"))
        try:
            user = await provision_user(
                db,
                email="upgrade@example.test",
                display_name="Upgrade",
                password="Test-upgrade-password",
                role="analyst",
                daily_runs=10,
                daily_ai_requests=20,
            )
        finally:
            await db.close()
        monkeypatch.setattr(module, "revision_hashes", lambda: hashes)
        monkeypatch.setattr(module.command, "upgrade", real_upgrade)
        await migrate(pg("migration_owner"), "step04")
        rows = await sql(pg("api_runtime"), "SELECT id FROM app.users WHERE id=:id", {"id": user})
        assert rows[0][0] == user
        assert (await sql(pg("api_runtime"), "SELECT count(*) FROM ops.schema_migrations"))[0][
            0
        ] == len(hashes)

    asyncio.run(scenario())


def test_migration_waits_for_shared_advisory_lock(pg):
    async def scenario():
        owner = create_async_engine(pg("migration_owner"))
        async with owner.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK})
            task = asyncio.create_task(migrate(pg("migration_owner")))
            await asyncio.sleep(0.15)
            assert not task.done()
        await asyncio.wait_for(task, 10)
        await owner.dispose()

    asyncio.run(scenario())


def test_checksum_mismatch_fails_closed(migrated):
    async def scenario():
        await sql(
            migrated("migration_owner"), "UPDATE ops.schema_migrations SET checksum=repeat('0',64)"
        )
        with pytest.raises(RuntimeError, match="checksum"):
            await migrate(migrated("migration_owner"))
        db = Database(migrated("api_runtime"))
        try:
            assert not await check_database(db, "api_runtime")
        finally:
            await db.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "role", ["api_runtime", "worker_runtime", "evaluator_runtime", "retention_runtime"]
)
def test_runtime_roles_cannot_ddl_read_private_or_modify_ledger(migrated, role):
    async def scenario():
        flags = await sql(
            migrated(role),
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls "
            "FROM pg_roles WHERE rolname=current_user",
        )
        assert flags[0] == (False, False, False, False)
        owned = await sql(
            migrated(role), "SELECT count(*) FROM pg_tables WHERE tableowner=current_user"
        )
        assert owned[0][0] == 0
        await sql(migrated("migration_owner"), "CREATE TABLE private.test_key (value text)")
        for statement in [
            "CREATE TABLE app.forbidden(id integer)",
            "CREATE TABLE public.forbidden(id integer)",
            "SELECT * FROM private.test_key",
            "UPDATE ops.schema_migrations SET release_sha='tampered'",
            "SET ROLE migration_owner",
        ]:
            with pytest.raises(DBAPIError):
                await sql(migrated(role), statement)

    asyncio.run(scenario())


@pytest.mark.parametrize("role", ["api_runtime", "worker_runtime", "evaluator_runtime"])
def test_runtime_audit_is_append_only(migrated, role):
    async def scenario():
        await sql(
            migrated(role),
            "INSERT INTO app.audit_logs(id,actor_role,action,entity_type) "
            "VALUES (:id,'system','test','test')",
            {"id": uuid4()},
        )
        for statement in [
            "UPDATE app.audit_logs SET action='changed'",
            "DELETE FROM app.audit_logs",
            "TRUNCATE app.audit_logs",
        ]:
            with pytest.raises(DBAPIError):
                await sql(migrated(role), statement)

    asyncio.run(scenario())


def test_provision_repeat_assignment_and_hashing(migrated):
    async def scenario():
        db = Database(migrated("migration_owner"))
        password = secrets.token_urlsafe(24)
        data = dict(
            email="instructor@example.test",
            display_name="Instructor",
            password=password,
            role="instructor",
            daily_runs=3,
            daily_ai_requests=0,
        )
        try:
            first, again = await asyncio.gather(
                provision_user(db, **data), provision_user(db, **data)
            )
            assert first == again
            with pytest.raises(ValueError):
                await provision_user(db, **{**data, "role": "analyst"})
            analyst = await provision_user(
                db, **{**data, "email": "analyst@example.test", "role": "analyst"}
            )
            await assign(db, first, analyst)
            await assign(db, first, analyst)
            with pytest.raises(ValueError):
                await assign(db, analyst, first)
            rows = await sql(
                migrated("migration_owner"),
                "SELECT password_hash FROM app.users WHERE id=:id",
                {"id": first},
            )
            assert PASSWORDS.verify(rows[0][0], password)
            assert password not in rows[0][0]
            assert (
                await sql(
                    migrated("migration_owner"), "SELECT count(*) FROM app.instructor_assignments"
                )
            )[0][0] == 1
            audit = await sql(migrated("api_runtime"), "SELECT action,reason FROM app.audit_logs")
            assert len(audit) == 3
            assert password not in str(audit)
        finally:
            await db.close()

    asyncio.run(scenario())


def test_constraints_and_runtime_transaction_rollback(migrated):
    async def scenario():
        db = Database(migrated("api_runtime"))
        user_id = uuid4()
        statement = """INSERT INTO app.users
                       (id,normalized_email,display_name,password_hash,role,status)
                       VALUES (:id,'test@example.test','Test',
                               '$argon2id$test-fixture','analyst','active')"""
        try:
            with pytest.raises(RuntimeError):
                async with db.sessions() as session, session.begin():
                    await session.execute(text(statement), {"id": user_id})
                    raise RuntimeError("rollback")
            assert not await sql(migrated("api_runtime"), "SELECT id FROM app.users")
            await sql(migrated("api_runtime"), statement, {"id": user_id})
            for invalid, values in [
                (statement, {"id": uuid4()}),  # normalized email unique
                (
                    "INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests) "
                    "VALUES (:id,-1,0)",
                    {"id": user_id},
                ),
                (
                    "INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests) "
                    "VALUES (:id,0,0)",
                    {"id": uuid4()},
                ),
                ("UPDATE app.users SET role='admin' WHERE id=:id", {"id": user_id}),
                ("UPDATE app.users SET version=0 WHERE id=:id", {"id": user_id}),
            ]:
                with pytest.raises(DBAPIError):
                    await sql(migrated("api_runtime"), invalid, values)
            with pytest.raises(DBAPIError):
                await sql(migrated("worker_runtime"), "SELECT password_hash FROM app.users")
        finally:
            await db.close()

    asyncio.run(scenario())


def test_api_ready_and_worker_with_runtime_credentials(migrated, monkeypatch):
    api_url = migrated("api_runtime")
    directory = Path(os.environ["SOC_TEST_SECRETS_DIR"])
    for key, value in {
        "DB_HOST": api_url.host,
        "DB_PORT": str(api_url.port),
        "DB_NAME": api_url.database,
        "DB_PASSWORD_FILE": str(directory / "api_runtime.txt"),
    }.items():
        monkeypatch.setenv(key, value)
    with TestClient(app) as client:
        assert client.get("/health/ready").json()["data"] == {"status": "ready"}
        assert client.get("/health/ready").status_code == 200
    env = {**os.environ, "DB_PASSWORD_FILE": str(directory / "worker_runtime.txt")}
    result = subprocess.run(
        [sys.executable, "-m", "app.worker", "--check"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    assert '"database_ready": true' in result.stdout
    assert '"queue_ready": true' in result.stdout
    monkeypatch.setenv("DB_PASSWORD_FILE", str(directory / "migration_owner.txt"))
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert api_url.password not in response.text


def test_bootstrap_repeat_preserves_accounts_and_grants(migrated):
    async def scenario():
        database = Database(migrated("migration_owner"))
        try:
            user = await provision_user(
                database,
                email="repeat@example.test",
                display_name="Repeat",
                password=secrets.token_urlsafe(24),
                role="instructor",
                daily_runs=2,
                daily_ai_requests=0,
            )
            await bootstrap(migrated("postgres"), Path(os.environ["SOC_TEST_SECRETS_DIR"]))
            await migrate(migrated("migration_owner"))
            assert (await sql(migrated("api_runtime"), "SELECT id FROM app.users"))[0][0] == user
            with pytest.raises(DBAPIError):
                await sql(migrated("api_runtime"), "DELETE FROM app.audit_logs")
        finally:
            await database.close()

    asyncio.run(scenario())


def test_sessions_challenges_and_ledger_constraints(migrated):
    async def scenario():
        database = Database(migrated("migration_owner"))
        try:
            user = await provision_user(
                database,
                email="session@example.test",
                display_name="Session",
                password=secrets.token_urlsafe(24),
                role="analyst",
                daily_runs=2,
                daily_ai_requests=0,
            )
            params = {"id": uuid4(), "user": user, "hash": "a" * 64}
            session = """INSERT INTO app.auth_sessions
                (id,user_id,token_hash,csrf_hash,expires_at)
                VALUES (:id,:user,:hash,:hash,now()+interval '1 day')"""
            await sql(migrated("api_runtime"), session, params)
            with pytest.raises(DBAPIError):
                await sql(migrated("api_runtime"), session, {**params, "id": uuid4()})
            with pytest.raises(DBAPIError):
                await sql(
                    migrated("api_runtime"), session, {**params, "id": uuid4(), "hash": "raw"}
                )
            challenge = """INSERT INTO app.auth_challenges(id,token_hash,csrf_hash,expires_at)
                VALUES (:id,:hash,:hash,now()+interval '10 minutes')"""
            await sql(migrated("api_runtime"), challenge, {"id": uuid4(), "hash": "b" * 64})
            with pytest.raises(DBAPIError):
                await sql(migrated("api_runtime"), challenge, {"id": uuid4(), "hash": "b" * 64})
            ledger = """INSERT INTO app.quota_ledgers(id,scope_key,user_id,period_start)
                VALUES (:id,:scope,:user,CURRENT_DATE)"""
            values = {"id": uuid4(), "scope": f"user:{user}", "user": user}
            await sql(migrated("api_runtime"), ledger, values)
            for invalid in [
                {**values, "id": uuid4()},
                {**values, "id": uuid4(), "scope": "system"},
            ]:
                with pytest.raises(DBAPIError):
                    await sql(migrated("api_runtime"), ledger, invalid)
            with pytest.raises(DBAPIError):
                await sql(migrated("api_runtime"), "UPDATE app.quota_ledgers SET run_count=-1")
        finally:
            await database.close()

    asyncio.run(scenario())

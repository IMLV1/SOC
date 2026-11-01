import asyncio

import pytest
from sqlalchemy import text

from app.db.migrate import MIGRATION_LOCK, expected_head, revision_hashes, sql_editor_upgrade
from app.db.session import Database

RELEASE = "a" * 40
PREVIOUS = "0027_reset_exam_attempt"


def test_sql_editor_export_requires_exact_sha_and_single_pending_revision():
    with pytest.raises(ValueError):
        sql_editor_upgrade("main", PREVIOUS)
    with pytest.raises(ValueError):
        sql_editor_upgrade(RELEASE, "0001_auth_foundation")
    sql = sql_editor_upgrade(RELEASE, PREVIOUS)
    assert "SET LOCAL ROLE migration_owner" in sql
    assert f"pg_advisory_xact_lock({MIGRATION_LOCK})" in sql
    assert "Migration checksum mismatch" in sql
    assert "INSERT INTO ops.schema_migrations" in sql
    assert revision_hashes()[expected_head()] in sql


@pytest.mark.integration
def test_sql_editor_upgrade_checks_ledger_applies_once_and_rejects_drift(migrated):
    async def execute():
        db = Database(migrated("postgres"))
        try:
            # Recreate the immediately previous schema/ledger in this disposable test DB.
            async with db.sessions() as session, session.begin():
                await session.execute(
                    text("ALTER TABLE app.analyses DROP CONSTRAINT question_fields")
                )
                await session.execute(
                    text("""ALTER TABLE app.analyses ADD CONSTRAINT question_fields
                    CHECK((kind='question' AND length(btrim(question_text)) BETWEEN 1 AND 2000
                      AND question_hash IS NOT NULL AND ticket_id IS NOT NULL
                      AND knowledge_release_id IS NOT NULL)
                    OR (kind='triage' AND question_text IS NULL AND question_hash IS NULL))""")
                )
                await session.execute(
                    text("DELETE FROM ops.schema_migrations WHERE version=:v"),
                    {"v": expected_head()},
                )
                await session.execute(
                    text("UPDATE ops.alembic_version SET version_num=:v"), {"v": PREVIOUS}
                )
            sql = sql_editor_upgrade(RELEASE, PREVIOUS)
            async with db.engine.connect() as connection:
                raw = await connection.get_raw_connection()
                await raw.driver_connection.execute(sql)
                await raw.driver_connection.execute(sql)
            async with db.sessions() as session:
                assert (
                    await session.scalar(text("SELECT version_num FROM ops.alembic_version"))
                    == expected_head()
                )
                assert (
                    await session.scalar(
                        text("SELECT release_sha FROM ops.schema_migrations WHERE version=:v"),
                        {"v": expected_head()},
                    )
                    == RELEASE
                )
                constraint = await session.scalar(
                    text("""SELECT pg_get_constraintdef(oid)
                    FROM pg_constraint WHERE conrelid='app.analyses'::regclass
                    AND conname='question_fields'""")
                )
                assert "dify-app" in constraint
            async with db.sessions() as session, session.begin():
                await session.execute(
                    text("UPDATE ops.schema_migrations SET checksum=:hash WHERE version=:v"),
                    {"hash": "0" * 64, "v": expected_head()},
                )
            async with db.engine.connect() as connection:
                raw = await connection.get_raw_connection()
                with pytest.raises(Exception, match="checksum mismatch"):
                    await raw.driver_connection.execute(sql)
                await raw.driver_connection.execute("ROLLBACK")
        finally:
            await db.close()

    asyncio.run(execute())

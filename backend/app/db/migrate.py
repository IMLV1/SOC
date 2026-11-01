"""One-shot Alembic migration + checksummed ledger under one transaction advisory lock."""

import asyncio
import hashlib
import io
import json
import os
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import URL, Connection, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.config import database_url, tls_connect_args

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION_LOCK = 73102002


def migration_config() -> Config:
    return Config(str(BACKEND / "alembic.ini"))


def revision_hashes() -> dict[str, str]:
    # Hash migration source files so edits to already-applied revisions fail closed.
    scripts = ScriptDirectory.from_config(migration_config())
    return {
        revision.revision: hashlib.sha256(
            Path(revision.path).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        for revision in reversed(list(scripts.walk_revisions()))
    }


def expected_head() -> str:
    head = ScriptDirectory.from_config(migration_config()).get_current_head()
    if head is None:
        raise RuntimeError("Migration head missing.")
    return head


def sql_editor_upgrade(release: str, previous: str) -> str:
    """Export one reviewed revision with the same role, lock and ledger guards.

    Intended for an authenticated SQL editor when a direct operator connection
    is unavailable. Replay is a no-op only when the entire ledger still matches.
    """
    if re.fullmatch(r"[0-9a-f]{40}", release) is None:
        raise ValueError("An exact release SHA is required")
    hashes = revision_hashes()
    versions = list(hashes)
    if len(versions) < 2 or previous != versions[-2]:
        raise ValueError("SQL editor export supports exactly the final pending revision")
    head = versions[-1]
    revision = ScriptDirectory.from_config(migration_config()).get_revision(head)
    if revision is None or revision.down_revision != previous:
        raise ValueError("A linear single revision upgrade is required")
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        revision.module.upgrade()
    expected = json.dumps(hashes).replace("'", "''")
    return f"""BEGIN;
SET LOCAL ROLE migration_owner;
SET LOCAL lock_timeout = '10s';
SELECT pg_advisory_xact_lock({MIGRATION_LOCK});
DO $soc_migration$
DECLARE expected jsonb := '{expected}'::jsonb;
        applied_count integer;
        current_head text;
BEGIN
  IF current_user <> 'migration_owner' THEN
    RAISE EXCEPTION 'Migrations require migration_owner';
  END IF;
  IF EXISTS (SELECT 1 FROM ops.schema_migrations m
      WHERE expected->>m.version IS DISTINCT FROM m.checksum) THEN
    RAISE EXCEPTION 'Migration checksum mismatch or unknown revision';
  END IF;
  SELECT count(*) INTO applied_count FROM ops.schema_migrations;
  IF (SELECT count(*) FROM ops.alembic_version) <> 1 THEN
    RAISE EXCEPTION 'Invalid Alembic head count';
  END IF;
  SELECT version_num INTO current_head FROM ops.alembic_version;
  IF applied_count = {len(versions)} AND current_head = '{head}' THEN
    RETURN;
  END IF;
  IF applied_count <> {len(versions) - 1} OR current_head <> '{previous}'
     OR EXISTS (SELECT 1 FROM jsonb_object_keys(expected - '{head}') v(version)
        WHERE NOT EXISTS (SELECT 1 FROM ops.schema_migrations m WHERE m.version=v.version))
     OR EXISTS (SELECT 1 FROM ops.schema_migrations WHERE version='{head}') THEN
    RAISE EXCEPTION 'Migration ledger is not the expected contiguous previous release';
  END IF;
  {output.getvalue()}
  UPDATE ops.alembic_version SET version_num='{head}' WHERE version_num='{previous}';
  INSERT INTO ops.schema_migrations(version,checksum,release_sha)
    VALUES ('{head}','{hashes[head]}','{release}');
END $soc_migration$;
COMMIT;
"""


def upgrade(connection: Connection, release: str) -> None:
    # This connection is already inside the caller's transaction: lock, Alembic
    # upgrade, and checksum-ledger writes either all commit or all roll back.
    if connection.scalar(text("SELECT current_user")) != "migration_owner":
        raise RuntimeError("Migrations require the dedicated migration_owner role.")
    connection.execute(text("SET LOCAL lock_timeout = '10s'"))
    connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK})
    connection.execute(
        text("""
        CREATE TABLE IF NOT EXISTS ops.schema_migrations (
            version text PRIMARY KEY, checksum text NOT NULL CHECK(length(checksum)=64),
            applied_at timestamptz NOT NULL DEFAULT now(), release_sha text NOT NULL
        )
    """)
    )
    hashes = revision_hashes()
    applied = {
        str(row[0]): str(row[1])
        for row in connection.execute(text("SELECT version,checksum FROM ops.schema_migrations"))
    }
    if any(
        version not in hashes or hashes[version] != checksum
        for version, checksum in applied.items()
    ):
        raise RuntimeError("Applied migration checksum mismatch or unknown revision.")
    versions = list(hashes)
    if set(applied) != set(versions[: len(applied)]):
        # A missing middle revision means the ledger cannot prove upgrade order.
        raise RuntimeError("Migration ledger is not a contiguous history.")
    has_version = connection.scalar(text("SELECT to_regclass('ops.alembic_version')"))
    current = (
        list(connection.scalars(text("SELECT version_num FROM ops.alembic_version")))
        if has_version
        else []
    )
    if current != ([versions[len(applied) - 1]] if applied else []):
        raise RuntimeError("Alembic revision and supplemental ledger disagree.")
    config = migration_config()
    config.attributes.update(connection=connection, migration_lock_held=True)
    command.upgrade(config, "head")
    for version, checksum in hashes.items():
        if version not in applied:
            connection.execute(
                text(
                    "INSERT INTO ops.schema_migrations(version,checksum,release_sha) "
                    "VALUES (:v,:c,:r)"
                ),
                {"v": version, "c": checksum, "r": release},
            )


async def migrate(url: URL, release: str = "local") -> None:
    engine = create_async_engine(url, hide_parameters=True, connect_args=tls_connect_args(url))
    try:
        async with engine.begin() as connection:
            await connection.run_sync(upgrade, release)
    finally:
        await engine.dispose()


def main() -> None:
    try:
        asyncio.run(migrate(database_url("migration_owner"), os.getenv("RELEASE_SHA", "local")))
    except Exception:
        raise SystemExit(
            "Migration failed; database transaction rolled back. Check configuration/ledger."
        ) from None
    print("Migrations and checksum ledger are current.")


if __name__ == "__main__":
    main()

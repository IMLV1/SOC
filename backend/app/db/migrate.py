"""One-shot Alembic migration + checksummed ledger under one transaction advisory lock."""

import asyncio
import hashlib
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
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

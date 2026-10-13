"""Explicit administrator-only bootstrap. Never imported by API/worker startup."""

import asyncio
import os
from pathlib import Path

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.config import ROLES, database_url, password_from_file


async def bootstrap(url: URL, secrets: Path) -> None:
    engine = create_async_engine(url, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT pg_advisory_xact_lock(73102001)"))
            for role in ROLES:
                exists = await connection.scalar(
                    text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)"),
                    {"role": role},
                )
                if not exists:
                    await connection.execute(text(f'CREATE ROLE "{role}"'))
                # Role identifiers are compile-time allowlisted. Password literal comes from PG.
                literal = await connection.scalar(
                    text("SELECT quote_literal(:password)"),
                    {"password": password_from_file(str(secrets / f"{role}.txt"))},
                )
                await connection.exec_driver_sql(
                    f'ALTER ROLE "{role}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                    f"NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {literal}"
                )
            db_name = await connection.scalar(text("SELECT quote_ident(current_database())"))
            await connection.exec_driver_sql(f"REVOKE ALL ON DATABASE {db_name} FROM PUBLIC")
            await connection.exec_driver_sql(
                f"GRANT CONNECT ON DATABASE {db_name} TO " + ",".join(ROLES)
            )
            await connection.execute(text("REVOKE ALL ON SCHEMA public FROM PUBLIC"))
            for schema in ("app", "private", "ops"):
                await connection.execute(
                    text(f"CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION migration_owner")
                )
                owner = await connection.scalar(
                    text("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=:name"),
                    {"name": schema},
                )
                if owner != "migration_owner":
                    raise ValueError("Existing schema has an unexpected owner; refusing adoption.")
                await connection.execute(text(f"REVOKE ALL ON SCHEMA {schema} FROM PUBLIC"))
            await connection.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner "
                    "REVOKE ALL ON TABLES FROM PUBLIC"
                )
            )
    finally:
        await engine.dispose()


def main() -> None:
    try:
        asyncio.run(bootstrap(database_url("postgres"), Path(os.environ["ROLE_SECRETS_DIR"])))
    except Exception:
        # DB exceptions may contain rendered DDL/password literals. Never print them.
        raise SystemExit("Database bootstrap failed; check isolated admin configuration.") from None
    print("Database roles/schemas bootstrapped; runtime has no owner privileges.")


if __name__ == "__main__":
    main()

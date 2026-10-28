"""Explicit managed-project bootstrap; never revoke Supabase's database/public grants."""

import asyncio
import os
from pathlib import Path

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.config import ROLES, password_from_file, tls_connect_args


async def setup(url: URL, secrets: Path) -> None:
    if os.environ.get("SOC_SUPABASE_SETUP") != "yes":
        raise ValueError("Explicit managed-project setup opt-in required")
    if not url.host or not url.host.endswith(".pooler.supabase.com"):
        raise ValueError("Expected managed session pooler")
    engine = create_async_engine(url, hide_parameters=True, connect_args=tls_connect_args(url))
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT pg_advisory_xact_lock(73102001)"))
            if await connection.scalar(text("SELECT current_user")) != "postgres":
                raise ValueError("Operator role required")
            for role in (*ROLES, "knowledge_publisher", "knowledge_ingestor"):
                # Refuse existing names on first setup. Re-running requires matching schema owner.
                exists = await connection.scalar(
                    text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}
                )
                if exists:
                    raise ValueError("Role already exists; use reviewed recovery, not adoption")
            for schema in ("app", "private", "ops", "kb"):
                if await connection.scalar(
                    text("SELECT 1 FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}
                ):
                    raise ValueError("SOC schema already exists; refusing overwrite")
            available = await connection.scalar(
                text(
                    "SELECT 1 FROM pg_available_extension_versions "
                    "WHERE name='vector' AND version='0.8.2'"
                )
            )
            if not available:
                raise ValueError("Required vector version unavailable")
            existing = await connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
            if existing is not None:
                raise ValueError("Existing vector extension requires operator compatibility review")
            await connection.execute(
                text("CREATE EXTENSION vector WITH SCHEMA public VERSION '0.8.2'")
            )
            for role in ROLES:
                literal = await connection.scalar(
                    text("SELECT quote_literal(:password)"),
                    {"password": password_from_file(str(secrets / f"{role}.txt"))},
                )
                await connection.exec_driver_sql(
                    f'CREATE ROLE "{role}" LOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                    f"NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {literal}"
                )
            for role in ("knowledge_publisher", "knowledge_ingestor"):
                await connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOINHERIT')
            await connection.execute(text("GRANT knowledge_publisher TO migration_owner"))
            await connection.execute(
                text("GRANT knowledge_ingestor TO worker_runtime WITH INHERIT TRUE")
            )
            # PostgreSQL 17 already grants the creator ADMIN via the new role itself.
            # Granting ADMIN back to that grantor is rejected; only enable SET/INHERIT.
            await connection.execute(
                text("GRANT migration_owner TO postgres WITH INHERIT TRUE, SET TRUE")
            )
            db = await connection.scalar(text("SELECT quote_ident(current_database())"))
            await connection.exec_driver_sql(
                f"GRANT CONNECT ON DATABASE {db} TO " + ",".join(ROLES)
            )
            await connection.execute(
                text(
                    "GRANT USAGE ON SCHEMA public TO migration_owner,worker_runtime,"
                    "knowledge_publisher,knowledge_ingestor"
                )
            )
            for schema in ("app", "private", "ops", "kb"):
                await connection.execute(
                    text(f"CREATE SCHEMA {schema} AUTHORIZATION migration_owner")
                )
                await connection.execute(
                    text(
                        f"REVOKE ALL ON SCHEMA {schema} FROM PUBLIC,anon,authenticated,service_role"
                    )
                )
            await connection.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner "
                    "REVOKE ALL ON TABLES FROM PUBLIC"
                )
            )
            # A narrowly scoped read-only bridge; runtime never receives auth schema grants.
            await connection.execute(
                text("""
                CREATE FUNCTION ops.supabase_session_active(subject uuid, session_id uuid)
                RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
                SET search_path=pg_catalog AS $$
                  SELECT EXISTS(SELECT 1 FROM auth.sessions s JOIN auth.users u ON u.id=s.user_id
                    WHERE s.id=session_id AND s.user_id=subject
                    AND (s.not_after IS NULL OR s.not_after>now())
                    AND u.deleted_at IS NULL AND (u.banned_until IS NULL OR u.banned_until<=now()))
                $$
            """)
            )
            await connection.execute(
                text("REVOKE ALL ON FUNCTION ops.supabase_session_active(uuid,uuid) FROM PUBLIC")
            )
            await connection.execute(
                text(
                    "GRANT EXECUTE ON FUNCTION ops.supabase_session_active(uuid,uuid) "
                    "TO api_runtime"
                )
            )
    finally:
        await engine.dispose()


async def main() -> None:
    project = os.environ["DB_PROJECT_REF"]
    # Operator password is provider-managed, not a new runtime role secret.
    password = Path(os.environ["DB_PASSWORD_FILE"]).read_text().strip()
    if not password or "\x00" in password or "\n" in password:
        raise ValueError("Invalid operator password file")
    url = URL.create(
        "postgresql+asyncpg",
        username=f"postgres.{project}",
        password=password,
        host=os.environ["DB_HOST"],
        port=5432,
        database="postgres",
    )
    await setup(url, Path(os.environ["ROLE_SECRETS_DIR"]))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        raise SystemExit(
            "Managed setup failed; transaction rolled back. No secret output."
        ) from None
    print("SOC roles and isolated schemas created; managed auth/public grants preserved.")

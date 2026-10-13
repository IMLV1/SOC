import asyncio

from sqlalchemy import text

from app.db.migrate import expected_head, revision_hashes
from app.db.session import Database


async def check_database(database: Database, role: str) -> bool:
    try:
        async with asyncio.timeout(5):
            async with database.engine.connect() as connection:
                actual = (
                    await connection.execute(
                        text("""SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls
                                FROM pg_roles WHERE rolname=current_user""")
                    )
                ).one()
                if actual[0] != role or any(actual[1:]):
                    return False
                owner = await connection.scalar(
                    text("""SELECT EXISTS(SELECT 1 FROM pg_namespace
                            WHERE nspname IN ('app','ops','private')
                            AND nspowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))""")
                )
                if owner:
                    return False
                head = (
                    await connection.scalars(text("SELECT version_num FROM ops.alembic_version"))
                ).all()
                if list(head) != [expected_head()]:
                    return False
                rows = await connection.execute(
                    text("SELECT version,checksum FROM ops.schema_migrations")
                )
                return {str(row[0]): str(row[1]) for row in rows} == revision_hashes()
    except Exception:
        # Missing schema, bad secret, connectivity/timeout: no DSN/SQL in public output.
        return False

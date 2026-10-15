"""Explicit local operator bootstrap for a new, disposable Render preview database.

Reads credentials from an ignored local directory. Never prints URLs, SQL or passwords.
Never run this from the web service or upload the administrator URL to Render services.
"""

import argparse
import asyncio
import secrets
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.bootstrap import bootstrap
from app.db.config import ROLES, password_from_file, tls_connect_args
from app.db.migrate import migrate
from app.db.session import Database
from app.scenarios.seed import seed


async def prepare(directory: Path) -> None:
    url = make_url((directory / "admin-url.txt").read_text(encoding="utf-8").strip())
    if not url.host or not url.host.endswith(".render.com"):
        raise ValueError("Expected an external Render database hostname")
    hostname = url.host
    url = url.set(drivername="postgresql+asyncpg", query={})
    for role in ROLES:
        path = directory / f"{role}.txt"
        if not path.exists():
            path.write_text(secrets.token_urlsafe(36), encoding="utf-8")
        password_from_file(str(path))
    engine = create_async_engine(url, hide_parameters=True, connect_args=tls_connect_args(url))
    try:
        async with engine.begin() as connection:
            # Managed PostgreSQL administrators aren't superusers. PostgreSQL 17
            # requires explicit SET membership to assign schema ownership.
            exists = await connection.scalar(
                text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='migration_owner')")
            )
            if not exists:
                await connection.execute(text("CREATE ROLE migration_owner NOLOGIN"))
            administrator = await connection.scalar(text("SELECT quote_ident(current_user)"))
            await connection.exec_driver_sql(
                f"GRANT migration_owner TO {administrator} WITH SET TRUE"
            )
        await bootstrap(url, directory)
    finally:
        await engine.dispose()
    owner_url = url.set(
        username="migration_owner",
        password=password_from_file(str(directory / "migration_owner.txt")),
    )
    await migrate(owner_url, "render-free-preview")
    database = Database(owner_url)
    try:
        await seed(database)
    finally:
        await database.close()
    # Runtime coordinates contain no password; upload only api_runtime.txt as a
    # Render secret file, never this directory or the owner/admin credentials.
    (directory / "runtime.env").write_text(
        f"DB_HOST={hostname.split('.')[0]}\nDB_PORT={url.port or 5432}\n"
        f"DB_NAME={url.database}\nDB_PASSWORD_FILE=/etc/secrets/api_runtime.txt\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        asyncio.run(prepare(args.directory.resolve()))
    except Exception:
        raise SystemExit(
            "Preview database preparation failed. Credentials/SQL suppressed; "
            "check managed database privileges and configuration."
        ) from None
    print("Preview roles, migrations and training catalog ready; no runtime owner access.")


if __name__ == "__main__":
    main()

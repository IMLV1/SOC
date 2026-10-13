import asyncio
import os
from pathlib import Path

import pytest
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.bootstrap import bootstrap
from app.db.config import password_from_file
from app.db.migrate import migrate


@pytest.fixture
def pg():
    name = os.getenv("SOC_TEST_DB_NAME", "")
    if not name:
        pytest.skip("Explicit isolated PostgreSQL test environment is not configured.")
    if not name.startswith("soc_test_") or os.getenv("SOC_TEST_ALLOW_RESET") != "yes":
        pytest.fail("Refusing reset: use a separate soc_test_* database and explicit reset opt-in.")
    directory = Path(os.environ["SOC_TEST_SECRETS_DIR"])

    def url(role):
        return URL.create(
            "postgresql+asyncpg",
            username=role,
            password=password_from_file(str(directory / f"{role}.txt")),
            host=os.getenv("SOC_TEST_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("SOC_TEST_DB_PORT", "5432")),
            database=name,
        )

    async def reset():
        engine = create_async_engine(url("postgres"))
        try:
            async with engine.begin() as conn:
                # Constant schemas, in the explicitly opted-in test database only.
                for schema in ("app", "private", "ops"):
                    await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        finally:
            await engine.dispose()
        await bootstrap(url("postgres"), directory)

    asyncio.run(reset())
    return url


@pytest.fixture
def migrated(pg):
    asyncio.run(migrate(pg("migration_owner"), "test"))
    return pg

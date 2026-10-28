import asyncio
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.bootstrap import bootstrap
from app.db.config import password_from_file
from app.db.migrate import migrate


@pytest.fixture
def investigation_release(tmp_path, monkeypatch):
    review = {
        "status": "approved_for_investigation",
        "reviewer": "synthetic test review",
        "workflow_id": "d62e8111-fd98-481f-9cb2-233b974550fa",
        "base_url": "https://dify.example.test/v1",
        "model_id": "synthetic-model",
        "contract_version": "soc-investigation-v1",
        "max_output_tokens": 2048,
        "call_bound_usd": "0.001000",
        "cost_bound_verified": True,
    }
    path = tmp_path / "investigation-review.json"
    path.write_text(json.dumps(review), encoding="utf8")
    key = tmp_path / "investigation-key"
    key.write_text("synthetic-investigation-key", encoding="utf8")
    values = {
        "SOC_AI_PROVIDER": "dify",
        "DIFY_ANALYSIS_RELEASE_FILE": str(path),
        "DIFY_ANALYSIS_APP_KEY_FILE": str(key),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values, review, path


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
                for schema in ("app", "private", "ops", "kb"):
                    await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(
                    text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public VERSION '0.8.2'")
                )
        finally:
            await engine.dispose()
        await bootstrap(url("postgres"), directory)

    asyncio.run(reset())
    return url


@pytest.fixture
def migrated(pg):
    asyncio.run(migrate(pg("migration_owner"), "test"))
    return pg

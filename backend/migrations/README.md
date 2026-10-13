# Migration boundary

No database schema or migration is created in checklist step 01.
SQLAlchemy, asyncpg and Alembic are pinned in `../pyproject.toml` and `../uv.lock`.
Step 02 adds the async environment, owner/runtime roles, advisory lock, migration
ledger and initial auth schema, and tests them against real PostgreSQL.
Do not run `alembic upgrade head` yet: no configured environment exists.

"""One-shot idempotent seeds run after the migration step."""

import asyncio

from app.db.config import database_url
from app.db.session import Database
from app.exams.seed import seed as seed_exam
from app.learning.seed import seed as seed_learning
from app.scenarios.seed import seed as seed_scenarios


async def main() -> None:
    database = Database(database_url("migration_owner"))
    try:
        await seed_scenarios(database)
        await seed_learning(database)
        await seed_exam(database)
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())

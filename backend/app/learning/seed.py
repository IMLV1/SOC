"""One-shot operator seed for the first versioned training lesson."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import text

from app.db.config import database_url
from app.db.session import Database
from app.learning.catalog import LESSON, LESSON_ID, LEVEL_ID


async def seed(database: Database) -> None:
    content = json.dumps(LESSON, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(content.encode()).hexdigest()
    async with database.sessions() as session, session.begin():
        await session.execute(
            text(
                """INSERT INTO app.learning_levels(id,ordinal,title,version)
                    VALUES (:id,1,'เริ่มต้น',1) ON CONFLICT(id) DO NOTHING"""
            ),
            {"id": LEVEL_ID},
        )
        existing = await session.scalar(
            text("SELECT content_hash FROM app.lessons WHERE id=:id AND version=1"),
            {"id": LESSON_ID},
        )
        if existing is not None and existing != digest:
            raise RuntimeError("Published lesson version is immutable; create a new version.")
        await session.execute(
            text(
                """INSERT INTO app.lessons
                    (id,level_id,version,title,content_json,content_hash,published_at)
                    VALUES (:id,:level,1,:title,CAST(:content AS jsonb),:hash,:published)
                    ON CONFLICT(id,version) DO NOTHING"""
            ),
            {
                "id": LESSON_ID,
                "level": LEVEL_ID,
                "title": LESSON["title"],
                "content": content,
                "hash": digest,
                "published": datetime.now(UTC),
            },
        )


async def main() -> None:
    database = Database(database_url("migration_owner"))
    try:
        await seed(database)
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())

"""Explicit operator seed. Runtime requests never open local training fixtures."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from app.db.session import Database
from app.learning.models import LessonView


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


async def seed(database: Database) -> None:
    # This package exists only in operator/test artifacts, never API/worker images.
    from operator_content.training_bank import QUESTIONS, cases, identifier

    path = Path(__file__).resolve().parents[2] / "fixtures/learning/curriculum-v1.json"
    curriculum = json.loads(path.read_text(encoding="utf-8"))
    level_ids = {item["ordinal"]: item["id"] for item in curriculum["levels"]}
    async with database.sessions() as session, session.begin():
        await session.execute(text("SELECT pg_advisory_xact_lock(73102202)"))
        for index, (demo_path, status) in enumerate((("/help", 200), ("/missing-page", 404)), 1):
            event_id = UUID(f"00000000-0000-4000-8000-{index:012}")
            await session.execute(
                text("""INSERT INTO app.demo_events(id,ordinal,content_json)
                    VALUES (:id,:ordinal,CAST(:content AS jsonb)) ON CONFLICT(id) DO NOTHING"""),
                {
                    "id": event_id,
                    "ordinal": index,
                    "content": encoded(
                        {
                            "id": str(event_id),
                            "event_time": f"2026-01-01T09:0{index - 1}:00Z",
                            "method": "GET",
                            "path": demo_path,
                            "status_code": status,
                            "description": "ตัวอย่างจำลองฝึกอ่าน request ไม่ใช่ข้อมูลผู้ใช้จริง",
                        }
                    ),
                },
            )
        for level in curriculum["levels"]:
            await session.execute(
                text("""INSERT INTO app.learning_levels(id,ordinal,title,version)
                VALUES (:id,:ordinal,:title,1) ON CONFLICT(id) DO NOTHING"""),
                {"id": UUID(level["id"]), "ordinal": level["ordinal"], "title": level["title"]},
            )
            for raw in level["lessons"]:
                lesson = LessonView.model_validate(raw)
                content = encoded(raw)
                digest = hashlib.sha256(content.encode()).hexdigest()
                previous = await session.scalar(
                    text("SELECT content_hash FROM app.lessons WHERE id=:id"), {"id": lesson.id}
                )
                if previous is not None and previous != digest:
                    raise RuntimeError("Published lesson drift; create a new content version.")
                await session.execute(
                    text("""INSERT INTO app.lessons
                    (id,level_id,version,title,content_json,content_hash,published_at)
                    VALUES (:id,:level,:version,:title,CAST(:content AS jsonb),:hash,now())
                    ON CONFLICT(id) DO NOTHING"""),
                    {
                        "id": lesson.id,
                        "level": lesson.level_id,
                        "version": lesson.version,
                        "title": lesson.title,
                        "content": content,
                        "hash": digest,
                    },
                )
        for case in cases(level_ids):
            digest = hashlib.sha256(encoded(case).encode()).hexdigest()
            previous = await session.scalar(
                text("SELECT content_hash FROM app.practice_cases WHERE id=:id"),
                {"id": UUID(str(case["id"]))},
            )
            if previous is not None and previous != digest:
                raise RuntimeError("Published practice drift; create a new content version.")
            await session.execute(
                text("""INSERT INTO app.practice_cases
                (id,stable_key,level_id,category,title,version,content_json,content_hash)
                VALUES (:id,:key,:level,:category,:title,1,CAST(:content AS jsonb),:hash)
                ON CONFLICT(id) DO NOTHING"""),
                {
                    "id": UUID(str(case["id"])),
                    "key": case["stable_key"],
                    "level": UUID(str(case["level_id"])),
                    "category": case["category"],
                    "title": case["title"],
                    "content": encoded(case["content"]),
                    "hash": digest,
                },
            )
            truth = case["truth"]
            assert isinstance(truth, dict)
            await session.execute(
                text("""INSERT INTO private.practice_truths
                (case_id,severity,disposition,evidence_ids,explanation,limitation)
                VALUES (:id,:severity,:disposition,CAST(:evidence AS jsonb),
                    :explanation,:limitation)
                ON CONFLICT(case_id) DO NOTHING"""),
                {"id": UUID(str(case["id"])), **truth, "evidence": encoded(truth["evidence_ids"])},
            )
        for ordinal, questions in QUESTIONS.items():
            for index, prompt in enumerate(questions, 1):
                question_id = UUID(identifier(f"WR-L{ordinal}-{index:02}"))
                previous = await session.scalar(
                    text("SELECT prompt FROM app.written_questions WHERE id=:id"),
                    {"id": question_id},
                )
                if previous is not None and previous != prompt:
                    raise RuntimeError("Written question drift; create a new version.")
                await session.execute(
                    text("""INSERT INTO app.written_questions(id,level_id,ordinal,prompt,category)
                    VALUES (:id,:level,:ordinal,:prompt,'written_knowledge')
                    ON CONFLICT(id) DO NOTHING"""),
                    {
                        "id": question_id,
                        "level": UUID(level_ids[ordinal]),
                        "ordinal": index,
                        "prompt": prompt,
                    },
                )

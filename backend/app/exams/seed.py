"""One-shot immutable exam bank seed; private answer keys never enter public fixtures."""

import asyncio
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field
from sqlalchemy import text

from app.auth.models import Strict
from app.db.config import database_url
from app.db.session import Database
from app.learning.catalog import LEVEL_ID
from app.scenarios.fixtures import EventFixture, content_hash, load_fixture

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "exam"
SEED_LOCK = 73102020


class CaseSeed(Strict):
    id: UUID
    stable_key: str = Field(pattern=r"^E[0-9]{2}$")
    version: int = Field(ge=1)
    purpose: Literal["exam"]
    title: Literal["Investigation case"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    duration_ms: int = Field(gt=0)
    learning_objectives: list[str] = Field(min_length=1, max_length=10)
    enabled: bool


class CaseTruth(Strict):
    scenario_id: UUID
    expected_evidence_keys: list[str] = Field(min_length=1)
    expected_severity: Literal["low", "medium", "high", "critical"]
    expected_disposition: Literal["true_positive", "false_positive", "undetermined"]
    criterion_guidance: dict[str, str]


def load_bank(root: Path = ROOT) -> list[tuple[CaseSeed, EventFixture, CaseTruth]]:
    cases = [
        CaseSeed.model_validate(row) for row in json.loads((root / "catalog.json").read_text())
    ]
    truths = [
        CaseTruth.model_validate(row)
        for row in json.loads((root / "ground-truth.json").read_text())
    ]
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("Invalid exam bank")
    if {case.id for case in cases} != {truth.scenario_id for truth in truths}:
        raise ValueError("Exam bank and truth do not match")
    result = []
    for case in cases:
        fixture = load_fixture(
            root.parent / "events" / "exam" / f"{case.stable_key.lower()}-v{case.version}.json",
            "exam",
        )
        truth = next(value for value in truths if value.scenario_id == case.id)
        keys = {event.key for event in fixture.events}
        if fixture.scenario_id != case.id or fixture.duration_ms != case.duration_ms:
            raise ValueError("Exam fixture does not match its catalog")
        if not set(truth.expected_evidence_keys) <= keys:
            raise ValueError("Exam truth references unavailable evidence")
        if set(truth.criterion_guidance) != {"evidence", "analysis", "classification", "reasoning"}:
            raise ValueError("Invalid criterion guidance")
        result.append((case, fixture, truth))
    return result


async def seed(database: Database, root: Path = ROOT, *, level_id: UUID = LEVEL_ID) -> int:
    bank = load_bank(root)
    async with database.sessions() as session, session.begin():
        if await session.scalar(text("SELECT current_user")) != "migration_owner":
            raise ValueError("Migration owner required")
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SEED_LOCK})
        for case, fixture, truth in bank:
            scenario_seed = content_hash(case.model_dump(mode="json"))
            fixture_digest = content_hash(fixture.model_dump(mode="json"))
            truth_digest = content_hash(truth.model_dump(mode="json"))
            existing = (
                await session.execute(
                    text("SELECT seed_hash,fixture_hash FROM app.scenarios WHERE id=:id"),
                    {"id": case.id},
                )
            ).first()
            if existing and tuple(existing) != (scenario_seed, fixture_digest):
                raise ValueError("Exam scenario version conflict")
            if not existing:
                await session.execute(
                    text("""INSERT INTO app.scenarios
                      (id,stable_key,version,purpose,public_title,difficulty,duration_ms,
                       learning_objectives,enabled,fixture_hash,seed_hash)
                      VALUES (:id,:key,:version,'exam','Investigation case',:difficulty,:duration,
                       CAST(:objectives AS jsonb),:enabled,:fixture,:seed)"""),
                    {
                        "id": case.id,
                        "key": case.stable_key,
                        "version": case.version,
                        "difficulty": case.difficulty,
                        "duration": case.duration_ms,
                        "objectives": json.dumps(case.learning_objectives),
                        "enabled": case.enabled,
                        "fixture": fixture_digest,
                        "seed": scenario_seed,
                    },
                )
            previous_case = await session.scalar(
                text("SELECT seed_hash FROM app.exam_cases WHERE id=:id"), {"id": case.id}
            )
            if previous_case is not None and previous_case != scenario_seed:
                raise ValueError("Exam case version conflict")
            if previous_case is None:
                await session.execute(
                    text("""INSERT INTO app.exam_cases
                      (id,scenario_id,level_id,stable_key,version,duration_ms,enabled,seed_hash)
                      VALUES (:id,:id,:level,:key,:version,:duration,:enabled,:seed)"""),
                    {
                        "id": case.id,
                        "level": level_id,
                        "key": case.stable_key,
                        "version": case.version,
                        "duration": case.duration_ms,
                        "enabled": case.enabled,
                        "seed": scenario_seed,
                    },
                )
            prior_truth = await session.scalar(
                text(
                    "SELECT content_hash FROM private.exam_case_truths "
                    "WHERE case_id=:id AND version=:version"
                ),
                {"id": case.id, "version": case.version},
            )
            if prior_truth is not None and prior_truth != truth_digest:
                raise ValueError("Exam truth version conflict")
            if prior_truth is None:
                await session.execute(
                    text("""INSERT INTO private.exam_case_truths
                      (case_id,version,expected_evidence_keys,expected_severity,
                       expected_disposition,criterion_guidance,content_hash)
                      VALUES (:id,:version,CAST(:evidence AS jsonb),:severity,:disposition,
                       CAST(:guidance AS jsonb),:hash)"""),
                    {
                        "id": case.id,
                        "version": case.version,
                        "evidence": json.dumps(truth.expected_evidence_keys),
                        "severity": truth.expected_severity,
                        "disposition": truth.expected_disposition,
                        "guidance": json.dumps(truth.criterion_guidance),
                        "hash": truth_digest,
                    },
                )
    return len(bank)


async def seed_all_levels(database: Database) -> None:
    for ordinal, folder in ((2, "exam-middle"), (3, "exam-advanced")):
        await seed(
            database,
            ROOT.parent / folder,
            level_id=UUID(f"15000000-0000-4000-8000-{ordinal:012}"),
        )


async def main() -> None:
    database = Database(database_url("migration_owner"))
    try:
        print(f"Verified exam cases: {await seed(database)}")
    finally:
        await database.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        raise SystemExit(
            "Exam case seed failed; verify the versioned operator assets and database access."
        ) from None

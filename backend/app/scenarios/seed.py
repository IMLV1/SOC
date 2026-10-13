"""Owner-only, transactional and immutable versioned training seed CLI."""

import asyncio
import json
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field
from sqlalchemy import text

from app.auth.models import Strict
from app.db.config import database_url
from app.db.session import Database
from app.scenarios.fixtures import content_hash, load_training_fixture
from app.scenarios.models import ScenarioView

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SEED_LOCK = 73102005


class CatalogSeed(ScenarioView):
    stable_key: str = Field(pattern=r"^S0[1-5]$")
    purpose: Literal["training"]
    enabled: bool


class TruthSeed(Strict):
    scenario_id: UUID
    truth_version: int = Field(ge=1)
    incident_key: str
    threat_label: bool
    expected_evidence_keys: list[str] = Field(min_length=1)
    explanation: str


def load_seed(directory: Path) -> list[tuple[CatalogSeed, str, list[TruthSeed]]]:
    catalog = [
        CatalogSeed.model_validate(row)
        for row in json.loads((directory / "catalog.json").read_text(encoding="utf-8"))
    ]
    truths = [
        TruthSeed.model_validate(row)
        for row in json.loads(
            (directory / "ground-truth/training.json").read_text(encoding="utf-8")
        )
    ]
    if len({item.id for item in catalog}) != len(catalog):
        raise ValueError("Duplicate catalog")
    if {item.scenario_id for item in truths} != {item.id for item in catalog}:
        raise ValueError("Truth catalog mismatch")
    result = []
    for item in catalog:
        fixture = load_training_fixture(
            directory / "events/training" / f"{item.stable_key.lower()}-v{item.version}.json"
        )
        if fixture.scenario_id != item.id or fixture.duration_ms != item.duration_ms:
            raise ValueError("Fixture catalog mismatch")
        selected = [truth for truth in truths if truth.scenario_id == item.id]
        keys = {event.key for event in fixture.events}
        if len({(t.truth_version, t.incident_key) for t in selected}) != len(selected):
            raise ValueError("Duplicate truth")
        if any(not set(t.expected_evidence_keys) <= keys for t in selected):
            raise ValueError("Truth references unavailable evidence")
        result.append((item, content_hash(fixture.model_dump(mode="json")), selected))
    return result


async def seed(database: Database, directory: Path = FIXTURES) -> int:
    items = load_seed(directory)
    async with database.sessions() as session, session.begin():
        if await session.scalar(text("SELECT current_user")) != "migration_owner":
            raise ValueError("Migration owner required")
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SEED_LOCK})
        for item, fixture_hash, truths in items:
            digest = content_hash(item.model_dump(mode="json"))
            existing = (
                await session.execute(
                    text("SELECT seed_hash,fixture_hash FROM app.scenarios WHERE id=:id"),
                    {"id": item.id},
                )
            ).first()
            if existing and tuple(existing) != (digest, fixture_hash):
                raise ValueError("Seed version conflict; publish a new version")
            if not existing:
                await session.execute(
                    text("""INSERT INTO app.scenarios
                        (id,stable_key,version,purpose,public_title,difficulty,duration_ms,
                         learning_objectives,enabled,fixture_hash,seed_hash)
                        VALUES (:id,:key,:version,'training',:title,:difficulty,:duration,
                                CAST(:objectives AS jsonb),:enabled,:fixture,:digest)"""),
                    {
                        "id": item.id,
                        "key": item.stable_key,
                        "version": item.version,
                        "title": item.title,
                        "difficulty": item.difficulty,
                        "duration": item.duration_ms,
                        "objectives": json.dumps(item.learning_objectives),
                        "enabled": item.enabled,
                        "fixture": fixture_hash,
                        "digest": digest,
                    },
                )
            for truth in truths:
                identity = uuid5(
                    NAMESPACE_URL, f"soc:truth:{item.id}:{truth.truth_version}:{truth.incident_key}"
                )
                digest = content_hash(truth.model_dump(mode="json"))
                previous = await session.scalar(
                    text("SELECT content_hash FROM private.ground_truth WHERE id=:id"),
                    {"id": identity},
                )
                if previous is not None and previous != digest:
                    raise ValueError("Truth version conflict; publish a new version")
                if previous is None:
                    await session.execute(
                        text("""INSERT INTO private.ground_truth
                            (id,scenario_id,truth_version,incident_key,threat_label,
                             expected_evidence_keys,explanation,content_hash)
                            VALUES (:id,:scenario,:version,:key,:label,
                                    CAST(:evidence AS jsonb),:explanation,:digest)"""),
                        {
                            "id": identity,
                            "scenario": item.id,
                            "version": truth.truth_version,
                            "key": truth.incident_key,
                            "label": truth.threat_label,
                            "evidence": json.dumps(truth.expected_evidence_keys),
                            "explanation": truth.explanation,
                            "digest": digest,
                        },
                    )
    return len(items)


async def main() -> None:
    database = Database(database_url("migration_owner"))
    try:
        count = await seed(database)
        print(f"Training scenario versions verified: {count}")
    finally:
        await database.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # Fixture paths, payloads, SQL and truth must not become log/error content.
        raise SystemExit(
            "Scenario seed failed; check versioned assets and database access."
        ) from None

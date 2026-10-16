"""Operator-only real-profile calibration. Held-out queries must remain separate."""

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.db.session import Database
from app.knowledge.corpus import digest
from app.knowledge.gemini import PROFILE, embed
from app.knowledge.service import retrieve, validate_release


async def calibrate(
    owner: Database, worker: Database, release: UUID, suite: dict[str, Any], nonce: str
) -> None:
    if suite.get("profile") != PROFILE or not nonce.strip():
        raise ValueError("Explicit real profile and operator nonce required")
    cases = suite.get("calibration", [])
    if not 4 <= len(cases) <= 8 or sum(c.get("expected") is None for c in cases) < 2:
        raise ValueError("Need separate positive and negative calibration cases")
    if sum(c.get("expected") is not None for c in cases) < 2:
        raise ValueError("Positive calibration cases required")
    async with owner.sessions() as s:
        existing = await s.scalar(
            text("SELECT 1 FROM kb.retrieval_policies WHERE release_id=:id"), {"id": release}
        )
        if existing:
            raise ValueError("Calibration already frozen; prepare a new release")
        if (
            await s.scalar(text("SELECT profile_id FROM kb.releases WHERE id=:id"), {"id": release})
            != PROFILE
        ):
            raise ValueError("Release profile mismatch")
    vectors = []
    for index, case in enumerate(cases):
        # Operator calibration may span rate windows; never wait holding DB locks.
        while True:
            async with worker.sessions() as s:
                remaining = await s.scalar(
                    text("""SELECT greatest(0,extract(epoch FROM
                min(dispatched_at)+interval '60 seconds'-clock_timestamp()))
                FROM app.provider_calls WHERE dispatched_at>clock_timestamp()-interval '60 seconds'
                HAVING count(*) >= (SELECT rpm FROM app.provider_policy WHERE id=1)""")
                )
            if remaining is None or remaining <= 0:
                break
            await asyncio.sleep(min(float(remaining) + 0.1, 15))
        vectors.append(
            await embed(
                worker,
                uuid4(),
                case["query"],
                operation=f"calibration:{release}:{digest(nonce)}:{index}",
            )
        )
    async with owner.sessions() as s, s.begin():
        await s.execute(text("SET LOCAL ROLE knowledge_publisher"))
        if (
            await s.scalar(text("SELECT profile_id FROM kb.releases WHERE id=:id"), {"id": release})
            != PROFILE
        ):
            raise ValueError("Release profile mismatch")
        positives = []
        negatives = []
        for case, vector in zip(cases, vectors, strict=True):
            rows = await retrieve(s, release, case["query"], draft=True, vector=vector)
            if not rows:
                raise ValueError("Empty calibration retrieval")
            if case.get("expected") is None:
                negatives.append(rows[0]["distance"])
            else:
                if rows[0]["stable_key"] != case["expected"]:
                    raise ValueError("Golden top1 failed")
                positives.append(rows[0]["distance"])
        if max(positives) >= min(negatives):
            raise ValueError("Calibration is not separable; do not publish")
        threshold = (max(positives) + min(negatives)) / 2
        await s.execute(
            text("""INSERT INTO kb.retrieval_policies
            (release_id,max_distance,calibration_hash) VALUES (:rid,:threshold,:hash)"""),
            {
                "rid": release,
                "threshold": threshold,
                "hash": digest(json.dumps(suite, sort_keys=True)),
            },
        )
        positive_cases = [c for c in cases if c.get("expected") is not None]
        positive_vectors = [
            v for c, v in zip(cases, vectors, strict=True) if c.get("expected") is not None
        ]
        if not await validate_release(
            s, release, {"profile": PROFILE, "golden": positive_cases}, positive_vectors
        ):
            raise ValueError("Golden validation failed")

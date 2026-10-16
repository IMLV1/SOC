"""Explicitly enabled embedding jobs; existing reviewed chunks remain immutable."""

import json
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import Database
from app.knowledge.corpus import digest
from app.knowledge.gemini import PROFILE, embed
from app.worker.fencing import require_lease


async def prepare_real(
    session: AsyncSession, source_release: UUID, calibration_id: str | None = None
) -> UUID:
    if await session.scalar(text("SELECT current_user")) not in {
        "migration_owner",
        "knowledge_publisher",
    }:
        raise PermissionError("Publisher required")
    await session.execute(text("SELECT id FROM kb.active_release WHERE id=1 FOR UPDATE"))
    versions = list(
        (
            await session.execute(
                text("""SELECT v.id FROM kb.members m JOIN kb.versions v ON v.id=m.version_id
        WHERE m.release_id=:id AND v.status='ready' AND v.revoked_at IS NULL ORDER BY v.id"""),
                {"id": source_release},
            )
        )
        .scalars()
        .all()
    )
    if not versions:
        raise ValueError("Reviewed ready release required")
    if calibration_id is not None and (not calibration_id.strip() or len(calibration_id) > 100):
        raise ValueError("Invalid calibration identity")
    identity = PROFILE + ":" + ",".join(map(str, versions))
    # A new threshold requires a new immutable release, never overwriting old runs.
    if calibration_id is not None:
        identity += ":calibration:" + calibration_id
    manifest = digest(identity)
    rid = uuid5(NAMESPACE_URL, manifest)
    await session.execute(
        text("""INSERT INTO kb.releases(id,manifest_hash,profile_id)
        VALUES (:id,:hash,:profile) ON CONFLICT DO NOTHING"""),
        {"id": rid, "hash": manifest, "profile": PROFILE},
    )
    for vid in versions:
        jid = uuid5(vid, PROFILE)
        await session.execute(
            text("INSERT INTO kb.members VALUES (:rid,:vid) ON CONFLICT DO NOTHING"),
            {"rid": rid, "vid": vid},
        )
        await session.execute(
            text("""INSERT INTO app.jobs(id,type,dedupe_key,payload)
            VALUES (:id,'ingest_knowledge',:key,CAST(:payload AS jsonb)) ON CONFLICT DO NOTHING"""),
            {
                "id": jid,
                "key": str(jid),
                "payload": json.dumps({"version_id": str(vid), "profile": PROFILE}),
            },
        )
        await session.execute(
            text("""INSERT INTO kb.ingestions(id,version_id,profile_id,job_id)
            VALUES (:id,:vid,:profile,:id) ON CONFLICT DO NOTHING"""),
            {"id": jid, "vid": vid, "profile": PROFILE},
        )
    return rid


async def ingest_real(database: Database, job: dict[str, Any]) -> None:
    vid = UUID(job["payload"]["version_id"])
    async with database.sessions() as s:
        await require_lease(s, job)
        if not await s.scalar(
            text("""SELECT 1 FROM kb.ingestions
            WHERE job_id=:job AND version_id=:version AND profile_id=:profile"""),
            {"job": job["id"], "version": vid, "profile": PROFILE},
        ):
            raise ValueError("Ingestion identity mismatch")
        rows = (
            (
                await s.execute(
                    text("""SELECT c.id,c.body FROM kb.chunks c
            JOIN kb.versions v ON v.id=c.version_id
            WHERE v.id=:id AND v.status='ready' AND v.revoked_at IS NULL
            AND NOT EXISTS(SELECT 1 FROM kb.embeddings_gemini768 e
              WHERE e.chunk_id=c.id) ORDER BY c.ordinal"""),
                    {"id": vid},
                )
            )
            .mappings()
            .all()
        )
    for row in rows:
        async with database.sessions() as s:
            await require_lease(s, job)
            if await s.scalar(text("SELECT revoked_at FROM kb.versions WHERE id=:id"), {"id": vid}):
                raise ValueError("KNOWLEDGE_REVOKED")
        vector = await embed(
            database, job["id"], row["body"], operation="document:" + str(row["id"]), document=True
        )
        async with database.sessions() as s, s.begin():
            await s.execute(text("SELECT id FROM kb.versions WHERE id=:id FOR UPDATE"), {"id": vid})
            await require_lease(s, job)
            if await s.scalar(text("SELECT revoked_at FROM kb.versions WHERE id=:id"), {"id": vid}):
                raise ValueError("KNOWLEDGE_REVOKED")
            await s.execute(
                text(
                    "INSERT INTO kb.embeddings_gemini768 VALUES "
                    "(:id,CAST(:vector AS public.vector)) ON CONFLICT DO NOTHING"
                ),
                {"id": row["id"], "vector": json.dumps(vector)},
            )

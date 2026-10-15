"""Operator-only manifest admission/publish; worker-only draft ingestion; filtered retrieval."""

import json
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.fake_embeddings import FakeEmbeddings, validate_vector
from app.db.session import Database
from app.knowledge.corpus import chunks, digest
from app.worker.fencing import require_lease


async def admit(session: AsyncSession, documents: list[dict[str, Any]]) -> UUID:
    # No browser upload endpoint. Caller is the explicit publisher operator.
    if await session.scalar(text("SELECT current_user")) not in (
        "migration_owner",
        "knowledge_publisher",
    ):
        raise PermissionError("Publisher connection required")
    await session.execute(text("SELECT id FROM kb.active_release WHERE id=1 FOR UPDATE"))
    ids = []
    if not documents:
        raise ValueError("Empty manifest")
    for doc in documents:
        if not doc["body"].strip() or digest(doc["body"]) != doc["sha256"]:
            raise ValueError("Changed or empty document")
        identity = f"{doc['stable_key']}:{doc['revision']}"
        vid = uuid5(NAMESPACE_URL, "soc:kb:" + identity)
        old = await session.scalar(
            text("SELECT content_hash FROM kb.versions WHERE id=:id"), {"id": vid}
        )
        if old and old != doc["sha256"]:
            raise ValueError("Immutable revision content mismatch")
        await session.execute(
            text("""INSERT INTO kb.versions
            (id,stable_key,revision,title,language,reviewer,license,content_hash,body)
            VALUES(:id,:stable_key,:revision,:title,:language,:reviewer,:license,:sha256,:body)
            ON CONFLICT(id) DO NOTHING"""),
            {"id": vid, **doc},
        )
        jid = uuid5(NAMESPACE_URL, "soc:ingest:" + str(vid) + ":fake-hash-16-v1")
        await session.execute(
            text("""INSERT INTO app.jobs(id,type,dedupe_key,payload)
          VALUES(:id,'ingest_knowledge',:key,CAST(:payload AS jsonb))
          ON CONFLICT(dedupe_key) DO NOTHING"""),
            {"id": jid, "key": str(jid), "payload": json.dumps({"version_id": str(vid)})},
        )
        await session.execute(
            text("""INSERT INTO kb.ingestions(id,version_id,profile_id,job_id)
          VALUES(:id,:vid,'fake-hash-16-v1',:id) ON CONFLICT DO NOTHING"""),
            {"id": jid, "vid": vid},
        )
        ids.append(str(vid))
    manifest_hash = digest(
        json.dumps(
            {
                "profile": "fake-hash-16-v1",
                "splitter": "utf8-byte-v1",
                "members": sorted(
                    (
                        str(
                            uuid5(
                                NAMESPACE_URL, "soc:kb:" + doc["stable_key"] + ":" + doc["revision"]
                            )
                        ),
                        doc["sha256"],
                    )
                    for doc in documents
                ),
            },
            sort_keys=True,
        )
    )
    rid = uuid5(NAMESPACE_URL, "soc:release:" + manifest_hash)
    await session.execute(
        text("""INSERT INTO kb.releases(id,manifest_hash,profile_id)
      VALUES(:id,:hash,'fake-hash-16-v1') ON CONFLICT DO NOTHING"""),
        {"id": rid, "hash": manifest_hash},
    )
    for member_id in ids:
        await session.execute(
            text("""INSERT INTO kb.members VALUES(:rid,:vid)
          ON CONFLICT DO NOTHING"""),
            {"rid": rid, "vid": UUID(member_id)},
        )
    await session.execute(
        text("""INSERT INTO app.audit_logs
        (id,actor_role,action,entity_type,entity_id) VALUES
        (:id,'system','knowledge.admit','knowledge_release',:entity)"""),
        {"id": uuid4(), "entity": rid},
    )
    return rid


async def ingest(database: Database, job: dict[str, Any]) -> None:
    vid = UUID(job["payload"]["version_id"])
    async with database.sessions() as session, session.begin():
        # Version before job. Publish/revoke serialize with the same version lock.
        version = (
            (
                await session.execute(
                    text("SELECT * FROM kb.versions WHERE id=:id FOR UPDATE"), {"id": vid}
                )
            )
            .mappings()
            .one()
        )
        await require_lease(session, job)
        if not await session.scalar(
            text("""SELECT 1 FROM kb.ingestions
          WHERE job_id=:job AND version_id=:vid AND profile_id='fake-hash-16-v1'"""),
            {"job": job["id"], "vid": vid},
        ):
            raise ValueError("Ingestion identity mismatch")
        if version["revoked_at"]:
            raise ValueError("Knowledge revoked")
        if version["status"] == "ready":
            return
        for chunk in chunks(version["body"]):
            cid = uuid5(vid, str(chunk["ordinal"]))
            vector = await FakeEmbeddings().embed(chunk["body"])
            validate_vector(vector, 16)
            if not any(vector):
                raise ValueError("Zero embedding")
            await session.execute(
                text("""INSERT INTO kb.chunks
              (id,version_id,ordinal,heading,start_byte,end_byte,body,content_hash)
              VALUES(:id,:vid,:ordinal,:heading,:start_byte,:end_byte,:body,:content_hash)
              ON CONFLICT DO NOTHING"""),
                {"id": cid, "vid": vid, **chunk},
            )
            await session.execute(
                text("""INSERT INTO kb.embeddings_fake16 VALUES
              (:id,CAST(:vector AS public.vector)) ON CONFLICT DO NOTHING"""),
                {"id": cid, "vector": json.dumps(vector)},
            )
        await session.execute(
            text("UPDATE kb.versions SET status='ready' WHERE id=:id"), {"id": vid}
        )
        await require_lease(session, job)


async def publish(session: AsyncSession, rid: UUID, expected_version: int) -> None:
    if await session.scalar(text("SELECT current_user")) not in (
        "migration_owner",
        "knowledge_publisher",
    ):
        raise PermissionError("Publisher connection required")
    active = (
        (await session.execute(text("SELECT * FROM kb.active_release WHERE id=1 FOR UPDATE")))
        .mappings()
        .one()
    )
    if active["version"] != expected_version:
        raise ValueError("Active release version conflict")
    members = (
        (
            await session.execute(
                text("""SELECT v.id,v.status,v.revoked_at FROM kb.versions v
      JOIN kb.members m ON m.version_id=v.id WHERE m.release_id=:id ORDER BY v.id
      FOR UPDATE OF v"""),
                {"id": rid},
            )
        )
        .mappings()
        .all()
    )
    if not members or any(v["status"] != "ready" or v["revoked_at"] for v in members):
        raise ValueError("Partial or revoked corpus")
    missing = await session.scalar(
        text("""SELECT count(*) FROM kb.chunks c
      JOIN kb.members m ON m.version_id=c.version_id
      LEFT JOIN kb.embeddings_fake16 e ON e.chunk_id=c.id
      WHERE m.release_id=:id AND e.chunk_id IS NULL"""),
        {"id": rid},
    )
    empty = await session.scalar(
        text("""SELECT count(*) FROM kb.members m
      WHERE m.release_id=:id AND NOT EXISTS
        (SELECT 1 FROM kb.chunks c WHERE c.version_id=m.version_id)"""),
        {"id": rid},
    )
    if empty:
        raise ValueError("Empty document")
    if missing:
        raise ValueError("Missing embeddings")
    validated = await session.scalar(
        text("""SELECT 1 FROM kb.validations
      WHERE release_id=:id AND passed AND membership_hash=(SELECT
        md5(string_agg(version_id::text,',' ORDER BY version_id))
        FROM kb.members WHERE release_id=:id) LIMIT 1"""),
        {"id": rid},
    )
    if not validated:
        raise ValueError("Golden validation required")
    await session.execute(
        text("""UPDATE kb.releases SET published_at=clock_timestamp()
      WHERE id=:id AND published_at IS NULL"""),
        {"id": rid},
    )
    await session.execute(
        text("UPDATE kb.active_release SET release_id=:id,version=version+1 WHERE id=1"),
        {"id": rid},
    )

    await session.execute(
        text("""INSERT INTO app.audit_logs
      (id,actor_role,action,entity_type,entity_id) VALUES
      (:id,'system','knowledge.publish','knowledge_release',:entity)"""),
        {"id": uuid4(), "entity": rid},
    )


async def revoke(session: AsyncSession, vid: UUID) -> None:
    if await session.scalar(text("SELECT current_user")) not in (
        "migration_owner",
        "knowledge_publisher",
    ):
        raise PermissionError("Publisher connection required")
    await session.execute(text("SELECT id FROM kb.active_release WHERE id=1 FOR UPDATE"))
    await session.execute(
        text("""UPDATE kb.versions SET revoked_at=COALESCE(revoked_at,clock_timestamp())
      WHERE id=:id"""),
        {"id": vid},
    )

    await session.execute(
        text("""INSERT INTO app.audit_logs
      (id,actor_role,action,entity_type,entity_id) VALUES
      (:id,'system','knowledge.revoke','knowledge_version',:entity)"""),
        {"id": uuid4(), "entity": vid},
    )


async def retrieve(
    session: AsyncSession, rid: UUID, query: str, *, draft: bool = False
) -> list[dict[str, Any]]:
    if draft and await session.scalar(text("SELECT current_user")) not in (
        "migration_owner",
        "knowledge_publisher",
    ):
        raise PermissionError("Draft validation requires publisher")
    vector = await FakeEmbeddings().embed(query)
    validate_vector(vector, 16)
    if not any(vector):
        return []
    rows = (
        (
            await session.execute(
                text("""SELECT c.id,c.version_id,c.body,c.heading,c.content_hash,v.stable_key,
        e.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector) AS distance
      FROM kb.embeddings_fake16 e JOIN kb.chunks c ON c.id=e.chunk_id
      JOIN kb.versions v ON v.id=c.version_id JOIN kb.members m ON m.version_id=v.id
      JOIN kb.releases r ON r.id=m.release_id
      WHERE r.id=:rid AND (r.published_at IS NOT NULL OR :draft) AND r.profile_id='fake-hash-16-v1'
        AND v.revoked_at IS NULL AND v.status='ready'
      ORDER BY distance,c.id LIMIT 12"""),
                {"rid": rid, "vector": json.dumps(vector), "draft": draft},
            )
        )
        .mappings()
        .all()
    )
    counts: dict[UUID, int] = {}
    result = []
    for row in rows:
        if counts.get(row["version_id"], 0) >= 2:
            continue
        counts[row["version_id"]] = counts.get(row["version_id"], 0) + 1
        result.append(dict(row))
        if len(result) == 5:
            break
    return result


async def validate_release(session: AsyncSession, rid: UUID, suite: dict[str, Any]) -> bool:
    if await session.scalar(text("SELECT current_user")) not in (
        "migration_owner",
        "knowledge_publisher",
    ):
        raise PermissionError("Publisher connection required")
    await session.execute(text("SELECT id FROM kb.active_release WHERE id=1 FOR UPDATE"))
    if suite.get("profile") != "fake-hash-16-v1":
        raise ValueError("Incompatible validation profile")
    pending = await session.scalar(
        text("""SELECT count(*) FROM kb.members m
      JOIN kb.versions v ON v.id=m.version_id WHERE m.release_id=:id
        AND (v.status<>'ready' OR v.revoked_at IS NOT NULL)"""),
        {"id": rid},
    )
    if pending:
        raise ValueError("Corpus is not ready for validation")
    cases = suite.get("golden", [])
    if not cases:
        raise ValueError("Golden queries required")
    passed = True
    for case in cases:
        rows = await retrieve(session, rid, case["query"], draft=True)
        passed = passed and bool(rows) and rows[0]["stable_key"] == case["expected"]
    await session.execute(
        text("""INSERT INTO kb.validations
      (release_id,suite_hash,sample_count,passed,membership_hash)
      SELECT :id,:hash,:count,:passed,md5(string_agg(version_id::text,',' ORDER BY version_id))
      FROM kb.members WHERE release_id=:id
      ON CONFLICT DO NOTHING"""),
        {
            "id": rid,
            "hash": digest(json.dumps(suite, sort_keys=True)),
            "count": len(cases),
            "passed": passed,
        },
    )
    return passed

"""Authorized frozen retrieval and one revocation projection for all readers."""

import json
import time
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthError
from app.knowledge.corpus import digest
from app.knowledge.service import retrieve


async def ensure_training(session: AsyncSession, run: UUID) -> None:
    # Exam attempts are blind: retrieval and generation are training-only paths.
    if not await session.scalar(text("SELECT app.is_training_run(:run)"), {"run": run}):
        raise AuthError(403, "AI_UNAVAILABLE_IN_EXAM")


async def revoked(session: AsyncSession, release: UUID | None) -> bool:
    return bool(
        release
        and await session.scalar(text("SELECT kb.release_revoked(:release)"), {"release": release})
    )


async def retrieval_view(
    session: AsyncSession, row: Mapping[Any, Any]
) -> tuple[dict[str, Any] | None, bool]:
    # Centralize revocation projection so list/detail/source responses hide the
    # same withdrawn citations instead of implementing separate checks per route.
    release = row["knowledge_release_id"]
    if release is None:
        return None, False
    withdrawn = bool(
        await session.scalar(text("SELECT kb.analysis_revoked(:id)"), {"id": row["id"]})
    )
    status = await session.scalar(
        text("SELECT status FROM app.retrievals WHERE analysis_id=:id"), {"id": row["id"]}
    )
    items = (
        []
        if withdrawn
        else (
            await session.execute(
                text("""SELECT id AS retrieval_item_id,
        document_title,document_version,heading,excerpt_snapshot AS excerpt,content_hash
        FROM app.retrieval_items WHERE run_id=:run AND analysis_id=:id ORDER BY rank"""),
                {"run": row["run_id"], "id": row["id"]},
            )
        )
        .mappings()
        .all()
    )
    return {
        "status": "revoked" if withdrawn else status or "unavailable",
        "release_id": release,
        "config_version": row["retrieval_config_version"],
        "citations": [dict(item) for item in items],
    }, withdrawn


async def source(session: AsyncSession, run: UUID, analysis: UUID, item: UUID) -> dict[str, Any]:
    row = (
        (
            await session.execute(
                text("""SELECT a.knowledge_release_id,i.id AS retrieval_item_id,
        i.document_title,i.document_version,i.heading,i.excerpt_snapshot AS excerpt,i.content_hash
        FROM app.retrieval_items i JOIN app.analyses a ON a.run_id=i.run_id AND a.id=i.analysis_id
        WHERE i.run_id=:run AND i.analysis_id=:analysis AND i.id=:item"""),
                {"run": run, "analysis": analysis, "item": item},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise AuthError(404, "NOT_FOUND")
    if await session.scalar(text("SELECT kb.analysis_revoked(:id)"), {"id": analysis}):
        raise AuthError(410, "KNOWLEDGE_REVOKED")
    return {k: row[k] for k in row if k != "knowledge_release_id"}


async def freeze(
    session: AsyncSession, row: Mapping[Any, Any], query: str, vector: list[float] | None = None
) -> dict[str, Any]:
    # Store the ranked excerpts and config version once; downstream retries read
    # this immutable snapshot instead of changing the evidence basis.
    if await revoked(session, row["knowledge_release_id"]):
        raise AuthError(409, "KNOWLEDGE_REVOKED")
    existing = await session.scalar(
        text("SELECT id FROM app.retrievals WHERE analysis_id=:id"), {"id": row["id"]}
    )
    if existing is None:
        started = time.monotonic()
        results = await retrieve(session, row["knowledge_release_id"], query, vector=vector)
        # The fake profile has no calibrated semantic threshold. Exact fake-vector
        # distance < 1 only rejects orthogonal/negative matches; never a quality claim.
        threshold = await session.scalar(
            text("SELECT max_distance FROM kb.retrieval_policies WHERE release_id=:id"),
            {"id": row["knowledge_release_id"]},
        )
        profile = await session.scalar(
            text("SELECT profile_id FROM kb.releases WHERE id=:id"),
            {"id": row["knowledge_release_id"]},
        )
        if threshold is None and profile == "gemini-embedding-2-768-v1":
            raise ValueError("REAL_RELEVANCE_POLICY_UNAVAILABLE")
        results = [
            r for r in results if r["distance"] < (threshold if threshold is not None else 1.0)
        ]
        # Reserve space for K-ID metadata/JSON escaping within the 3000-byte context cap.
        bounded = []
        size = 0
        for item in results:
            cost = len(json.dumps(item["body"], ensure_ascii=False).encode()) + 200
            if size + cost <= 2800:
                bounded.append(item)
                size += cost
        results = bounded
        retrieval = uuid4()
        await session.execute(
            text("""INSERT INTO app.retrievals
            (id,run_id,analysis_id,release_id,config_version,status,query_hash,latency_ms)
            VALUES (:id,:run,:analysis,:release,:config,:status,:hash,:latency)"""),
            {
                "id": retrieval,
                "run": row["run_id"],
                "analysis": row["id"],
                "release": row["knowledge_release_id"],
                "config": row["retrieval_config_version"],
                "status": "matched" if results else "no_match",
                "hash": digest(query),
                "latency": round((time.monotonic() - started) * 1000),
            },
        )
        for rank, item in enumerate(results, 1):
            metadata = (
                (
                    await session.execute(
                        text("SELECT title,revision FROM kb.versions WHERE id=:id"),
                        {"id": item["version_id"]},
                    )
                )
                .mappings()
                .one()
            )
            await session.execute(
                text("""INSERT INTO app.retrieval_items
                (id,run_id,analysis_id,retrieval_id,chunk_id,version_id,rank,score,
                 excerpt_snapshot,content_hash,document_title,document_version,heading)
                VALUES (:id,:run,:analysis,:retrieval,:chunk,:version,:rank,:score,
                        :excerpt,:hash,:title,:revision,:heading)"""),
                {
                    "id": uuid4(),
                    "run": row["run_id"],
                    "analysis": row["id"],
                    "retrieval": retrieval,
                    "chunk": item["id"],
                    "version": item["version_id"],
                    "rank": rank,
                    "score": 1 - item["distance"],
                    "excerpt": item["body"],
                    "hash": item["content_hash"],
                    "title": metadata["title"],
                    "revision": metadata["revision"],
                    "heading": item["heading"],
                },
            )
    view, _ = await retrieval_view(session, row)
    assert view is not None
    return view


async def copy_retrieval(session: AsyncSession, old: UUID, new: UUID) -> None:
    row = (
        (await session.execute(text("SELECT * FROM app.analyses WHERE id=:id"), {"id": old}))
        .mappings()
        .one()
    )
    if await revoked(session, row["knowledge_release_id"]):
        raise AuthError(409, "KNOWLEDGE_REVOKED")
    retrieval = (
        (
            await session.execute(
                text("SELECT * FROM app.retrievals WHERE analysis_id=:id"), {"id": old}
            )
        )
        .mappings()
        .first()
    )
    if retrieval is None:
        return
    rid = uuid4()
    await session.execute(
        text("""INSERT INTO app.retrievals
        (id,run_id,analysis_id,release_id,config_version,status,query_hash,latency_ms)
        SELECT :rid,run_id,:new,release_id,config_version,status,query_hash,latency_ms
        FROM app.retrievals WHERE analysis_id=:old"""),
        {"rid": rid, "old": old, "new": new},
    )
    items = (
        (
            await session.execute(
                text("SELECT * FROM app.retrieval_items WHERE analysis_id=:old"), {"old": old}
            )
        )
        .mappings()
        .all()
    )
    for item in items:
        columns = [k for k in item if k not in {"id", "analysis_id", "retrieval_id"}]
        values = dict(item) | {"id": uuid4(), "analysis_id": new, "retrieval_id": rid}
        columns = ["id", "analysis_id", "retrieval_id"] + columns
        await session.execute(
            text(
                "INSERT INTO app.retrieval_items ("
                + ",".join(columns)
                + ") VALUES ("
                + ",".join(":" + c for c in columns)
                + ")"
            ),
            values,
        )


async def redact_snapshot(session: AsyncSession, snapshot: dict[str, Any]) -> dict[str, Any]:
    # Do not mutate the immutable evaluation or its metrics. Redact at read time.
    safe: dict[str, Any] = json.loads(json.dumps(snapshot, default=str))
    for analysis in safe.get("analyses", []):
        aid = analysis.get("id")
        if aid and await session.scalar(text("SELECT kb.analysis_revoked(:id)"), {"id": UUID(aid)}):
            analysis["result"] = None
            analysis["question_text"] = None
            analysis["retrieval"] = None
            analysis["response_visibility"] = "withdrawn"
    return safe

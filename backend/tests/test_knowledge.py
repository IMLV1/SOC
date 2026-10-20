import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.session import Database
from app.knowledge.corpus import chunks, digest, load_manifest
from app.knowledge.service import admit, publish, retrieve, revoke, validate_release
from app.worker.jobs import process_one

ROOT = Path(__file__).resolve().parents[1] / "knowledge"


def test_utf8_chunk_boundaries_and_manifest_scope(tmp_path):
    body = "# ภาษาไทย\n" + "ตรวจหลักฐานก่อนสรุปผล " * 100
    raw = body.encode()
    parts = chunks(body, 100, 20)
    assert len(parts) > 2
    assert parts == chunks(body, 100, 20)
    for item in parts:
        assert raw[item["start_byte"] : item["end_byte"]].decode() == item["body"]
        assert len(item["body"].encode()) <= 100
        assert digest(item["body"]) == item["content_hash"]
    assert parts[0]["start_byte"] == 0 and parts[-1]["end_byte"] == len(raw)
    manifest = json.loads((ROOT / "manifest.json").read_text())
    manifest["documents"][0]["path"] = "../docs/srs.md"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_manifest(tmp_path / "manifest.json")
    assert len(load_manifest(ROOT / "manifest.json")) == 2


@pytest.mark.integration
def test_ingestion_publish_revoke_and_acl(migrated):
    async def run():
        owner = Database(migrated("migration_owner"))
        worker = Database(migrated("worker_runtime"))
        api = Database(migrated("api_runtime"))
        try:
            docs = load_manifest(ROOT / "manifest.json")
            async with owner.sessions() as s, s.begin():
                await s.execute(text("SET LOCAL ROLE knowledge_publisher"))
                rid = await admit(s, docs)
                assert await admit(s, docs) == rid
            with pytest.raises(ValueError, match="Partial"):
                async with owner.sessions() as s, s.begin():
                    await publish(s, rid, 1)
            for _ in range(2):
                assert await process_one(worker, "kb-test")
            async with owner.sessions() as s, s.begin():
                await s.execute(text("SET LOCAL ROLE knowledge_publisher"))
                assert await s.scalar(text("SELECT count(*) FROM kb.ingestions")) == 2
                assert (
                    await s.scalar(text("SELECT count(*) FROM kb.versions WHERE status='ready'"))
                    == 2
                )
                assert await validate_release(
                    s,
                    rid,
                    json.loads(
                        (Path(__file__).parent / "knowledge_queries.json").read_text(
                            encoding="utf-8"
                        )
                    ),
                )
                await publish(s, rid, 1)
            with pytest.raises(ValueError, match="conflict"):
                async with owner.sessions() as s, s.begin():
                    await publish(s, rid, 1)
            async with worker.sessions() as s:
                assert await retrieve(s, uuid4(), "authentication") == []
                suites = json.loads(
                    (Path(__file__).parent / "knowledge_queries.json").read_text(encoding="utf-8")
                )
                for split in ("golden", "held_out"):
                    for case in suites[split]:
                        results = await retrieve(s, rid, case["query"])
                        assert results
                        assert case["expected"] in [row["stable_key"] for row in results[:1]]
            with pytest.raises(DBAPIError):
                async with owner.sessions() as s, s.begin():
                    await s.execute(text("SET LOCAL ROLE knowledge_publisher"))
                    await s.execute(text("SELECT * FROM private.ground_truth"))
            with pytest.raises(DBAPIError):
                async with worker.sessions() as s, s.begin():
                    await s.execute(text("UPDATE kb.active_release SET release_id=NULL"))
            with pytest.raises(DBAPIError):
                async with worker.sessions() as s:
                    await s.execute(text("SELECT * FROM private.ground_truth"))
            with pytest.raises(DBAPIError):
                async with api.sessions() as s:
                    await s.execute(text("SELECT body FROM kb.versions"))
            async with owner.sessions() as s, s.begin():
                vid = await s.scalar(text("SELECT id FROM kb.versions WHERE stable_key='blocked'"))
                await revoke(s, vid)
                await revoke(s, vid)
            async with worker.sessions() as s:
                results = await retrieve(s, rid, "blocked")
                assert all(row["version_id"] != vid for row in results)
        finally:
            await owner.close()
            await worker.close()
            await api.close()

    asyncio.run(run())


@pytest.mark.integration
def test_run_refuses_legacy_local_knowledge_until_dify_is_integrated(migrated, monkeypatch):
    from test_investigation_pipeline import prepare

    from app.auth.service import AuthError
    from app.runs.service import start_run

    async def run():
        user, selection = await prepare(migrated)
        api = Database(migrated("api_runtime"))
        try:
            monkeypatch.setenv("SOC_KB_ENABLED", "true")
            with pytest.raises(AuthError, match="DIFY_RAG_ADAPTER_UNAVAILABLE"):
                async with api.sessions() as session, session.begin():
                    await start_run(session, user, selection, uuid4())
            async with api.sessions() as session:
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM app.runs WHERE owner_user_id=:user"),
                        {"user": user},
                    )
                    == 0
                )
        finally:
            await api.close()

    asyncio.run(run())


@pytest.mark.integration
def test_ingestion_stale_worker_rolls_back_chunks(migrated, monkeypatch):
    from app.analysis.fake_embeddings import FakeEmbeddings
    from app.knowledge.service import ingest
    from app.worker.fencing import LeaseLost
    from app.worker.jobs import claim

    async def run():
        owner = Database(migrated("migration_owner"))
        worker = Database(migrated("worker_runtime"))
        original = FakeEmbeddings.embed
        try:
            async with owner.sessions() as s, s.begin():
                await admit(s, load_manifest(ROOT / "manifest.json"))
            job = await claim(worker, "stale-ingestor")
            assert job and job["type"] == "ingest_knowledge"

            async def expire(self, body):
                async with owner.sessions() as s, s.begin():
                    await s.execute(
                        text(
                            "UPDATE app.jobs SET "
                            "lease_expires_at=clock_timestamp()-interval '1 second' "
                            "WHERE id=:id"
                        ),
                        {"id": job["id"]},
                    )
                return await original(self, body)

            monkeypatch.setattr(FakeEmbeddings, "embed", expire)
            with pytest.raises(LeaseLost):
                await ingest(worker, job)
            async with owner.sessions() as s:
                assert await s.scalar(text("SELECT count(*) FROM kb.chunks")) == 0
                assert (
                    await s.scalar(text("SELECT count(*) FROM kb.versions WHERE status='ready'"))
                    == 0
                )
        finally:
            await owner.close()
            await worker.close()

    asyncio.run(run())

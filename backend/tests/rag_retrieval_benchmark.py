"""Manual trusted retrieval benchmark; one bounded real embedding batch, never CI."""

import argparse
import asyncio
import json
import time
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import URL, text

from app.analysis.fake_embeddings import validate_vector
from app.db.session import Database
from app.knowledge.corpus import digest
from app.knowledge.gemini import PROFILE, dispatch
from app.knowledge.service import retrieve


async def evaluate(session, release, cases, vectors, threshold):
    if len(cases) != len(vectors):
        raise ValueError("Embedding count mismatch")
    records = []
    for case, vector in zip(cases, vectors, strict=True):
        validate_vector(vector, 768)
        started = time.monotonic()
        candidates = await retrieve(session, release, case["query"], vector=vector)
        selected = [r for r in candidates if r["distance"] < threshold]
        expected = case["expected"]
        rank = next((i for i, r in enumerate(selected, 1) if r["stable_key"] == expected), None)
        records.append(
            {
                **case,
                "retrieved": [
                    {
                        "chunk_id": str(r["id"]),
                        "version_id": str(r["version_id"]),
                        "stable_key": r["stable_key"],
                        "distance": r["distance"],
                        "content_hash": r["content_hash"],
                    }
                    for r in selected
                ],
                "recall_at_5": int(rank is not None) if expected is not None else None,
                "reciprocal_rank": 1 / rank if rank else 0 if expected is not None else None,
                "no_match": not selected,
                "retrieval_latency_ms": round((time.monotonic() - started) * 1000),
            }
        )
    return records


async def run(args):
    if args.output.exists():
        raise ValueError("Refusing to overwrite benchmark evidence or replay its dispatch")
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    cases = suite["cases"]
    if len(cases) != 50 or any(
        sum(c["language"] == lang for c in cases) != 25 for lang in ("en", "th")
    ):
        raise ValueError("Need 50 frozen bilingual cases")
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate case identity")
    url = URL.create(
        "postgresql+asyncpg",
        username="worker_runtime",
        password=(args.secrets / "worker_runtime.txt").read_text().strip(),
        host="127.0.0.1",
        port=args.port,
        database="soc_test_rag14_real",
    )
    database = Database(url)
    report = {
        "mode": "real",
        "profile": PROFILE,
        "release_id": str(args.release),
        "suite_sha256": digest(json.dumps(suite, sort_keys=True)),
        "status": "pending",
        "human_reviewed": False,
        "scope": "retrieval only, not no-RAG/RAG answer quality acceptance",
    }
    # Persist the frozen configuration before any external dispatch.
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    try:
        async with database.sessions() as s:
            threshold = await s.scalar(
                text("SELECT max_distance FROM kb.retrieval_policies WHERE release_id=:id"),
                {"id": args.release},
            )
            if threshold is None:
                raise ValueError("Frozen calibration required")
        started = time.monotonic()
        response = await dispatch(
            database,
            uuid4(),
            "query_embedding",
            {
                "requests": [
                    {
                        "model": "models/gemini-embedding-2",
                        "content": {"parts": [{"text": c["query"]}]},
                        "outputDimensionality": 768,
                    }
                    for c in cases
                ]
            },
            operation=args.operation,
            method="batchEmbedContents",
        )
        vectors = [item["values"] for item in response["embeddings"]]
        report["embedding_batch_latency_ms"] = round((time.monotonic() - started) * 1000)
        async with database.sessions() as s:
            report["records"] = await evaluate(s, args.release, cases, vectors, threshold)
            catalog = (
                (
                    await s.execute(
                        text("""SELECT c.id AS chunk_id,c.content_hash,c.body,
                c.version_id,v.stable_key FROM kb.chunks c JOIN kb.versions v ON v.id=c.version_id
                JOIN kb.members m ON m.version_id=v.id WHERE m.release_id=:id ORDER BY c.id"""),
                        {"id": args.release},
                    )
                )
                .mappings()
                .all()
            )
            report["context_catalog"] = [dict(c) for c in catalog]
        report["threshold"] = threshold
        report["metrics"] = {}
        for language in ("en", "th"):
            rows = [r for r in report["records"] if r["language"] == language]
            answerable = [r for r in rows if r["expected"] is not None]
            negatives = [r for r in rows if r["expected"] is None]
            report["metrics"][language] = {
                "answerable": len(answerable),
                "unanswerable": len(negatives),
                "recall_at_5": sum(r["recall_at_5"] for r in answerable) / len(answerable),
                "mrr": sum(r["reciprocal_rank"] for r in answerable) / len(answerable),
                "no_match_unanswerable": sum(r["no_match"] for r in negatives),
            }
        report["status"] = "measured_pending_independent_relevance_review"
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        raise
    finally:
        async with database.sessions() as s:
            call = (
                (
                    await s.execute(
                        text(
                            "SELECT id,operation_key,model_id,status,actual_tokens,"
                            "reserved_tokens,telemetry_json,dispatched_at FROM app.provider_calls "
                            "WHERE operation_key=:key"
                        ),
                        {"key": args.operation},
                    )
                )
                .mappings()
                .first()
            )
            report["call"] = dict(call) if call else None
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
        )
        await database.close()
    print(json.dumps({"status": report["status"], "metrics": report["metrics"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=UUID, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--secrets", type=Path, required=True)
    parser.add_argument("--port", type=int, default=55449)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))

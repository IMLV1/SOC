"""Manual, bounded synthetic acceptance. Labels live only in test/operator assets."""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langsmith import tracing_context
from pydantic import create_model
from sqlalchemy import URL, text

from app.analysis.fake_embeddings import validate_vector
from app.analysis.models import QuestionResult
from app.analysis.provider import AnalysisInput, EvidenceItem
from app.auth.models import Strict
from app.db.bootstrap import bootstrap
from app.db.migrate import migrate
from app.db.session import Database
from app.knowledge.corpus import digest, load_manifest
from app.knowledge.gemini import PROFILE, dispatch, structured
from app.knowledge.generation import POLICY, validate_result
from app.knowledge.real_ingestion import prepare_real
from app.knowledge.service import admit, publish, retrieve, validate_release
from app.worker.jobs import process_one

ROOT = Path(__file__).resolve().parents[1]
GOLD = [
    ("authentication session login evidence", "authentication"),
    ("คำขอถูกปฏิเสธ 403 ยืนยันการเข้าถึงสำเร็จไหม", "blocked"),
    ("How to bake a chocolate cake?", None),
    ("ระยะทางจากโลกถึงดาวอังคารเท่าไร", None),
]
EN_AUTH = [
    "What does a successful session establish?",
    "How should failed logins be correlated?",
    "Can login success identify the attacker?",
    "What should I check after repeated login failures?",
    "Does authentication alone prove data access?",
    "Why confirm activity with the account owner?",
    "Which timestamps should be compared in authentication logs?",
    "How can I relate sessions to later activity?",
    "Should I separate observed login facts from hypotheses?",
    "What is unknown after a session is created?",
]
EN_BLOCK = [
    "Does a denied HTTP request establish compromise?",
    "What does status 403 show?",
    "How should blocked requests be interpreted?",
    "Which response fields distinguish denied and successful requests?",
    "Can a blocked payload prove successful data access?",
    "What evidence is needed after a policy denial?",
    "Should a dangerous URL alone establish successful compromise?",
    "How can I explain a denied request cautiously?",
    "What is the difference between potential and observed impact?",
    "Why check response and subsequent logs?",
]
TH_AUTH = [
    "session สำเร็จบอกอะไรได้บ้าง",
    "ควรเชื่อม login ล้มเหลวอย่างไร",
    "login สำเร็จบอกตัวผู้โจมตีไหม",
    "หลัง login ล้มเหลวหลายครั้งต้องตรวจอะไร",
    "การยืนยันตัวตนพิสูจน์ว่าอ่านข้อมูลแล้วไหม",
    "ทำไมต้องยืนยันกิจกรรมกับเจ้าของบัญชี",
    "เวลาใน authentication logs ควรเทียบอย่างไร",
    "เชื่อม session กับกิจกรรมต่อเนื่องอย่างไร",
    "ควรแยกข้อสังเกต login จากสมมติฐานไหม",
    "หลังสร้าง session ยังไม่รู้อะไร",
]
TH_BLOCK = [
    "HTTP request ถูกปฏิเสธพิสูจน์การเจาะไหม",
    "status 403 บอกอะไร",
    "ควรตีความ blocked request อย่างไร",
    "response field ใดแยกคำขอถูกปฏิเสธกับสำเร็จ",
    "payload ที่ถูก block พิสูจน์การอ่านข้อมูลไหม",
    "หลัง policy denial ต้องหาหลักฐานใดเพิ่ม",
    "URL อันตรายเพียงอย่างเดียวพิสูจน์ compromise ไหม",
    "ควรอธิบาย denied request อย่างระมัดระวังอย่างไร",
    "potential impact ต่างจาก observed impact อย่างไร",
    "ทำไมต้องดู response และ log ต่อเนื่อง",
]
UNKNOWN_EN = [
    "What is tomorrow weather?",
    "What medicine cures a cold?",
    "How to grow tomatoes?",
    "Who won the lunar chess championship?",
    "Which stock will rise tomorrow?",
]
UNKNOWN_TH = [
    "พรุ่งนี้ฝนจะตกไหม",
    "ยาอะไรแก้หวัดได้",
    "ปลูกมะเขือเทศอย่างไร",
    "ใครชนะหมากรุกบนดวงจันทร์",
    "หุ้นใดจะขึ้นพรุ่งนี้",
]
HELD = [
    {"language": lang, "query": q, "expected": expected}
    for lang, queries, expected in [
        ("en", EN_AUTH, "authentication"),
        ("en", EN_BLOCK, "blocked"),
        ("en", UNKNOWN_EN, None),
        ("th", TH_AUTH, "authentication"),
        ("th", TH_BLOCK, "blocked"),
        ("th", UNKNOWN_TH, None),
    ]
    for q in queries
]


async def generate_v1(data, question, snapshot, database, operation):
    # Frozen benchmark schema/prompt from the initial smoke; production metadata
    # additions must not silently change one comparison arm during a resumed run.
    fields: dict[str, Any] = {
        name: (field.annotation, field)
        for name, field in QuestionResult.model_fields.items()
        if name != "omitted_evidence_ids"
    }
    schema = create_model("QuestionResult", __base__=Strict, **fields)
    parser = PydanticOutputParser(pydantic_object=schema)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", POLICY),
            (
                "human",
                "{schema}\nUntrusted question: {question}"
                "\nE-events: {events}\nK-documents: {knowledge}",
            ),
        ]
    )
    if snapshot["status"] == "no_match":
        return QuestionResult(
            answer="Insufficient context / หลักฐานไม่เพียงพอ",
            claims=[],
            unknowns=["No matching approved knowledge"],
            answer_status="insufficient_context",
        )

    async def model(messages):
        return await structured(
            database, data.analysis_id, messages, schema.model_json_schema(), operation=operation
        )

    with tracing_context(enabled=False):
        result = await (prompt | RunnableLambda(model) | parser).ainvoke(
            {
                "schema": parser.get_format_instructions(),
                "question": question,
                "events": json.dumps(
                    [e.model_dump(mode="json", exclude={"username"}) for e in data.evidence],
                    ensure_ascii=False,
                ),
                "knowledge": json.dumps(
                    [
                        {"metadata": {"K-ID": c["retrieval_item_id"]}, "text": c["excerpt"]}
                        for c in snapshot["citations"]
                    ],
                    ensure_ascii=False,
                ),
            },
            config={"callbacks": []},
        )
    result = QuestionResult.model_validate(result.model_dump())
    validate_result(
        result,
        {e.id for e in data.evidence},
        {UUID(c["retrieval_item_id"]) for c in snapshot["citations"]},
    )
    return result


async def run(args):
    secret = Path(args.secrets)

    def url(role):
        return URL.create(
            "postgresql+asyncpg",
            username=role,
            password=(secret / (role + ".txt")).read_text().strip(),
            host="127.0.0.1",
            port=args.port,
            database="soc_test_rag14_real",
        )

    os.environ["SOC_INSTALL_VECTOR"] = "yes"
    await bootstrap(url("postgres"), secret)
    await migrate(url("migration_owner"), "rag14-real")
    owner = Database(url("migration_owner"))
    worker = Database(url("worker_runtime"))
    state = Path(args.output)
    report = (
        json.loads(state.read_text(encoding="utf-8"))
        if state.exists()
        else {
            "mode": "real",
            "profile": PROFILE,
            "chat_model": "gemini-3.5-flash-lite",
            "dataset_hash": digest(json.dumps(HELD, ensure_ascii=False, sort_keys=True)),
            "scope": (
                "synthetic two-document corpus; labels authored for regression; "
                "human review pending"
            ),
            "records": [],
            "benchmark_schema": "question-v1-before-omission-metadata",
        }
    )

    for record in report["records"]:
        if record["status"] in {"ValueError", "ValidationError", "OutputParserException"}:
            record["validation_exception"] = record["status"]
            record["status"] = "invalid_output"

    async def pace():
        async with worker.sessions() as s:
            count = await s.scalar(
                text(
                    "SELECT count(*) FROM app.provider_calls "
                    "WHERE dispatched_at>clock_timestamp()-interval '60 seconds'"
                )
            )
            total = await s.scalar(text("SELECT count(*) FROM app.provider_calls"))
        if total >= args.max_calls:
            raise RuntimeError("OPERATOR_CALL_CAP")
        while count >= 5:
            await asyncio.sleep(15)
            async with worker.sessions() as s:
                count = await s.scalar(
                    text(
                        "SELECT count(*) FROM app.provider_calls "
                        "WHERE dispatched_at>clock_timestamp()-interval '60 seconds'"
                    )
                )

    async def batch(queries, key):
        await pace()
        response = await dispatch(
            worker,
            uuid4(),
            "query_embedding",
            {
                "requests": [
                    {
                        "model": "models/gemini-embedding-2",
                        "content": {"parts": [{"text": q}]},
                        "outputDimensionality": 768,
                    }
                    for q in queries
                ]
            },
            operation=key,
            method="batchEmbedContents",
        )
        vectors = [item["values"] for item in response["embeddings"]]
        if len(vectors) != len(queries):
            raise ValueError("EMBEDDING_COUNT")
        for vector in vectors:
            validate_vector(vector, 768)
        return vectors

    try:
        # Default mock knowledge preparation performs no external calls.
        async with owner.sessions() as s, s.begin():
            fake = await admit(s, load_manifest(ROOT / "knowledge/manifest.json"))
        for _ in range(2):
            await process_one(worker, "benchmark-ingest-fake")
        async with owner.sessions() as s, s.begin():
            rid = await prepare_real(s, fake)
        report["release_id"] = str(rid)
        for _ in range(2):
            await pace()
            await process_one(worker, "benchmark-ingest-real")
        # Two positive and two unrelated golden queries, never the held-out set.
        if "gold_vectors" not in report:
            report["gold_vectors"] = await batch([q for q, _ in GOLD], "rag14:gold-v1")
            state.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        distances = []
        async with owner.sessions() as s, s.begin():
            await s.execute(text("SET LOCAL ROLE knowledge_publisher"))
            for (query, expected), vector in zip(GOLD, report["gold_vectors"], strict=True):
                rows = await retrieve(s, rid, query, draft=True, vector=vector)
                distances.append(rows[0]["distance"])
                if expected and rows[0]["stable_key"] != expected:
                    raise ValueError("GOLDEN_TOP1_FAILED")
            if max(distances[:2]) >= min(distances[2:]):
                raise ValueError("GOLDEN_RELEVANCE_NOT_SEPARABLE")
            threshold = (max(distances[:2]) + min(distances[2:])) / 2
            await s.execute(
                text("""INSERT INTO kb.retrieval_policies VALUES (:rid,:threshold,:hash)
                ON CONFLICT DO NOTHING"""),
                {
                    "rid": rid,
                    "threshold": threshold,
                    "hash": digest(json.dumps(GOLD, ensure_ascii=False)),
                },
            )
            suite = {
                "profile": PROFILE,
                "golden": [{"query": q, "expected": e} for q, e in GOLD[:2]],
            }
            assert await validate_release(s, rid, suite, report["gold_vectors"][:2])
            published = await s.scalar(
                text("SELECT published_at FROM kb.releases WHERE id=:id"), {"id": rid}
            )
            if not published:
                version = await s.scalar(text("SELECT version FROM kb.active_release"))
                await publish(s, rid, version)
        report["threshold"] = threshold
        cases = (
            HELD
            if args.full
            else [
                {"query": q, "expected": e, "language": lang}
                for (q, e), lang in zip(GOLD[:2], ["en", "th"], strict=True)
            ]
        )
        key = "held-v1" if args.full else "smoke-v1"
        if key not in report:
            report[key] = await batch([case["query"] for case in cases], "rag14:" + key)
            state.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        event = uuid5(NAMESPACE_URL, "rag14:blocked-event")
        evidence = EvidenceItem(
            id=event,
            source="web",
            username=None,
            request={"method": "GET", "path": "/restricted"},
            response={"status": 403},
            log={"event_type": "request_policy_denied"},
        )
        for index, (case, vector) in enumerate(zip(cases, report[key], strict=True)):
            async with worker.sessions() as s:
                rows = await retrieve(s, rid, case["query"], vector=vector)
            selected = [r for r in rows if r["distance"] < threshold]
            citations = [
                {"retrieval_item_id": str(uuid5(rid, str(r["id"]))), "excerpt": r["body"]}
                for r in selected
            ]
            for arm in ["no_rag", "rag"]:
                operation = f"rag14:{key}:{index}:{arm}"
                if any(r["operation"] == operation for r in report["records"]):
                    continue
                await pace()
                aid = uuid5(NAMESPACE_URL, operation)
                data = AnalysisInput(
                    analysis_id=aid,
                    evidence=[evidence],
                    prompt_version="rag-v1",
                    max_output_tokens=1200,
                )
                snapshot = {
                    "status": ("matched" if selected else "no_match")
                    if arm == "rag"
                    else "unavailable",
                    "citations": citations if arm == "rag" else [],
                }
                start = time.monotonic()
                try:
                    result = await generate_v1(
                        data, case["query"], snapshot, worker, operation=operation
                    )
                    record = {
                        "operation": operation,
                        "split": key,
                        "index": index,
                        "language": case["language"],
                        "arm": arm,
                        "status": "succeeded",
                        "result": result.model_dump(mode="json"),
                    }
                except Exception as exc:
                    record = {
                        "operation": operation,
                        "split": key,
                        "index": index,
                        "language": case["language"],
                        "arm": arm,
                        "status": "invalid_output"
                        if isinstance(exc, ValueError)
                        else type(exc).__name__,
                        "validation_exception": type(exc).__name__,
                        "result": None,
                    }
                record["latency_ms"] = round((time.monotonic() - start) * 1000)
                record["expected"] = case["expected"]
                record["retrieved"] = [r["stable_key"] for r in selected]
                report["records"].append(record)
                state.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(
                    json.dumps(
                        {k: record[k] for k in ("split", "index", "language", "arm", "status")}
                    ),
                    flush=True,
                )
                # User explicitly authorized collecting validation failures as
                # failures and continuing other cases. Never publish raw output.
                if record["status"] not in {"succeeded", "invalid_output"}:
                    raise RuntimeError("BOUNDED_BENCHMARK_STOPPED")
    finally:
        async with worker.sessions() as s:
            calls = (
                (
                    await s.execute(
                        text(
                            "SELECT id,operation_key,component,model_id,status,"
                            "reserved_tokens,actual_tokens,"
                            "dispatched_at FROM app.provider_calls ORDER BY dispatched_at"
                        )
                    )
                )
                .mappings()
                .all()
            )
            report["calls"] = [dict(c) for c in calls]
            report["measured_cost_usd"] = (
                None if any(c["status"] == "unknown" for c in calls) else 0
            )
        state.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        await owner.close()
        await worker.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--secrets", required=True)
    parser.add_argument("--port", type=int, default=55449)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-calls", type=int, default=12)
    parser.add_argument("--full", action="store_true")
    try:
        asyncio.run(run(parser.parse_args()))
    except Exception as exc:
        raise SystemExit("Acceptance stopped: " + type(exc).__name__) from None

"""A frozen exam is graded by the evaluator using the shared Dify workflow."""

import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_exam_integration import prepare_exam

from app.auth import service as auth
from app.db.session import Database
from app.evaluation.__main__ import process_one as evaluate_one
from app.knowledge.dify_client import DifyConfig
from app.knowledge.dify_workflow import WorkflowReply
from app.learning.catalog import LEVEL_ID
from app.main import app
from app.worker.jobs import process_one as release_one


@pytest.mark.integration
def test_submitted_exam_is_graded_and_finalized_without_instructor(migrated, monkeypatch):
    users, tokens = asyncio.run(prepare_exam(migrated))
    analyst_token = tokens[0]
    workflow = str(uuid4())

    async def enable_policy():
        owner = Database(migrated("migration_owner"))
        try:
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("""UPDATE app.tutor_policy SET enabled=true,
                    cost_bound_verified=true,exam_grade_enabled=true,
                    workflow_id=:workflow,corpus_revision='test-approved',
                    document_ids=CAST(:documents AS jsonb),
                    chunk_hashes=CAST(:hashes AS jsonb),
                    exam_grade_call_bound_usd=0.001 WHERE id=1"""),
                    {
                        "workflow": workflow,
                        "documents": json.dumps([str(uuid4())]),
                        "hashes": json.dumps(["a" * 64]),
                    },
                )
        finally:
            await owner.close()

    asyncio.run(enable_policy())
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setattr(
        DifyConfig,
        "from_env",
        classmethod(lambda cls: cls("https://api.dify.ai/v1", Path("/unused"))),
    )

    async def fake_workflow(config, workflow_id, question, user, *, mode):
        assert workflow_id == workflow and mode == "exam_grade"
        data = json.loads(question)
        assert "private_truth" not in question and "expected_evidence_keys" not in question
        event_ids = [item["id"] for item in data["events"]]
        assert event_ids
        return WorkflowReply(
            {
                "answer": json.dumps(
                    {
                        "analysis_score": 2,
                        "reasoning_score": 2,
                        "analysis_feedback": "อธิบายหลักฐานและข้อจำกัดได้ชัดเจน",
                        "reasoning_feedback": "เชื่อมเหตุผลกับ event ที่พบ",
                        "evidence_refs": [event_ids[0]],
                        "section_ids": [],
                    }
                ),
                "sources": [],
            },
            120,
            str(uuid4()),
        )

    monkeypatch.setattr("app.grading.exam_ai.run_workflow", fake_workflow)
    with TestClient(app, headers={"Origin": "http://testserver"}) as learner:
        learner.cookies.set(auth.SESSION, analyst_token)
        headers = {"X-CSRF-Token": auth.csrf(analyst_token)}
        started = learner.post(
            f"/api/v1/learning/levels/{LEVEL_ID}/attempts",
            json={"expected_progress_version": 1},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert started.status_code == 201, started.text
        attempt = started.json()["data"]
        attempt_id = UUID(attempt["id"])
        run_id = UUID(attempt["run_id"])

        async def release_events():
            owner = Database(migrated("migration_owner"))
            worker = Database(migrated("worker_runtime"))
            try:
                async with owner.sessions() as session, session.begin():
                    await session.execute(
                        text("""UPDATE app.runs
                        SET resumed_at=clock_timestamp()-interval '60 seconds'
                        WHERE id=:run"""),
                        {"run": run_id},
                    )
                for _ in range(5):
                    if not await release_one(worker, "exam-ai-release"):
                        break
            finally:
                await owner.close()
                await worker.close()

        asyncio.run(release_events())
        visible = learner.get(f"/api/v1/exam/attempts/{attempt_id}")
        assert visible.status_code == 200, visible.text

        async def expected_answer():
            owner = Database(migrated("migration_owner"))
            try:
                async with owner.sessions() as session:
                    truth = (
                        (
                            await session.execute(
                                text("""SELECT t.expected_evidence_keys,t.expected_severity,
                            t.expected_disposition FROM app.exam_attempts a
                            JOIN private.exam_case_truths t ON t.case_id=a.case_id
                            WHERE a.id=:attempt ORDER BY t.version DESC LIMIT 1"""),
                                {"attempt": attempt_id},
                            )
                        )
                        .mappings()
                        .one()
                    )
                    events = (
                        (
                            await session.execute(
                                text("""SELECT id,fixture_event_key FROM app.events
                            WHERE run_id=:run"""),
                                {"run": run_id},
                            )
                        )
                        .mappings()
                        .all()
                    )
                expected = set(truth["expected_evidence_keys"])
                return (
                    [
                        str(event["id"])
                        for event in events
                        if event["fixture_event_key"] in expected
                    ],
                    truth["expected_severity"],
                    truth["expected_disposition"],
                )
            finally:
                await owner.close()

        evidence, severity, disposition = asyncio.run(expected_answer())
        assert evidence
        submitted = learner.post(
            f"/api/v1/exam/attempts/{attempt_id}/submit",
            json={
                "expected_version": attempt["version"],
                "evidence_event_ids": evidence,
                "severity": severity,
                "disposition": disposition,
                "reason": "ตอบ 401 จึงยังยืนยัน login สำเร็จไม่ได้ ควรตรวจ event ถัดไป",
            },
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["data"]["status"] == "submitted"

        evaluator = Database(migrated("evaluator_runtime"))
        try:
            assert asyncio.run(evaluate_one(evaluator, "exam-ai-test"))
        finally:
            asyncio.run(evaluator.close())

        result = learner.get(f"/api/v1/exam/attempts/{attempt_id}/result")
        assert result.status_code == 200, result.text
        assert result.json()["data"]["status"] == "passed"
        assert result.json()["data"]["score"] == 8

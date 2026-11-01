"""Dify ticket question admission, frozen evidence, quota and revocation on PostgreSQL."""

import asyncio
import hashlib
import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_investigation_pipeline import issue_session, prepare, release_all

from app.analysis.worker import analyze_job
from app.auth import service as auth
from app.db.session import Database
from app.knowledge.dify_workflow import WorkflowReply
from app.main import app
from app.runs.service import start_run
from app.worker.jobs import claim, settle


@pytest.mark.integration
def test_dify_ticket_questions_freeze_question_evidence_and_reject_drift(
    migrated, monkeypatch, tmp_path
):
    context = "## SOC-003 — HTTP response\n403 แสดงการปฏิเสธคำขอ"
    key = tmp_path / "dify.key"
    key.write_text("test-only", encoding="utf-8")
    monkeypatch.setenv("DIFY_APP_KEY_FILE", str(key))
    monkeypatch.setenv("SOC_AI_PROVIDER", "dify")
    monkeypatch.setenv("SOC_KB_ENABLED", "false")
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    calls = []

    async def fake_workflow(config, workflow_id, question, user, mode):
        payload = json.loads(question)
        calls.append(payload)
        refs = [item["id"] for item in payload["evidence"]]
        return WorkflowReply(
            {
                "answer": json.dumps(
                    {
                        "summary": "ข้อมูลยังไม่พอยืนยันผลกระทบ SOC-003",
                        "hypotheses": [],
                        "evidence_refs": refs,
                        "knowledge_refs": [],
                        "observed_impact": "ดูหลักฐาน",
                        "potential_impact": "ยังไม่ทราบ",
                        "suggested_severity": {"level": "low", "reason": "หลักฐานจำกัด"},
                        "confidence": {"level": "low", "reason": "ยังไม่ทราบบริบท"},
                        "unknowns": ["เหตุผลของกิจกรรม"],
                        "recommended_checks": ["ตรวจ log เพิ่ม"],
                    }
                ),
                "sources": [{"content": context, "metadata": {"document_id": "approved"}}],
            },
            42,
            "synthetic-run",
        )

    monkeypatch.setattr("app.analysis.dify_provider.run_workflow", fake_workflow)

    async def setup():
        user, selection = await prepare(migrated)
        owner = Database(migrated("migration_owner"))
        api = Database(migrated("api_runtime"))
        worker = Database(migrated("worker_runtime"))
        try:
            async with owner.sessions() as session, session.begin():
                await session.execute(
                    text("""UPDATE app.tutor_policy SET enabled=true,
                    cost_bound_verified=true,analysis_enabled=true,analysis_call_bound_usd=0.01,
                    workflow_id='approved-workflow',corpus_revision='ticket-test',
                    document_ids='["approved"]'::jsonb,chunk_hashes=CAST(:hashes AS jsonb)
                    WHERE id=1"""),
                    {"hashes": json.dumps([hashlib.sha256(context.encode()).hexdigest()])},
                )
            async with api.sessions() as session, session.begin():
                run, _ = await start_run(session, user, selection, uuid4())
            run_id = UUID(run["id"])
            await release_all(api, worker, run_id)
            async with api.sessions() as session:
                ticket = (
                    (
                        await session.execute(
                            text("SELECT id,version FROM app.tickets WHERE run_id=:run LIMIT 1"),
                            {"run": run_id},
                        )
                    )
                    .mappings()
                    .one()
                )
            return run_id, dict(ticket), await issue_session(migrated, user)
        finally:
            await owner.close()
            await api.close()
            await worker.close()

    run_id, ticket, token = asyncio.run(setup())
    calls.clear()
    path = f"/api/v1/runs/{run_id}/tickets/{ticket['id']}/questions"
    body = {"question": "ควรตรวจอะไรเพิ่ม?", "expected_version": ticket["version"]}
    headers = {"X-CSRF-Token": auth.csrf(token), "Idempotency-Key": str(uuid4())}
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.cookies.set(auth.SESSION, token)
        queued = client.post(path, json=body, headers=headers)
        assert queued.status_code == 202, queued.text
        item = queued.json()["data"]
        assert item["mode"] == "real" and item["kind"] == "question"
        assert client.post(path, json=body, headers=headers).json()["data"]["id"] == item["id"]
        assert (
            client.post(path, json=body | {"question": "changed"}, headers=headers).status_code
            == 409
        )
        assert client.post(path, json=body).status_code == 403

        async def execute():
            worker = Database(migrated("worker_runtime"))
            try:
                job = await claim(worker, "ticket-test")
                assert job is not None and job["payload"]["analysis_id"] == item["id"]
                await analyze_job(worker, job)
                assert await settle(worker, job)
            finally:
                await worker.close()

        asyncio.run(execute())
        result = client.get(f"/api/v1/runs/{run_id}/analyses/{item['id']}").json()["data"]
        assert result["status"] == "succeeded", result
        assert len(calls) == 1 and calls[0]["question"] == body["question"]
        assert {e["id"] for e in calls[0]["evidence"]} == set(item["evidence_ids"])
        client.cookies.set(auth.SESSION, str(uuid4()))
        # Mutations check CSRF before require_user; a stale token cannot pass either boundary.
        rejected = client.post(path, json=body, headers=headers)
        assert rejected.status_code == 403 and rejected.json()["error"]["code"] == "CSRF_INVALID"
        assert client.get(f"/api/v1/runs/{run_id}/analyses/{item['id']}").status_code == 401
        client.cookies.set(auth.SESSION, token)

        async def revoke():
            owner = Database(migrated("migration_owner"))
            try:
                async with owner.sessions() as session, session.begin():
                    await session.execute(
                        text("UPDATE app.tutor_policy SET analysis_enabled=false WHERE id=1")
                    )
            finally:
                await owner.close()

        asyncio.run(revoke())
        hidden = client.get(f"/api/v1/runs/{run_id}/analyses/{item['id']}").json()["data"]
        assert hidden["response_visibility"] == "withdrawn" and hidden["result"] is None
        assert (
            client.post(
                path, json=body, headers=headers | {"Idempotency-Key": str(uuid4())}
            ).status_code
            == 503
        )
        # Replay must also respect revocation instead of leaking the cached result.
        replay = client.post(path, json=body, headers=headers).json()["data"]
        assert replay["response_visibility"] == "withdrawn" and replay["result"] is None

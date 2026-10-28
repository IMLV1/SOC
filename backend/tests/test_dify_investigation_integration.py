import asyncio
import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_investigation_pipeline import prepare

from app.analysis.dify_provider import DifyAnalysisFailure, DifyAnalysisReply
from app.analysis.investigation_budget import committed_usd, reserve_usd, settle_usd
from app.analysis.investigation_config import release_snapshot
from app.analysis.provider import MockProvider
from app.analysis.service import analysis_view, enqueue_analysis
from app.analysis.worker import analyze_job
from app.db.session import Database
from app.evaluation.worker import finalize
from app.knowledge.dify_client import DifyUnavailable
from app.knowledge.rag import redact_snapshot
from app.learning.catalog import LESSON_ID
from app.learning.seed import seed as seed_learning
from app.runs.service import finish_run, start_run
from app.worker.jobs import process_one, settle

pytestmark = pytest.mark.integration


async def setup(migrated):
    user, selection = await prepare(migrated)
    api, worker, owner = [
        Database(migrated(role)) for role in ("api_runtime", "worker_runtime", "migration_owner")
    ]
    async with api.sessions() as s, s.begin():
        run, _ = await start_run(s, user, selection, uuid4())
    run_id = UUID(run["id"])
    assert await process_one(worker, "release-only")
    async with api.sessions() as s:
        event = await s.scalar(
            text("SELECT id FROM app.events WHERE run_id=:run LIMIT 1"), {"run": run_id}
        )
    assert event
    return user, run_id, event, api, worker, owner


async def enqueue(api, worker, user, run, event):
    async with api.sessions() as s, s.begin():
        aid = await enqueue_analysis(s, run, user, str(uuid4()), str(uuid4()), [event])
    async with worker.sessions() as s, s.begin():
        job = (
            (
                await s.execute(
                    text("""UPDATE app.jobs SET status='running',attempts=1,
            locked_by='integration-test',lease_token=:token,
            lease_expires_at=clock_timestamp()+interval '60 seconds'
            WHERE payload->>'analysis_id'=:analysis RETURNING *"""),
                    {"token": uuid4(), "analysis": str(aid)},
                )
            )
            .mappings()
            .one()
        )
    return aid, dict(job)


async def close_all(*dbs):
    for db in dbs:
        await db.close()


def test_worker_persists_aggregate_usage_and_revokes_all_read_projections(
    migrated, investigation_release, monkeypatch
):
    _, review, path = investigation_release
    calls = []

    async def fake(config, workflow, data):
        calls.append(data.analysis_id)
        result = (await MockProvider().analyze(data)).result
        return DifyAnalysisReply(result, 42, "synthetic-provider-run")

    monkeypatch.setattr("app.analysis.dify_provider.analyze", fake)

    async def run():
        user, rid, event, api, worker, owner = await setup(migrated)
        try:
            aid, job = await enqueue(api, worker, user, rid, event)
            await analyze_job(worker, job)
            await analyze_job(worker, job)
            assert await settle(worker, job)
            assert calls == [aid]
            async with api.sessions() as s:
                row = (
                    (await s.execute(text("SELECT * FROM app.analyses WHERE id=:id"), {"id": aid}))
                    .mappings()
                    .one()
                )
                view = await analysis_view(s, row)
                assert view["status"] == "succeeded" and view["result"]
                assert view["usage"]["input_tokens"] is None
                assert view["usage"]["output_tokens"] is None
                assert view["usage"]["total_tokens"] == 42
                pin = await s.scalar(
                    text(
                        "SELECT config_snapshot->'investigation' FROM app.run_versions "
                        "WHERE run_id=:id"
                    ),
                    {"id": rid},
                )
                path.write_text(json.dumps(review | {"model_id": "changed"}), encoding="utf8")
                assert (await analysis_view(s, row))["result"] is None
                exported = await redact_snapshot(
                    s, {"analyses": [{"id": str(aid), "mode": "real", "result": view["result"]}]}
                )
                assert exported["analyses"][0]["response_visibility"] == "withdrawn"
                assert exported["analyses"][0]["result"] is None
                assert pin["model_id"] == review["model_id"]
            aid2, job2 = await enqueue(api, worker, user, rid, event)
            await analyze_job(worker, job2)
            assert await settle(worker, job2)
            assert calls == [aid]
            async with api.sessions() as s:
                assert await s.scalar(text("SELECT count(*) FROM app.investigation_calls")) == 1
                assert (
                    await s.scalar(
                        text(
                            "SELECT usage_status FROM app.investigation_calls WHERE analysis_id=:id"
                        ),
                        {"id": aid},
                    )
                    == "reconciled"
                )
                assert (
                    await s.scalar(
                        text("SELECT status FROM app.analyses WHERE id=:id"), {"id": aid2}
                    )
                    == "failed"
                )
            async with api.sessions() as s, s.begin():
                version = await s.scalar(
                    text("SELECT version FROM app.runs WHERE id=:id"), {"id": rid}
                )
                await finish_run(s, rid, user, version)
            for _ in range(10):
                if not await process_one(worker, "drain-revoked-run"):
                    break
            evaluator = Database(migrated("evaluator_runtime"))
            try:
                async with evaluator.sessions() as s, s.begin():
                    assert await finalize(s, rid)
                async with owner.sessions() as s:
                    frozen = await s.scalar(
                        text("SELECT snapshot_json FROM app.evaluations WHERE run_id=:id"),
                        {"id": rid},
                    )
                    entry = next(a for a in frozen["analyses"] if a["id"] == str(aid))
                    assert entry["result"] is None and entry["response_visibility"] == "withdrawn"
            finally:
                await evaluator.close()
        finally:
            await close_all(api, worker, owner)

    asyncio.run(run())


def test_tutor_and_investigation_race_share_one_usd_cap(
    migrated, investigation_release, monkeypatch, tmp_path
):
    from app.auth.service import AuthError
    from app.tutor.service import admit

    key = tmp_path / "tutor-key"
    key.write_text("synthetic-tutor-key", encoding="utf8")
    monkeypatch.setenv("DIFY_APP_KEY_FILE", str(key))

    async def run():
        user, rid, event, api, worker, owner = await setup(migrated)
        try:
            await seed_learning(owner)
            async with owner.sessions() as s, s.begin():
                await s.execute(
                    text("""UPDATE app.tutor_policy SET enabled=true,
                    cost_bound_verified=true,workflow_id='synthetic-workflow',
                    corpus_revision='test',document_ids='["doc"]',chunk_hashes='["hash"]',
                    call_bound_usd=0.15""")
                )
            aid, _ = await enqueue(api, worker, user, rid, event)
            snapshot = release_snapshot() | {"call_bound_usd": "0.15"}

            async def investigation():
                async with worker.sessions() as s, s.begin():
                    return await reserve_usd(s, aid, snapshot)

            async def tutor():
                try:
                    async with api.sessions() as s, s.begin():
                        await admit(s, user, LESSON_ID, "synthetic question", uuid4())
                    return True
                except AuthError as error:
                    assert error.status == 429
                    return False

            assert sorted(await asyncio.gather(investigation(), tutor())) == [False, True]
            async with worker.sessions() as s:
                assert await committed_usd(s) == Decimal("0.15")
        finally:
            await close_all(api, worker, owner)

    asyncio.run(run())


@pytest.mark.parametrize(
    "outcome",
    [
        "timeout",
        "crash",
        "version_mismatch",
        "unknown_success",
        "known_zero",
        "invalid_output",
        "revoke_during_call",
        "lease_lost",
    ],
)
def test_unknown_holds_and_crash_recovery_never_dispatch_twice(
    migrated, investigation_release, monkeypatch, outcome
):
    calls = []
    _, review, path = investigation_release

    class Crash(BaseException):
        pass

    async def fake(config, workflow, data):
        calls.append(data.analysis_id)
        if outcome == "timeout":
            raise TimeoutError()
        if outcome == "crash":
            raise Crash()
        if outcome == "version_mismatch":
            raise DifyUnavailable("DIFY_WORKFLOW_VERSION_MISMATCH")
        if outcome == "invalid_output":
            raise DifyAnalysisFailure("DIFY_ANALYSIS_OUTPUT_INVALID", 42)
        if outcome == "revoke_during_call":
            path.write_text(json.dumps(review | {"status": "withdrawn"}), encoding="utf8")
        if outcome == "lease_lost":
            db = Database(migrated("migration_owner"))
            try:
                async with db.sessions() as s, s.begin():
                    await s.execute(
                        text("""UPDATE app.jobs SET lease_expires_at=now()-interval '1 second'
                        WHERE payload->>'analysis_id'=:id"""),
                        {"id": str(data.analysis_id)},
                    )
            finally:
                await db.close()
        result = (await MockProvider().analyze(data)).result
        tokens = 42 if outcome == "revoke_during_call" else 0 if outcome == "known_zero" else None
        return DifyAnalysisReply(result, tokens, "synthetic-run")

    monkeypatch.setattr("app.analysis.dify_provider.analyze", fake)

    async def run():
        user, rid, event, api, worker, owner = await setup(migrated)
        try:
            aid, job = await enqueue(api, worker, user, rid, event)
            if outcome == "crash":
                with pytest.raises(Crash):
                    await analyze_job(worker, job)
            elif outcome == "lease_lost":
                # lock_domain returns False for an already-expired lease;
                # only expiry after domain work raises LeaseLost. Both must
                # refuse persistence. Assert the durable behavior, not an exception.
                await analyze_job(worker, job)
                async with api.sessions() as s:
                    stale = (
                        await s.execute(
                            text("SELECT status,result_json FROM app.analyses WHERE id=:id"),
                            {"id": aid},
                        )
                    ).one()
                    assert stale.status == "running" and stale.result_json is None
                job["lease_token"] = uuid4()
                async with owner.sessions() as s, s.begin():
                    await s.execute(
                        text("""UPDATE app.jobs SET lease_token=:token,
                        lease_expires_at=now()+interval '60 seconds',attempts=2 WHERE id=:id"""),
                        {"id": job["id"], "token": job["lease_token"]},
                    )
            else:
                await analyze_job(worker, job)
            await analyze_job(worker, job)
            assert calls == [aid]
            async with api.sessions() as s:
                status = await s.scalar(
                    text("SELECT usage_status FROM app.investigation_calls WHERE analysis_id=:id"),
                    {"id": aid},
                )
                assert status == (
                    "reconciled"
                    if outcome in {"known_zero", "invalid_output", "revoke_during_call"}
                    else "unknown"
                )
                if outcome in {"revoke_during_call", "lease_lost"}:
                    assert (
                        await s.scalar(
                            text("SELECT result_json FROM app.analyses WHERE id=:id"), {"id": aid}
                        )
                        is None
                    )
                assert (
                    await s.scalar(
                        text("SELECT count(*) FROM app.analysis_attempts WHERE analysis_id=:id"),
                        {"id": aid},
                    )
                    == 1
                )
            if outcome == "version_mismatch":
                _, second = await enqueue(api, worker, user, rid, event)
                await analyze_job(worker, second)
                assert calls == [aid]
        finally:
            await close_all(api, worker, owner)

    asyncio.run(run())


def test_global_usd_budget_includes_tutor_and_unknown_across_utc_days(
    migrated, investigation_release
):
    async def run():
        user, rid, event, api, worker, owner = await setup(migrated)
        try:
            await seed_learning(owner)
            async with owner.sessions() as s, s.begin():
                await s.execute(
                    text("""INSERT INTO app.tutor_questions
                    (id,owner_user_id,lesson_id,question,idempotency_key,request_hash,
                     policy_version,workflow_id,corpus_revision,reserved_usd,usage_status,budget_day)
                    VALUES(:id,:owner,:lesson,'synthetic question',:key,'hash',1,
                           'workflow','corpus',0.20,'unknown',
                           (now() AT TIME ZONE 'UTC')::date-2)"""),
                    {"id": uuid4(), "owner": user, "lesson": LESSON_ID, "key": uuid4()},
                )
            ids = [(await enqueue(api, worker, user, rid, event))[0] for _ in range(2)]
            snapshot = release_snapshot() | {"call_bound_usd": "0.040000"}

            async def reserve(aid):
                async with worker.sessions() as s, s.begin():
                    return await reserve_usd(s, aid, snapshot)

            assert sorted(await asyncio.gather(*(reserve(aid) for aid in ids))) == [False, True]
            async with worker.sessions() as s:
                assert await committed_usd(s) == Decimal("0.24")
            async with owner.sessions() as s, s.begin():
                await s.execute(text("UPDATE app.investigation_calls SET budget_day=budget_day-2"))
            async with worker.sessions() as s, s.begin():
                assert await committed_usd(s) == Decimal("0.24")
                admitted = await s.scalar(text("SELECT analysis_id FROM app.investigation_calls"))
                await settle_usd(s, admitted, 0, None)
            async with worker.sessions() as s:
                assert await committed_usd(s) == Decimal("0.20")
            # API may read accounting but cannot create/change budget reservations.
            with pytest.raises(DBAPIError):
                async with api.sessions() as s, s.begin():
                    await s.execute(text("UPDATE app.investigation_calls SET reserved_usd=0.01"))
        finally:
            await close_all(api, worker, owner)

    asyncio.run(run())

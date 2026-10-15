"""Explicit bounded arm-C execution; worker secret, no private truth access."""

import argparse
import asyncio
import json
import os
from uuid import UUID

from sqlalchemy import text

from app.analysis.budget import reserve_call, settle_call
from app.analysis.gemini_provider import GeminiProvider, ProviderRateLimited, request_body
from app.analysis.models import ProviderResponseError
from app.analysis.provider import AnalysisInput, validate_citations
from app.analysis.provider_config import load_config
from app.analysis.service import reserve_quota
from app.db.config import database_url
from app.db.session import Database


async def execute_arm(database: Database, arm: UUID) -> None:
    config = load_config(os.environ)
    provider = GeminiProvider(config)
    async with database.sessions() as session, session.begin():
        row = (
            (
                await session.execute(
                    text("""SELECT a.*,b.dataset_run_id,b.requested_by,
            b.dataset_hash,e.dataset_hash AS frozen_hash,e.release_cutoff
            FROM app.experiment_arms a JOIN app.experiment_batches b ON b.id=a.batch_id
            JOIN app.evaluations e ON e.run_id=b.dataset_run_id
            WHERE a.id=:id AND a.mode='C'"""),
                    {"id": arm},
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            text("SELECT id FROM app.runs WHERE id=:id FOR UPDATE"), {"id": row["dataset_run_id"]}
        )
        state = await session.scalar(
            text("SELECT status FROM app.experiment_arms WHERE id=:id FOR UPDATE"), {"id": arm}
        )
        assigned = await session.scalar(
            text("""SELECT 1 FROM app.instructor_assignments ia
            JOIN app.runs r ON r.owner_user_id=ia.analyst_user_id
            JOIN app.users u ON u.id=ia.instructor_user_id
            WHERE r.id=:run AND r.status='completed'
              AND EXISTS(SELECT 1 FROM app.scenario_instances si WHERE si.run_id=r.id)
              AND NOT EXISTS(SELECT 1 FROM app.scenario_instances si
                  JOIN app.scenarios s ON s.id=si.scenario_id
                  WHERE si.run_id=r.id AND s.purpose<>'training')
              AND r.expires_at>clock_timestamp()
              AND ia.instructor_user_id=:user AND u.status='active'
              AND u.role='instructor'"""),
            {"run": row["dataset_run_id"], "user": row["requested_by"]},
        )
        if not assigned or state not in {"unavailable", "pending"}:
            raise ValueError("Experiment not authorized or already executed")
        if row["dataset_hash"] != row["frozen_hash"]:
            raise ValueError("Frozen dataset mismatch")
        events = (
            (
                await session.execute(
                    text("""SELECT id,source,username,
            request_json AS request,response_json AS response,log_json AS log FROM app.events
            WHERE run_id=:run AND release_seq<=:cutoff ORDER BY release_seq"""),
                    {"run": row["dataset_run_id"], "cutoff": row["release_cutoff"]},
                )
            )
            .mappings()
            .all()
        )
        data = AnalysisInput.model_validate(
            {
                "analysis_id": arm,
                "evidence": [dict(e) for e in events],
                "prompt_version": "prompt-v1",
                "max_output_tokens": 2048,
            }
        )
        bound = len(json.dumps(request_body(data), ensure_ascii=False).encode()) + 4096 + 2048
        if not await reserve_call(session, arm, config.chat_model, bound, experiment=True):
            raise ValueError("Provider budget/rate/unknown hold blocks dispatch")
        if not await reserve_quota(
            session, row["requested_by"], row["dataset_run_id"], arm, experiment=True
        ):
            raise ValueError("Account quota blocks dispatch")
        baseline = (
            (
                await session.execute(
                    text("""SELECT outputs_json,metrics_json
            FROM app.experiment_arms WHERE batch_id=:batch AND mode='B' AND status='completed'"""),
                    {"batch": row["batch_id"]},
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            text("""UPDATE app.experiment_arms SET status='pending',
            config_snapshot=CAST(:config AS jsonb),error_code=NULL WHERE id=:id"""),
            {
                "id": arm,
                "config": json.dumps(
                    {
                        "mode": "real",
                        "model": config.chat_model,
                        "prompt_version": "prompt-v1",
                        "rag_enabled": False,
                        "dataset_hash": row["dataset_hash"],
                        "pricing_tier": "free",
                    }
                ),
            },
        )
        await session.execute(
            text("UPDATE app.experiment_batches SET status='running' WHERE id=:id"),
            {"id": row["batch_id"]},
        )
    status, error, tokens, result = "completed", None, 0, None
    try:
        output = await asyncio.wait_for(provider.analyze(data), timeout=25)
        tokens = output.usage.total_tokens
        validate_citations(output.result, {item.id for item in data.evidence})
        result = output.model_dump(mode="json")
    except ProviderRateLimited:
        status, error = "failed", "PROVIDER_RATE_LIMITED"
    except ProviderResponseError as exc:
        tokens = exc.usage.total_tokens
        status, error = "failed", "INVALID_PROVIDER_OUTPUT"
    except TimeoutError:
        status, error = "failed", "PROVIDER_TIMEOUT"
    except Exception:
        status, error = "failed", "PROVIDER_ERROR"
    async with database.sessions() as session, session.begin():
        await session.execute(
            text("SELECT id FROM app.runs WHERE id=:id FOR UPDATE"), {"id": row["dataset_run_id"]}
        )
        await session.execute(
            text("SELECT id FROM app.experiment_arms WHERE id=:id FOR UPDATE"), {"id": arm}
        )
        await settle_call(
            session,
            arm,
            tokens,
            rejected=error == "PROVIDER_RATE_LIMITED",
            cooldown=60 if error == "PROVIDER_RATE_LIMITED" else 0,
            experiment=True,
        )
        await session.execute(
            text("""UPDATE app.experiment_arms SET status=:status,
            outputs_json=CAST(:output AS jsonb),metrics_json=CAST(:metrics AS jsonb),
            error_code=:error WHERE id=:id"""),
            {
                "id": arm,
                "status": status,
                "error": error,
                "output": json.dumps({"findings": baseline["outputs_json"], "triage": result}),
                "metrics": json.dumps(baseline["metrics_json"]),
            },
        )
        ledgers = (
            (
                await session.execute(
                    text("""SELECT l.id FROM app.quota_ledgers l
            JOIN app.quota_reservations q ON q.ledger_id=l.id
            WHERE q.experiment_arm_id=:id AND q.status='reserved'
            ORDER BY l.scope_key,l.period_start FOR UPDATE OF l"""),
                    {"id": arm},
                )
            )
            .scalars()
            .all()
        )
        for ledger in ledgers:
            await session.execute(
                text("""UPDATE app.quota_ledgers SET
                consumed_tokens=consumed_tokens+:tokens,version=version+1 WHERE id=:id"""),
                {"id": ledger, "tokens": tokens},
            )
        await session.execute(
            text("""UPDATE app.quota_reservations SET status=:status,
            actual_tokens=:tokens,settled_at=clock_timestamp() WHERE experiment_arm_id=:id
            AND status='reserved'"""),
            {
                "id": arm,
                "tokens": tokens or None,
                "status": "consumed"
                if tokens
                else "released"
                if error == "PROVIDER_RATE_LIMITED"
                else "unknown",
            },
        )

        await session.execute(
            text("UPDATE app.experiment_batches SET status=:status WHERE id=:id"),
            {"id": row["batch_id"], "status": status},
        )

    if status != "completed":
        raise RuntimeError(error or "PROVIDER_ERROR")


async def execute(arm: UUID) -> None:
    database = Database(database_url("worker_runtime"))
    try:
        await execute_arm(database, arm)
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", type=UUID, required=True)
    try:
        asyncio.run(execute(parser.parse_args().arm))
    except Exception:
        raise SystemExit("Experiment rejected; check assignment, frozen data and budget") from None


if __name__ == "__main__":
    main()

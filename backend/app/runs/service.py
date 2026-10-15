"""Run transactions. DB time is authoritative; the browser never releases evidence."""

import hashlib
import json
import os
import secrets
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.provider_config import load_config
from app.auth.service import AuthError
from app.detection.policy import BASELINE_VERSION, CONFIG, CORRELATION_VERSION, RULE_VERSION
from app.scenarios.models import TrainingSelection
from app.scenarios.routes import select_training

RUN_COLUMNS = "id,status,version,elapsed_ms,duration_ms,expires_at,seed,analysis_mode,resumed_at"


def request_hash(body: TrainingSelection) -> str:
    serialized = body.model_dump(mode="json", exclude_none=True)
    return hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest()


async def server_time(session: AsyncSession) -> datetime:
    value = await session.scalar(text("SELECT clock_timestamp()"))
    assert isinstance(value, datetime)
    return value


def effective_ms(row: Mapping[Any, Any], now: datetime) -> int:
    elapsed = int(row["elapsed_ms"])
    if row["status"] == "running" and row["resumed_at"] is not None:
        elapsed += max(0, int((now - row["resumed_at"]).total_seconds() * 1000))
    return min(elapsed, int(row["duration_ms"]))


def run_view(row: Mapping[Any, Any], now: datetime) -> dict[str, Any]:
    return {
        key: row[key]
        for key in ("id", "status", "version", "duration_ms", "expires_at", "seed", "analysis_mode")
    } | {"elapsed_ms": effective_ms(row, now), "server_time": now}


async def get_owned_run(
    session: AsyncSession, run_id: UUID, owner_id: UUID, *, lock: bool = False
) -> Mapping[Any, Any]:
    suffix = " FOR UPDATE" if lock else ""
    row = (
        (
            await session.execute(
                text(
                    f"SELECT {RUN_COLUMNS},owner_user_id,release_cursor,created_at "
                    f"FROM app.runs WHERE id=:id AND owner_user_id=:owner{suffix}"
                ),
                {"id": run_id, "owner": owner_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise AuthError(404, "NOT_FOUND")
    return row


async def start_run(
    session: AsyncSession, owner_id: UUID, body: TrainingSelection, key: UUID
) -> tuple[dict[str, Any], bool]:
    # Serializes starts for one account, including different idempotency keys.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:owner,73102006))"),
        {"owner": str(owner_id)},
    )
    digest = request_hash(body)
    previous = (
        (
            await session.execute(
                text("""SELECT request_hash,response_json FROM app.idempotency_keys
                WHERE user_id=:owner AND method='POST' AND route_key='/runs' AND key=:key"""),
                {"owner": owner_id, "key": key},
            )
        )
        .mappings()
        .first()
    )
    if previous:
        if previous["request_hash"] != digest:
            raise AuthError(409, "IDEMPOTENCY_CONFLICT")
        return dict(previous["response_json"]), False
    selected = await select_training(session, body)
    if await session.scalar(
        text("SELECT 1 FROM app.runs WHERE owner_user_id=:owner AND status='running'"),
        {"owner": owner_id},
    ):
        raise AuthError(409, "RUN_ALREADY_RUNNING")
    quota = await session.scalar(
        text("SELECT daily_runs FROM app.user_quotas WHERE user_id=:owner FOR UPDATE"),
        {"owner": owner_id},
    )
    if quota is None:
        raise AuthError(403, "FORBIDDEN")
    today = await session.scalar(text("SELECT (clock_timestamp() AT TIME ZONE 'UTC')::date"))
    await session.execute(
        text("""INSERT INTO app.quota_ledgers(id,scope_key,user_id,period_start)
            VALUES (:id,:scope,:owner,:today) ON CONFLICT(scope_key,period_start) DO NOTHING"""),
        {"id": uuid4(), "scope": f"user:{owner_id}", "owner": owner_id, "today": today},
    )
    used = await session.scalar(
        text("""SELECT run_count FROM app.quota_ledgers
            WHERE scope_key=:scope AND period_start=:today FOR UPDATE"""),
        {"scope": f"user:{owner_id}", "today": today},
    )
    if used is None or used >= quota:
        raise AuthError(429, "RUN_QUOTA_EXCEEDED")
    now = await server_time(session)
    run_id = uuid4()
    provider_config = load_config(os.environ)
    analysis_mode = "mock" if provider_config.mode == "mock" else "real"
    model_id = provider_config.chat_model
    seed = body.seed if body.seed is not None else secrets.randbelow(2147483648)
    duration = max(item.duration_ms for item in selected)
    await session.execute(
        text("""INSERT INTO app.runs
            (id,owner_user_id,status,seed,resumed_at,duration_ms,expires_at,analysis_mode)
            VALUES (:id,:owner,'running',:seed,CAST(:now AS timestamptz),:duration,
                    CAST(:now AS timestamptz) + interval '30 days',:analysis_mode)"""),
        {
            "id": run_id,
            "owner": owner_id,
            "seed": seed,
            "now": now,
            "duration": duration,
            "analysis_mode": analysis_mode,
        },
    )
    fixture_hashes = []
    truth_versions: dict[str, int] = {}
    for ordinal, item in enumerate(selected, 1):
        await session.execute(
            text("""INSERT INTO app.scenario_instances(id,run_id,scenario_id,ordinal)
                VALUES (:id,:run,:scenario,:ordinal)"""),
            {"id": uuid4(), "run": run_id, "scenario": item.id, "ordinal": ordinal},
        )
        fixture_hashes.append(
            str(
                await session.scalar(text("SELECT app.training_fixture_hash(:id)"), {"id": item.id})
            )
        )
        truth_versions[str(item.id)] = int(
            await session.scalar(
                text("SELECT app.training_truth_version(:scenario)"), {"scenario": item.id}
            )
            or 1
        )
    await session.execute(
        text("""INSERT INTO app.run_versions
            (run_id,rule_version,baseline_version,correlation_version,ticket_policy_version,
             prompt_version,model_id,fixture_hash,config_snapshot,ground_truth_versions)
            VALUES (:run,:rule,:baseline,:correlation,'ticket-v1',
                    'prompt-v1',:model,:hash,CAST(:config AS jsonb),
                    CAST(:truth_versions AS jsonb))"""),
        {
            "run": run_id,
            "rule": RULE_VERSION,
            "baseline": BASELINE_VERSION,
            "correlation": CORRELATION_VERSION,
            "model": model_id,
            "hash": hashlib.sha256(":".join(fixture_hashes).encode()).hexdigest(),
            "config": json.dumps(
                {
                    "scenario_ids": [str(item.id) for item in selected],
                    "seed": seed,
                    "detector_config": CONFIG,
                    "analysis_mode": analysis_mode,
                    "model_id": model_id,
                }
            ),
            "truth_versions": json.dumps(truth_versions),
        },
    )
    await enqueue_release(session, run_id, 0, now, 1)
    await session.execute(
        text("""UPDATE app.quota_ledgers SET run_count=run_count+1,version=version+1
            WHERE scope_key=:scope AND period_start=:today"""),
        {"scope": f"user:{owner_id}", "today": today},
    )
    row = await get_owned_run(session, run_id, owner_id)
    result = json.loads(json.dumps(run_view(row, now), default=str))
    await session.execute(
        text("""INSERT INTO app.idempotency_keys
            (id,user_id,method,route_key,key,request_hash,status,response_status,response_json,resource_id,expires_at)
            VALUES (:id,:owner,'POST','/runs',:key,:hash,'completed',201,CAST(:body AS jsonb),:run,
                    CAST(:now AS timestamptz) + interval '30 days')"""),
        {
            "id": uuid4(),
            "owner": owner_id,
            "key": key,
            "hash": digest,
            "body": json.dumps(result, default=str),
            "run": run_id,
            "now": now,
        },
    )
    await audit_run(session, owner_id, run_id, "run.start")
    return result, True


async def enqueue_release(
    session: AsyncSession, run_id: UUID, cursor: int, available: datetime, epoch: int
) -> None:
    await session.execute(
        text("""INSERT INTO app.jobs(id,run_id,type,dedupe_key,payload,available_at)
            VALUES (:id,:run,'release_events',:dedupe,CAST(:payload AS jsonb),:at)
            ON CONFLICT(dedupe_key) DO NOTHING"""),
        {
            "id": uuid4(),
            "run": run_id,
            # A wake-up may release no event (notably just after resume). The next
            # wake-up must not collide with the still-running job at this cursor.
            "dedupe": f"release:{run_id}:{epoch}:{cursor}:{available.isoformat()}",
            "payload": json.dumps({"cursor": cursor}),
            "at": available,
        },
    )


async def audit_run(session: AsyncSession, owner_id: UUID, run_id: UUID, action: str) -> None:
    await session.execute(
        text("""INSERT INTO app.audit_logs
            (id,actor_user_id,actor_role,action,entity_type,entity_id)
            VALUES (:id,:owner,'analyst',:action,'run',:run)"""),
        {"id": uuid4(), "owner": owner_id, "action": action, "run": run_id},
    )


async def change_state(
    session: AsyncSession, run_id: UUID, owner_id: UUID, action: str, expected: int
) -> dict[str, Any]:
    row = await get_owned_run(session, run_id, owner_id, lock=True)
    if row["version"] != expected:
        raise AuthError(409, "VERSION_CONFLICT")
    now = await server_time(session)
    if action == "pause" and row["status"] == "running":
        elapsed = effective_ms(row, now)
        await session.execute(
            text("""UPDATE app.runs SET status='paused',elapsed_ms=:elapsed,
                resumed_at=NULL,version=version+1 WHERE id=:id"""),
            {"id": run_id, "elapsed": elapsed},
        )
    elif action == "resume" and row["status"] == "paused":
        await session.execute(
            text("""UPDATE app.runs SET status='running',resumed_at=:now,
                version=version+1 WHERE id=:id"""),
            {"id": run_id, "now": now},
        )
        await enqueue_release(session, run_id, int(row["release_cursor"]), now, expected + 1)
    else:
        raise AuthError(409, "INVALID_RUN_STATE")
    await audit_run(session, owner_id, run_id, f"run.{action}")
    return run_view(await get_owned_run(session, run_id, owner_id), now)


async def finish_run(
    session: AsyncSession, run_id: UUID, owner_id: UUID, expected: int
) -> dict[str, Any]:
    row = await get_owned_run(session, run_id, owner_id, lock=True)
    now = await server_time(session)
    if row["status"] in {"completing", "completed"}:
        return run_view(row, now) | {"evaluation_url": f"/api/v1/runs/{run_id}/evaluation"}
    if row["version"] != expected:
        raise AuthError(409, "VERSION_CONFLICT")
    if row["status"] not in {"running", "paused", "reviewing"}:
        raise AuthError(409, "INVALID_RUN_STATE")
    elapsed = effective_ms(row, now)
    cutoff = int(row["release_cursor"])
    hashes = (
        (
            await session.execute(
                text("""SELECT content_hash FROM app.events
        WHERE run_id=:run AND release_seq<=:cutoff ORDER BY release_seq"""),
                {"run": run_id, "cutoff": cutoff},
            )
        )
        .scalars()
        .all()
    )
    dataset_hash = hashlib.sha256(":".join(hashes).encode()).hexdigest()
    await session.execute(
        text("""UPDATE app.runs SET status='completing',
        elapsed_ms=:elapsed,resumed_at=NULL,completing_at=:now,version=version+1
        WHERE id=:run"""),
        {"elapsed": elapsed, "now": now, "run": run_id},
    )
    await session.execute(
        text("""INSERT INTO app.run_completions
        (run_id,revision,release_cutoff,assessment_cutoff,dataset_hash,truncated,drain_deadline)
        VALUES (:run,1,:cutoff,CAST(:now AS timestamptz),:hash,:truncated,
                CAST(:now AS timestamptz) + interval '60 seconds')"""),
        {
            "run": run_id,
            "cutoff": cutoff,
            "now": now,
            "hash": dataset_hash,
            "truncated": elapsed < row["duration_ms"],
        },
    )
    await session.execute(
        text("""INSERT INTO app.jobs(id,run_id,type,dedupe_key,payload)
        VALUES (:id,:run,'finalize_run',:dedupe,'{}'::jsonb)
        ON CONFLICT(dedupe_key) DO NOTHING"""),
        {"id": uuid4(), "run": run_id, "dedupe": f"finalize:{run_id}:1"},
    )
    await audit_run(session, owner_id, run_id, "run.finish_requested")
    return run_view(await get_owned_run(session, run_id, owner_id), now) | {
        "evaluation_url": f"/api/v1/runs/{run_id}/evaluation"
    }

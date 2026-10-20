"""PostgreSQL-backed worker: short claims, fenced commits, at-least-once delivery."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.analysis.worker import analyze_job
from app.db.session import Database
from app.detection.worker import detect_run
from app.knowledge.service import ingest
from app.runs.service import effective_ms, enqueue_release, server_time
from app.scenarios.fixtures import FixtureEvent, content_hash, load_fixture
from app.worker.fencing import lock_domain, require_lease

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures/events/training"
LEASE_SECONDS = 60
MAX_ATTEMPTS = 3


async def heartbeat(database: Database, worker_id: str, release_sha: str = "local") -> None:
    async with database.sessions() as session, session.begin():
        await session.execute(
            text("""INSERT INTO app.worker_heartbeats
            (worker_id,role,release_sha,last_seen_at)
            VALUES (:worker,'runner',:sha,clock_timestamp())
            ON CONFLICT(worker_id) DO UPDATE
            SET last_seen_at=clock_timestamp(),release_sha=:sha"""),
            {"worker": worker_id, "sha": release_sha},
        )


async def claim(database: Database, worker_id: str) -> dict[str, Any] | None:
    await recover_runs(database)
    async with database.sessions() as session, session.begin():
        await session.execute(
            text("""UPDATE app.jobs SET status='failed',
            last_error='LEASE_EXHAUSTED',locked_by=NULL,lease_token=NULL,
            lease_expires_at=NULL,finished_at=clock_timestamp()
            WHERE status='running' AND attempts>=3 AND lease_expires_at<=clock_timestamp()""")
        )
        row = (
            (
                await session.execute(
                    text("""SELECT id FROM app.jobs
            WHERE type IN ('release_events','detect_events','analyze_evidence','ingest_knowledge')
              AND attempts < 3 AND
              ((status='queued' AND available_at<=clock_timestamp())
               OR (status='running' AND lease_expires_at<=clock_timestamp()))
            ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT 1""")
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        token = uuid4()
        claimed = (
            (
                await session.execute(
                    text("""UPDATE app.jobs SET status='running',
            attempts=attempts+1,locked_by=:worker,lease_token=:token,
            lease_expires_at=clock_timestamp() + interval '60 seconds'
            WHERE id=:id RETURNING id,run_id,type,payload,attempts,lease_token"""),
                    {"worker": worker_id, "token": token, "id": row["id"]},
                )
            )
            .mappings()
            .one()
        )
        return dict(claimed)


async def recover_runs(database: Database) -> None:
    # Separate transaction: never retain a job lock while waiting for a run.
    async with database.sessions() as session, session.begin():
        # Reconcile a running run left without a wake-up by an older worker or
        # an interrupted deployment. Terminally failed release jobs are not
        # retried here; MAX_ATTEMPTS remains the upper bound.
        await session.execute(
            text("""WITH stalled AS (
                SELECT r.id,r.version,r.release_cursor FROM app.runs r
                WHERE r.status='running'
                  AND NOT EXISTS (SELECT 1 FROM app.jobs j
                    WHERE j.run_id=r.id AND j.type='release_events'
                      AND j.status IN ('queued','running','failed'))
                ORDER BY r.created_at FOR UPDATE SKIP LOCKED LIMIT 5
            ) INSERT INTO app.jobs(id,run_id,type,dedupe_key,payload,available_at)
            SELECT gen_random_uuid(),id,'release_events',
                   'recovery:'||id::text||':'||version::text||':'||release_cursor::text,
                   jsonb_build_object('cursor',release_cursor),clock_timestamp()
            FROM stalled ON CONFLICT(dedupe_key) DO NOTHING""")
        )


async def extend_lease(database: Database, job_id: UUID, token: UUID) -> bool:
    async with database.sessions() as session, session.begin():
        changed = await session.scalar(
            text("""UPDATE app.jobs
            SET lease_expires_at=clock_timestamp() + interval '60 seconds'
            WHERE id=:id AND lease_token=:token AND status='running'
            AND lease_expires_at>clock_timestamp() RETURNING id"""),
            {"id": job_id, "token": token},
        )
        return changed is not None


async def settle(database: Database, job: dict[str, Any], error: str | None = None) -> bool:
    async with database.sessions() as session, session.begin():
        terminal = error is None or job["attempts"] >= MAX_ATTEMPTS
        status = "succeeded" if error is None else ("failed" if terminal else "queued")
        changed = await session.scalar(
            text("""UPDATE app.jobs SET status=:status,
            locked_by=NULL,lease_token=NULL,lease_expires_at=NULL,last_error=:error,
            available_at=CASE WHEN :status='queued' THEN clock_timestamp() +
                (:delay * interval '1 second') ELSE available_at END,
            finished_at=CASE WHEN :terminal THEN clock_timestamp() ELSE NULL END
            WHERE id=:id AND status='running' AND lease_token=:token
            AND lease_expires_at>clock_timestamp() RETURNING id"""),
            {
                "status": status,
                "error": error,
                "terminal": terminal,
                "delay": min(30, 2 ** int(job["attempts"])),
                "id": job["id"],
                "token": job["lease_token"],
            },
        )
        return changed is not None


async def release_events(database: Database, job: dict[str, Any]) -> None:
    run_id = job["run_id"]
    if run_id is None:
        raise ValueError("Release job missing run")
    async with database.sessions() as session, session.begin():
        if not await lock_domain(session, job):
            return
        row = (
            (
                await session.execute(
                    text("""SELECT id,status,version,elapsed_ms,resumed_at,
            duration_ms,release_cursor,created_at FROM app.runs WHERE id=:id FOR UPDATE"""),
                    {"id": run_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None or row["status"] != "running":
            return
        now = await server_time(session)
        elapsed = effective_ms(row, now)
        instance_rows = (
            (
                await session.execute(
                    text("""SELECT i.id,i.ordinal,s.stable_key,
            s.version,s.fixture_hash,s.purpose FROM app.scenario_instances i
            JOIN app.scenarios s ON s.id=i.scenario_id WHERE i.run_id=:run
            ORDER BY i.ordinal"""),
                    {"run": run_id},
                )
            )
            .mappings()
            .all()
        )
        schedule: list[tuple[int, int, str, UUID, FixtureEvent]] = []
        for instance in instance_rows:
            path = (
                FIXTURE_ROOT.parent
                / instance["purpose"]
                / f"{instance['stable_key'].lower()}-v{instance['version']}.json"
            )
            fixture = load_fixture(path, instance["purpose"])
            if content_hash(fixture.model_dump(mode="json")) != instance["fixture_hash"]:
                raise ValueError("Pinned fixture hash mismatch")
            schedule.extend(
                (event.release_offset_ms, instance["ordinal"], event.key, instance["id"], event)
                for event in fixture.events
            )
        schedule.sort(key=lambda item: (item[0], item[1], item[2]))
        cursor = int(row["release_cursor"])
        for index, (offset, _, key, instance_id, event) in enumerate(schedule[cursor:], cursor + 1):
            if offset > elapsed:
                break
            body = event.model_dump(mode="json")
            await session.execute(
                text("""INSERT INTO app.events
                (id,run_id,scenario_instance_id,fixture_event_key,release_seq,event_time,
                 source,asset_id,username,src_ip,request_json,response_json,log_json,content_hash)
                VALUES (:id,:run,:instance,:key,:seq,:time,:source,:asset,:username,
                        CAST(:ip AS inet),CAST(:request AS jsonb),CAST(:response AS jsonb),
                        CAST(:log AS jsonb),:hash)
                ON CONFLICT(run_id,scenario_instance_id,fixture_event_key) DO NOTHING"""),
                {
                    "id": uuid4(),
                    "run": run_id,
                    "instance": instance_id,
                    "key": key,
                    "seq": index,
                    "time": row["created_at"] + timedelta(milliseconds=event.event_offset_ms),
                    "source": event.source,
                    "asset": event.asset_id,
                    "username": event.username,
                    "ip": event.src_ip,
                    "request": json.dumps(body["request"]),
                    "response": json.dumps(body["response"]),
                    "log": json.dumps(body["log"]),
                    "hash": content_hash(body),
                },
            )
            cursor = index
        if cursor > row["release_cursor"]:
            await session.execute(
                text("UPDATE app.runs SET release_cursor=:cursor WHERE id=:id"),
                {"cursor": cursor, "id": run_id},
            )
            run_mode = await session.scalar(
                text("SELECT mode FROM app.runs WHERE id=:run"), {"run": run_id}
            )
            if run_mode == "training":
                await session.execute(
                    text("""INSERT INTO app.jobs
                (id,run_id,type,dedupe_key,payload)
                VALUES (:id,:run,'detect_events',:dedupe,'{}'::jsonb)
                ON CONFLICT(dedupe_key) DO NOTHING"""),
                    {"id": uuid4(), "run": run_id, "dedupe": f"detect:{run_id}:{cursor}"},
                )
        if elapsed >= row["duration_ms"]:
            await session.execute(
                text("""UPDATE app.runs SET status='reviewing',
                elapsed_ms=duration_ms,resumed_at=NULL,version=version+1 WHERE id=:id"""),
                {"id": run_id},
            )
        else:
            next_offset = schedule[cursor][0] if cursor < len(schedule) else int(row["duration_ms"])
            delay = max(0, next_offset - elapsed)
            # Resume can create another wake-up for the same cursor. Both are safe under run lock.
            await enqueue_release(
                session, run_id, cursor, now + timedelta(milliseconds=delay), int(row["version"])
            )

        await require_lease(session, job)


async def process_one(database: Database, worker_id: str) -> bool:
    job = await claim(database, worker_id)
    if job is None:
        return False
    try:
        if job["type"] == "ingest_knowledge":
            await ingest(database, job)
        elif job["type"] == "release_events":
            await release_events(database, job)
        elif job["type"] == "detect_events":
            await detect_run(database, job["run_id"], job=job)
        elif job["type"] == "analyze_evidence":
            await analyze_job(database, job)
        else:
            raise ValueError("Unsupported job type")
    except Exception as exc:
        await settle(database, job, type(exc).__name__)
        return True
    await settle(database, job)
    return True

import hashlib
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.analysis.service import enqueue_analysis
from app.db.session import Database
from app.detection.policy import evaluate_pinned
from app.worker.fencing import lock_domain, require_lease


async def detect_run(
    database: Database, run_id: UUID, *, job: dict[str, Any] | None = None
) -> None:
    async with database.sessions() as session, session.begin():
        if job is not None and not await lock_domain(session, job):
            return
        # A run lock orders this after release and blocks completion snapshot races.
        run = (
            (
                await session.execute(
                    text("""SELECT id,owner_user_id,created_at FROM app.runs
            WHERE id=:run FOR UPDATE"""),
                    {"run": run_id},
                )
            )
            .mappings()
            .first()
        )
        if run is None:
            return
        rows = (
            (
                await session.execute(
                    text("""SELECT id,source,username,src_ip,asset_id,event_time,
            scenario_instance_id,response_json,log_json,content_hash
            FROM app.events WHERE run_id=:run ORDER BY release_seq"""),
                    {"run": run_id},
                )
            )
            .mappings()
            .all()
        )
        evidence = {row["id"]: row for row in rows}
        versions = (
            await session.execute(
                text(
                    """SELECT rule_version,baseline_version,correlation_version
                    FROM app.run_versions WHERE run_id=:run"""
                ),
                {"run": run_id},
            )
        ).one()
        detector_input = [
            dict(row)
            | {"offset_ms": int((row["event_time"] - run["created_at"]).total_seconds() * 1000)}
            for row in rows
        ]
        for finding in evaluate_pinned(detector_input, *versions):
            digest = hashlib.sha256(
                ":".join(evidence[item]["content_hash"] for item in finding.evidence_ids).encode()
            ).hexdigest()
            detection_id = await session.scalar(
                text("""INSERT INTO app.detections
                (id,run_id,detector_type,detector_version,correlation_key,
                 evidence_snapshot_hash,severity,explanation)
                VALUES (:id,:run,:kind,:version,:correlation,:hash,:severity,:explanation)
                ON CONFLICT(run_id,detector_type,detector_version,
                            correlation_key,evidence_snapshot_hash)
                DO NOTHING RETURNING id"""),
                {
                    "id": uuid4(),
                    "run": run_id,
                    "kind": finding.detector_type,
                    "version": finding.detector_version,
                    "correlation": finding.correlation_key,
                    "hash": digest,
                    "severity": finding.severity,
                    "explanation": finding.explanation,
                },
            )
            if detection_id is None:
                continue
            for event_id in finding.evidence_ids:
                await session.execute(
                    text("""INSERT INTO app.detection_evidence
                    (run_id,detection_id,event_id) VALUES (:run,:detection,:event)"""),
                    {"run": run_id, "detection": detection_id, "event": event_id},
                )
            alert_id = uuid4()
            await session.execute(
                text("""INSERT INTO app.alerts
                (id,run_id,detection_id,severity) VALUES (:id,:run,:detection,:severity)"""),
                {
                    "id": alert_id,
                    "run": run_id,
                    "detection": detection_id,
                    "severity": finding.severity,
                },
            )
            ticket_id = await session.scalar(
                text("""INSERT INTO app.tickets
                (id,run_id,origin,correlation_key,title,severity)
                VALUES (:id,:run,'automatic',:correlation,:title,:severity)
                ON CONFLICT(run_id,correlation_key) WHERE origin='automatic'
                DO NOTHING RETURNING id"""),
                {
                    "id": uuid4(),
                    "run": run_id,
                    "correlation": finding.correlation_key,
                    "title": finding.title,
                    "severity": finding.severity,
                },
            )
            if ticket_id is None:
                ticket_id = await session.scalar(
                    text("""SELECT id FROM app.tickets
                    WHERE run_id=:run AND origin='automatic' AND correlation_key=:correlation"""),
                    {"run": run_id, "correlation": finding.correlation_key},
                )
            await session.execute(
                text("""INSERT INTO app.ticket_alerts
                (run_id,ticket_id,alert_id) VALUES (:run,:ticket,:alert)
                ON CONFLICT DO NOTHING"""),
                {"run": run_id, "ticket": ticket_id, "alert": alert_id},
            )
            for event_id in finding.evidence_ids:
                await session.execute(
                    text("""INSERT INTO app.ticket_events
                    (run_id,ticket_id,event_id) VALUES (:run,:ticket,:event)
                    ON CONFLICT DO NOTHING"""),
                    {"run": run_id, "ticket": ticket_id, "event": event_id},
                )
            await enqueue_analysis(
                session,
                run_id,
                run["owner_user_id"],
                finding.correlation_key,
                digest,
                list(finding.evidence_ids),
                ticket_id,
            )

        if job is not None:
            await require_lease(session, job)

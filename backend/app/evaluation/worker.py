"""Evaluator-only finalization for frozen training runs."""

import json
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.metrics import Candidate, Incident, metrics


async def finalize(session: AsyncSession, run_id: UUID) -> bool:
    """Return False while in-cutoff work is draining; otherwise publish one immutable result."""
    run = (
        (
            await session.execute(
                text("""SELECT status FROM app.runs WHERE id=:run FOR UPDATE"""), {"run": run_id}
            )
        )
        .mappings()
        .first()
    )
    if run is None or run["status"] != "completing":
        return True
    completion = (
        (
            await session.execute(
                text("""SELECT * FROM app.run_completions WHERE run_id=:run"""), {"run": run_id}
            )
        )
        .mappings()
        .one()
    )
    now = await session.scalar(text("SELECT clock_timestamp()"))
    pending = await session.scalar(
        text("""SELECT count(*) FROM app.jobs
        WHERE run_id=:run AND type IN ('detect_events','analyze_evidence')
          AND status IN ('queued','running')"""),
        {"run": run_id},
    )
    if pending and now < completion["drain_deadline"]:
        retry = uuid4()
        await session.execute(
            text("""INSERT INTO app.jobs(id,run_id,type,dedupe_key,payload,available_at)
             VALUES (:id,:run,'finalize_run',:dedupe,'{}'::jsonb,
                     clock_timestamp()+interval '1 second')
            ON CONFLICT(dedupe_key) DO NOTHING"""),
            {"id": retry, "run": run_id, "dedupe": f"finalize:{run_id}:retry:{retry}"},
        )
        return True

    scenarios = (
        (
            await session.execute(
                text("""SELECT i.id AS instance_id,i.scenario_id,s.version
        FROM app.scenario_instances i JOIN app.scenarios s ON s.id=i.scenario_id
        WHERE i.run_id=:run ORDER BY i.ordinal"""),
                {"run": run_id},
            )
        )
        .mappings()
        .all()
    )
    truth_versions = await session.scalar(
        text("SELECT ground_truth_versions FROM app.run_versions WHERE run_id=:run"),
        {"run": run_id},
    )
    truth_versions = truth_versions or {}
    events = (
        (
            await session.execute(
                text("""SELECT id,scenario_instance_id,fixture_event_key,release_seq
        FROM app.events WHERE run_id=:run AND release_seq<=:cutoff ORDER BY release_seq"""),
                {"run": run_id, "cutoff": completion["release_cutoff"]},
            )
        )
        .mappings()
        .all()
    )
    tickets = (
        (
            await session.execute(
                text("""SELECT id,
        (deleted_at IS NOT NULL AND deleted_at<=:cutoff) AS deleted_at_cutoff
        FROM app.tickets
        WHERE run_id=:run AND created_at<=:cutoff ORDER BY created_at,id"""),
                {"run": run_id, "cutoff": completion["assessment_cutoff"]},
            )
        )
        .mappings()
        .all()
    )
    ticket_events = (
        (
            await session.execute(
                text("""SELECT te.ticket_id,te.event_id FROM app.ticket_events te
        JOIN app.events e ON e.run_id=te.run_id AND e.id=te.event_id
        JOIN app.tickets t ON t.run_id=te.run_id AND t.id=te.ticket_id
        WHERE te.run_id=:run AND e.release_seq<=:release AND t.created_at<=:cutoff"""),
                {
                    "run": run_id,
                    "release": completion["release_cutoff"],
                    "cutoff": completion["assessment_cutoff"],
                },
            )
        )
        .mappings()
        .all()
    )
    detection_events = (
        (
            await session.execute(
                text("""SELECT d.id AS detection_id,de.event_id,
                    coalesce(bool_or(t.deleted_at IS NOT NULL
                        AND t.deleted_at<=:cutoff),false) AS deleted_ticket
                FROM app.detections d JOIN app.detection_evidence de
                  ON de.run_id=d.run_id AND de.detection_id=d.id
                LEFT JOIN app.ticket_alerts ta ON ta.run_id=d.run_id AND ta.alert_id IN
                  (SELECT a.id FROM app.alerts a WHERE a.run_id=d.run_id AND a.detection_id=d.id)
                LEFT JOIN app.tickets t ON t.run_id=ta.run_id AND t.id=ta.ticket_id
                WHERE d.run_id=:run GROUP BY d.id,de.event_id ORDER BY d.id,de.event_id"""),
                {"run": run_id, "cutoff": completion["assessment_cutoff"]},
            )
        )
        .mappings()
        .all()
    )
    latest_assessments = (
        (
            await session.execute(
                text("""SELECT DISTINCT ON(ticket_id) ticket_id,disposition
        FROM app.assessments WHERE run_id=:run AND created_at<=:cutoff
        ORDER BY ticket_id,revision DESC"""),
                {"run": run_id, "cutoff": completion["assessment_cutoff"]},
            )
        )
        .mappings()
        .all()
    )
    disposition = {item["ticket_id"]: item["disposition"] for item in latest_assessments}
    analyses = (
        (
            await session.execute(
                text("""SELECT id,correlation_key,evidence_hash,mode,model_id,prompt_version,
        kind,question_text,knowledge_release_id,retrieval_config_version,
        status,result_json,usage_json,created_at,finished_at FROM app.analyses
        WHERE run_id=:run AND created_at<=:cutoff ORDER BY created_at,id"""),
                {"run": run_id, "cutoff": completion["assessment_cutoff"]},
            )
        )
        .mappings()
        .all()
    )
    retrieval_snapshots: dict[UUID, dict[str, Any]] = {}
    for analysis in analyses:
        retrieval = (
            (
                await session.execute(
                    text("""SELECT status,release_id,config_version
            FROM app.retrievals WHERE run_id=:run AND analysis_id=:id"""),
                    {"run": run_id, "id": analysis["id"]},
                )
            )
            .mappings()
            .first()
        )
        if retrieval is not None:
            citations = (
                (
                    await session.execute(
                        text("""SELECT id AS retrieval_item_id,
                document_title,document_version,heading,excerpt_snapshot AS excerpt,content_hash
                FROM app.retrieval_items WHERE run_id=:run AND analysis_id=:id ORDER BY rank"""),
                        {"run": run_id, "id": analysis["id"]},
                    )
                )
                .mappings()
                .all()
            )
            retrieval_snapshots[analysis["id"]] = {
                "status": retrieval["status"],
                "release_id": str(retrieval["release_id"]),
                "config_version": retrieval["config_version"],
                "citations": [
                    dict(c) | {"retrieval_item_id": str(c["retrieval_item_id"])} for c in citations
                ],
            }
    event_by_key = {(e["scenario_instance_id"], e["fixture_event_key"]): e for e in events}
    truth_rows: list[tuple[Any, Any]] = []
    for scenario in scenarios:
        truths = (
            (
                await session.execute(
                    text("""SELECT truth_version,incident_key,threat_label,
                expected_evidence_keys,explanation
            FROM private.ground_truth WHERE scenario_id=:scenario
              AND truth_version=:truth_version ORDER BY incident_key"""),
                    {
                        "scenario": scenario["scenario_id"],
                        "truth_version": int(truth_versions.get(str(scenario["scenario_id"]), 1)),
                    },
                )
            )
            .mappings()
            .all()
        )
        truth_rows.extend((scenario, item) for item in truths)
    incidents: list[Incident] = []
    item_rows: list[dict[str, object]] = []
    for scenario, truth in truth_rows:
        refs = frozenset(
            event_by_key[(scenario["instance_id"], key)]["id"]
            for key in truth["expected_evidence_keys"]
            if (scenario["instance_id"], key) in event_by_key
        )
        incidents.append(
            Incident(
                f"{scenario['instance_id']}:{truth['incident_key']}",
                bool(truth["threat_label"]),
                refs or frozenset({uuid4()}),
            )
        )
        item_rows.append(
            {
                "scenario_instance_id": scenario["instance_id"],
                "incident_key": truth["incident_key"],
                "label": bool(truth["threat_label"]),
                "refs": refs,
                "complete": len(refs) == len(truth["expected_evidence_keys"]),
            }
        )
    released = frozenset(e["id"] for e in events)
    ticket_ref_map: dict[UUID, set[UUID]] = {t["id"]: set() for t in tickets}
    for row in ticket_events:
        if row["ticket_id"] in ticket_ref_map:
            ticket_ref_map[row["ticket_id"]].add(row["event_id"])
    for item in item_rows:
        refs = cast(frozenset[UUID], item["refs"])
        item["ticket_deleted"] = any(
            bool(ticket["deleted_at_cutoff"]) and bool(refs & ticket_ref_map[ticket["id"]])
            for ticket in tickets
        )
    detection_refs: dict[UUID, set[UUID]] = {}
    detection_deleted: dict[UUID, bool] = {}
    for detection_row in detection_events:
        detection_id = cast(UUID, detection_row["detection_id"])
        event_id = cast(UUID, detection_row["event_id"])
        detection_refs.setdefault(detection_id, set()).add(event_id)
        detection_deleted[detection_id] = detection_deleted.get(detection_id, False) or bool(
            detection_row["deleted_ticket"]
        )
    candidates = [
        Candidate(frozenset(refs), deleted=detection_deleted.get(detection_id, False))
        for detection_id, refs in detection_refs.items()
    ]
    result = (
        metrics(incidents, candidates, released)
        if incidents
        else {
            "unit": "incident_group",
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "tn": 0,
            "precision": None,
            "recall": None,
            "precision_null_reason": "NO_POSITIVE_CANDIDATES",
            "recall_null_reason": "NO_THREAT_GROUPS",
            "incomplete_groups": 0,
            "undetermined_groups": 0,
            "unmatched_candidates": len(candidates),
        }
    )
    from app.analysis.investigation_config import analysis_withdrawn

    withdraw_real = any(a["mode"] == "real" for a in analyses) and await analysis_withdrawn(
        session, run_id, "real"
    )
    snapshot = {
        "release_cutoff": completion["release_cutoff"],
        "assessment_cutoff": completion["assessment_cutoff"].isoformat(),
        "events": [
            {
                "id": str(e["id"]),
                "scenario_instance_id": str(e["scenario_instance_id"]),
                "key": e["fixture_event_key"],
                "release_seq": e["release_seq"],
            }
            for e in events
        ],
        "tickets": [
            {
                "id": str(t["id"]),
                "deleted": bool(t["deleted_at_cutoff"]),
                "evidence": sorted(str(v) for v in ticket_ref_map[t["id"]]),
                "disposition": disposition.get(t["id"]),
            }
            for t in tickets
        ],
        "analyses": [
            {
                "id": str(a["id"]),
                "correlation_key": a["correlation_key"],
                "evidence_hash": a["evidence_hash"],
                "mode": a["mode"],
                "model_id": a["model_id"],
                "prompt_version": a["prompt_version"],
                "status": a["status"],
                "kind": a["kind"],
                "question_text": None
                if withdraw_real and a["mode"] == "real"
                else a["question_text"],
                "knowledge_release_id": str(a["knowledge_release_id"])
                if a["knowledge_release_id"]
                else None,
                "retrieval": retrieval_snapshots.get(a["id"]),
                "response_visibility": "withdrawn"
                if withdraw_real and a["mode"] == "real"
                else "visible",
                "result": None if withdraw_real and a["mode"] == "real" else a["result_json"],
                "usage": a["usage_json"],
                "created_at": a["created_at"].isoformat(),
                "finished_at": a["finished_at"].isoformat() if a["finished_at"] else None,
            }
            for a in analyses
        ],
        "detections": [
            {
                "id": str(detection_id),
                "evidence_ids": sorted(str(event_id) for event_id in refs),
                "ticket_deleted_at_cutoff": detection_deleted.get(detection_id, False),
            }
            for detection_id, refs in sorted(detection_refs.items(), key=lambda item: str(item[0]))
        ],
        "human_metrics": {
            "status": "unavailable",
            "reason": "HUMAN_SCORING_POLICY_UNDECIDED",
            "ticket_count": len(tickets),
        },
        "truth_versions": truth_versions,
    }
    evaluation_id = uuid4()
    versions = {
        "metrics": "incident-group-v1",
        "rules": "pinned-per-run",
        "truth_versions": truth_versions,
    }
    await session.execute(
        text("""INSERT INTO app.evaluations
        (id,run_id,revision,status,release_cutoff,assessment_cutoff,
         ground_truth_version,dataset_hash,truncated,
         snapshot_json,metrics_json,versions_json,completed_at)
        VALUES (:id,:run,1,'completed',:release,:cutoff,:truth,:hash,:truncated,
                CAST(:snapshot AS jsonb),
                CAST(:metrics AS jsonb),CAST(:versions AS jsonb),clock_timestamp())
                ON CONFLICT(run_id,revision) DO NOTHING"""),
        {
            "id": evaluation_id,
            "run": run_id,
            "release": completion["release_cutoff"],
            "cutoff": completion["assessment_cutoff"],
            "truth": max((int(value) for value in truth_versions.values()), default=1),
            "hash": completion["dataset_hash"],
            "truncated": completion["truncated"],
            "snapshot": json.dumps(snapshot),
            "metrics": json.dumps(result),
            "versions": json.dumps(versions),
        },
    )
    for item in item_rows:
        await session.execute(
            text("""INSERT INTO app.evaluation_items
            (id,run_id,evaluation_id,scenario_instance_id,incident_key,ground_truth_label,
             evidence_complete,correct,ticket_deleted,snapshot_json)
            VALUES (:id,:run,:evaluation,:instance,:key,:label,:complete,NULL,:deleted,
                    CAST(:snapshot AS jsonb))
            ON CONFLICT(evaluation_id,scenario_instance_id,incident_key) DO NOTHING"""),
            {
                "id": uuid4(),
                "run": run_id,
                "evaluation": evaluation_id,
                "instance": item["scenario_instance_id"],
                "key": item["incident_key"],
                "label": item["label"],
                "complete": item["complete"],
                "deleted": item["ticket_deleted"],
                "snapshot": json.dumps(
                    {
                        "event_ids": sorted(
                            str(value) for value in cast(frozenset[UUID], item["refs"])
                        )
                    }
                ),
            },
        )
    for scenario, truth in truth_rows:
        await session.execute(
            text("""INSERT INTO private.evaluation_truth
            (id,run_id,evaluation_id,scenario_instance_id,incident_key,truth_version,threat_label,
             expected_evidence_keys,explanation)
            VALUES (:id,:run,:evaluation,:instance,:key,:truth_version,:label,
                     CAST(:evidence AS jsonb),:explanation)
            ON CONFLICT(evaluation_id,scenario_instance_id,incident_key) DO NOTHING"""),
            {
                "id": uuid4(),
                "run": run_id,
                "evaluation": evaluation_id,
                "instance": scenario["instance_id"],
                "key": truth["incident_key"],
                "truth_version": truth["truth_version"],
                "label": truth["threat_label"],
                "evidence": json.dumps(truth["expected_evidence_keys"]),
                "explanation": truth["explanation"],
            },
        )
    await session.execute(
        text(
            "UPDATE app.runs SET status='completed',completed_at=clock_timestamp(),"
            "version=version+1 WHERE id=:run AND status='completing'"
        ),
        {"run": run_id},
    )
    # Fence workers that returned after the drain deadline before exposing completed.
    await session.execute(
        text("""UPDATE app.jobs SET status='cancelled',last_error='RUN_COMPLETED_CUTOFF',
            locked_by=NULL,lease_token=NULL,lease_expires_at=NULL,finished_at=clock_timestamp()
            WHERE run_id=:run AND type IN ('release_events','detect_events','analyze_evidence')
              AND status IN ('queued','running')"""),
        {"run": run_id},
    )
    return True

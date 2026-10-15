"""Read-only evaluation, export, and assigned Instructor review routes."""

import json
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.auth import service as auth
from app.auth.service import authorize_assignment, authorize_owner
from app.evaluation.experiments import compare
from app.http_models import Meta

router = APIRouter(prefix="/api/v1", tags=["Evaluation"])
admin_router = APIRouter(prefix="/api/v1/admin/runs", tags=["Instructor review"])


class CommentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=2000)


async def evaluation_row(session: Any, run_id: UUID) -> Any:
    return (
        (
            await session.execute(
                text("""SELECT e.* FROM app.evaluations e
        JOIN app.runs r ON r.id=e.run_id WHERE e.run_id=:run AND r.status='completed'"""),
                {"run": run_id},
            )
        )
        .mappings()
        .first()
    )


@router.get("/runs/{run_id}/evaluation", operation_id="evaluation_get")
async def get_evaluation(run_id: UUID, request: Request) -> dict[str, Any]:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await authorize_owner(
            user,
            await session.scalar(
                text("SELECT owner_user_id FROM app.runs WHERE id=:run"), {"run": run_id}
            )
            or UUID(int=0),
        )
        row = await evaluation_row(session, run_id)
        if row is None:
            raise auth.AuthError(409, "EVALUATION_PENDING")
        data = {
            "id": row["id"],
            "run_id": run_id,
            "revision": row["revision"],
            "status": row["status"],
            "release_cutoff": row["release_cutoff"],
            "assessment_cutoff": row["assessment_cutoff"],
            "dataset_hash": row["dataset_hash"],
            "truncated": row["truncated"],
            "metrics": row["metrics_json"],
            "versions": row["versions_json"],
        }
    return {"data": data, "meta": Meta(request_id=request.state.request_id).model_dump()}


@router.get("/runs/{run_id}/export", operation_id="evaluation_export")
async def export_evaluation(run_id: UUID, request: Request) -> Response:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        owner = await session.scalar(
            text("SELECT owner_user_id FROM app.runs WHERE id=:run"), {"run": run_id}
        )
        if owner is None:
            raise auth.AuthError(404, "NOT_FOUND")
        await authorize_owner(user, owner)
        row = await evaluation_row(session, run_id)
        if row is None:
            raise auth.AuthError(409, "EVALUATION_PENDING")
        body = {
            "evaluation_id": str(row["id"]),
            "run_id": str(run_id),
            "revision": row["revision"],
            "dataset_hash": row["dataset_hash"],
            "release_cutoff": row["release_cutoff"],
            "assessment_cutoff": row["assessment_cutoff"].isoformat(),
            "truncated": row["truncated"],
            "metrics": row["metrics_json"],
            "versions": row["versions_json"],
            "snapshot": row["snapshot_json"],
        }
    return Response(
        content=json.dumps(body, sort_keys=True, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="evaluation-{run_id}.json"'},
    )


@router.get("/runs/{run_id}/ground-truth", operation_id="training_ground_truth_get")
async def owner_ground_truth(run_id: UUID, request: Request) -> dict[str, Any]:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        row = (
            (
                await session.execute(
                    text("SELECT owner_user_id,status FROM app.runs WHERE id=:run"), {"run": run_id}
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise auth.AuthError(404, "NOT_FOUND")
        await authorize_owner(user, row["owner_user_id"])
        if row["status"] != "completed":
            raise auth.AuthError(409, "GROUND_TRUTH_LOCKED")
        truth = (
            (
                await session.execute(
                    text("""SELECT * FROM private.owner_training_truth(:user,:run)
                    ORDER BY scenario_key,incident_key"""),
                    {"user": user["id"], "run": run_id},
                )
            )
            .mappings()
            .all()
        )
        await session.execute(
            text("""INSERT INTO app.audit_logs
                (id,actor_user_id,actor_role,action,entity_type,entity_id,run_id)
                VALUES (:id,:actor,'analyst','ground_truth.owner_read','run',:run,:run)"""),
            {"id": uuid4(), "actor": user["id"], "run": run_id},
        )
    return {
        "data": [dict(item) for item in truth],
        "meta": Meta(request_id=request.state.request_id).model_dump(),
    }


async def assigned_run(session: Any, user: Any, run_id: UUID) -> UUID:
    owner = await session.scalar(
        text("SELECT owner_user_id FROM app.runs WHERE id=:run"), {"run": run_id}
    )
    if owner is None:
        raise auth.AuthError(404, "NOT_FOUND")
    await authorize_assignment(session, user, owner)
    return UUID(str(owner))


@admin_router.get("", operation_id="instructor_runs_list")
async def instructor_runs(request: Request) -> dict[str, Any]:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        if user["role"] != "instructor":
            raise auth.AuthError(403, "FORBIDDEN")
        rows = (
            (
                await session.execute(
                    text("""SELECT r.id,r.owner_user_id,u.display_name,r.status,r.version,
                    r.created_at,(e.id IS NOT NULL) AS evaluated
                    FROM app.instructor_assignments ia JOIN app.runs r
                      ON r.owner_user_id=ia.analyst_user_id
                    JOIN app.users u ON u.id=r.owner_user_id
                    LEFT JOIN app.evaluations e ON e.run_id=r.id AND e.status='completed'
                    WHERE ia.instructor_user_id=:instructor
                    ORDER BY r.created_at DESC,r.id DESC LIMIT 100"""),
                    {"instructor": user["id"]},
                )
            )
            .mappings()
            .all()
        )
    return {
        "data": [dict(row) for row in rows],
        "meta": Meta(request_id=request.state.request_id).model_dump(),
    }


@admin_router.get("/{run_id}/evaluation", operation_id="instructor_evaluation_get")
async def instructor_evaluation(run_id: UUID, request: Request) -> dict[str, Any]:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await assigned_run(session, user, run_id)
        row = await evaluation_row(session, run_id)
        if row is None:
            raise auth.AuthError(409, "EVALUATION_PENDING")
        data = {
            "id": row["id"],
            "run_id": run_id,
            "revision": row["revision"],
            "status": row["status"],
            "metrics": row["metrics_json"],
            "versions": row["versions_json"],
            "truncated": row["truncated"],
        }
        await session.execute(
            text("""INSERT INTO app.audit_logs
            (id,actor_user_id,actor_role,action,entity_type,entity_id,run_id)
            VALUES (:id,:actor,'instructor','evaluation.instructor_read','run',:run,:run)"""),
            {"id": uuid4(), "actor": user["id"], "run": run_id},
        )
    return {"data": data, "meta": Meta(request_id=request.state.request_id).model_dump()}


@admin_router.get("/{run_id}/ground-truth", operation_id="instructor_ground_truth_get")
async def instructor_truth(run_id: UUID, request: Request) -> dict[str, Any]:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await assigned_run(session, user, run_id)
        status = await session.scalar(
            text("SELECT status FROM app.runs WHERE id=:run"), {"run": run_id}
        )
        if status in {"running", "paused", "reviewing"}:
            truth_query = "SELECT * FROM private.assigned_training_truth(:user,:run)"
        elif status == "completed":
            if await evaluation_row(session, run_id) is None:
                raise auth.AuthError(409, "EVALUATION_PENDING")
            truth_query = "SELECT * FROM private.assigned_evaluation_truth(:user,:run)"
        else:
            raise auth.AuthError(409, "GROUND_TRUTH_LOCKED")
        rows = (
            (
                await session.execute(
                    text(truth_query + " ORDER BY scenario_key,incident_key"),
                    {"user": user["id"], "run": run_id},
                )
            )
            .mappings()
            .all()
        )
        await session.execute(
            text("""INSERT INTO app.audit_logs
            (id,actor_user_id,actor_role,action,entity_type,entity_id,run_id)
            VALUES (:id,:actor,'instructor','ground_truth.instructor_read','run',:run,:run)"""),
            {"id": uuid4(), "actor": user["id"], "run": run_id},
        )
    return {
        # Keep private storage column names out of the browser bundle.
        "data": [
            {
                "scenario_key": row["scenario_key"],
                "incident_key": row["incident_key"],
                "label": row["threat_label"],
                "evidence": row["expected_evidence_keys"],
                "details": row["explanation"],
                "version": row["truth_version"],
            }
            for row in rows
        ],
        "meta": Meta(request_id=request.state.request_id).model_dump(),
    }


@admin_router.get("/{run_id}/comments", operation_id="instructor_comments_list")
async def list_comments(run_id: UUID, request: Request) -> dict[str, Any]:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        await assigned_run(session, user, run_id)
        rows = (
            (
                await session.execute(
                    text("""SELECT id,instructor_user_id,body,created_at
                        FROM app.instructor_run_comments
            WHERE run_id=:run AND deleted_at IS NULL ORDER BY created_at,id"""),
                    {"run": run_id},
                )
            )
            .mappings()
            .all()
        )
    return {
        "data": [dict(row) for row in rows],
        "meta": Meta(request_id=request.state.request_id).model_dump(),
    }


@admin_router.post("/{run_id}/comments", status_code=201, operation_id="instructor_comments_create")
async def create_comment(run_id: UUID, body: CommentInput, request: Request) -> dict[str, Any]:
    async with auth.database(request).sessions() as session, session.begin():
        await auth.csrf_check(session, request)
        user = await auth.require_user(session, request)
        owner = await assigned_run(session, user, run_id)
        row = (
            (
                await session.execute(
                    text("""INSERT INTO app.instructor_run_comments
            (id,instructor_user_id,analyst_user_id,run_id,body)
            VALUES (:id,:instructor,:owner,:run,:body)
            RETURNING id,instructor_user_id,body,created_at"""),
                    {
                        "id": uuid4(),
                        "instructor": user["id"],
                        "owner": owner,
                        "run": run_id,
                        "body": body.body.strip(),
                    },
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            text("""INSERT INTO app.audit_logs
            (id,actor_user_id,actor_role,action,entity_type,entity_id,run_id)
            VALUES (:id,:actor,'instructor','instructor.comment_create','run',:run,:run)"""),
            {"id": uuid4(), "actor": user["id"], "run": run_id},
        )
    return {"data": dict(row), "meta": Meta(request_id=request.state.request_id).model_dump()}


@admin_router.post(
    "/{run_id}/experiments", status_code=201, operation_id="instructor_experiment_create"
)
async def create_experiment(run_id: UUID, request: Request) -> dict[str, Any]:
    async with auth.database(request).sessions() as session, session.begin():
        await auth.csrf_check(session, request)
        user = await auth.require_user(session, request)
        await assigned_run(session, user, run_id)
        evaluation = await evaluation_row(session, run_id)
        if evaluation is None:
            raise auth.AuthError(409, "EVALUATION_PENDING")
        event_rows = (
            (
                await session.execute(
                    text("""SELECT e.id,e.scenario_instance_id,e.fixture_event_key,e.source,
            e.username,e.src_ip,e.asset_id,e.event_time,e.response_json,e.log_json,r.created_at
            FROM app.events e JOIN app.runs r ON r.id=e.run_id
            WHERE e.run_id=:run AND e.release_seq<=:cutoff ORDER BY e.release_seq"""),
                    {"run": run_id, "cutoff": evaluation["release_cutoff"]},
                )
            )
            .mappings()
            .all()
        )
        events = [
            dict(row)
            | {"offset_ms": int((row["event_time"] - row["created_at"]).total_seconds() * 1000)}
            for row in event_rows
        ]
        truth_rows = (
            (
                await session.execute(
                    text("""SELECT scenario_instance_id,incident_key,threat_label,
            expected_evidence_keys FROM private.assigned_evaluation_truth(:user,:run)"""),
                    {"user": user["id"], "run": run_id},
                )
            )
            .mappings()
            .all()
        )
        truths = [dict(row) for row in truth_rows]
        versions_row = (
            (
                await session.execute(
                    text("""SELECT rule_version,baseline_version,correlation_version
            FROM app.run_versions WHERE run_id=:run"""),
                    {"run": run_id},
                )
            )
            .mappings()
            .one()
        )
        outputs = compare(events, truths, dict(versions_row))
        batch_id = uuid4()
        config = {
            "dataset_hash": evaluation["dataset_hash"],
            "release_cutoff": evaluation["release_cutoff"],
            "assessment_cutoff": evaluation["assessment_cutoff"].isoformat(),
            "A": "rules-v1",
            "B": dict(versions_row),
            "C": "unavailable",
        }
        await session.execute(
            text("""INSERT INTO app.experiment_batches
            (id,dataset_run_id,requested_by,dataset_hash,config_versions,truncated,status)
            VALUES (:id,:run,:user,:hash,CAST(:config AS jsonb),:truncated,'completed')"""),
            {
                "id": batch_id,
                "run": run_id,
                "user": user["id"],
                "hash": evaluation["dataset_hash"],
                "config": json.dumps(config),
                "truncated": evaluation["truncated"],
            },
        )
        for arm in ("A", "B", "C"):
            data = outputs[arm]
            await session.execute(
                text("""INSERT INTO app.experiment_arms
                (id,batch_id,mode,status,config_snapshot,outputs_json,metrics_json,error_code)
                VALUES (:id,:batch,:mode,:status,CAST(:config AS jsonb),CAST(:outputs AS jsonb),
                        CAST(:metrics AS jsonb),:error)"""),
                {
                    "id": uuid4(),
                    "batch": batch_id,
                    "mode": arm,
                    "status": data["status"],
                    "config": json.dumps(config[arm] if arm != "C" else {"available": False}),
                    "outputs": json.dumps(data.get("findings", [])),
                    "metrics": json.dumps(data["metrics"])
                    if data.get("metrics") is not None
                    else None,
                    "error": data.get("error_code"),
                },
            )
        await session.execute(
            text("""INSERT INTO app.audit_logs
            (id,actor_user_id,actor_role,action,entity_type,entity_id,run_id)
            VALUES (:id,:actor,'instructor','experiment.create','run',:run,:run)"""),
            {"id": uuid4(), "actor": user["id"], "run": run_id},
        )
    return {
        "data": {
            "id": batch_id,
            "dataset_run_id": run_id,
            "dataset_hash": evaluation["dataset_hash"],
            "arms": outputs,
        },
        "meta": Meta(request_id=request.state.request_id).model_dump(),
    }

"""Explicit one-shot operator activation; never called by runtime startup."""

import argparse
import asyncio
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.db.config import database_url
from app.db.session import Database


def reviewed_policy(
    review: dict[str, Any],
    *,
    enable_grade: bool = False,
    enable_practice: bool = False,
    enable_analysis: bool = False,
) -> dict[str, Any]:
    required_status = (
        "approved_for_tutor_grade_practice_analysis"
        if enable_practice or enable_analysis
        else "approved_for_tutor_and_grade"
        if enable_grade
        else "approved_for_lesson_tutor"
    )
    if review.get("status") != required_status:
        raise ValueError("Review is not approved")
    if enable_grade and review.get("grade_mode_verified") is not True:
        raise ValueError("Grade mode has not been verified")
    if enable_practice and review.get("practice_mode_verified") is not True:
        raise ValueError("Practice mode has not been verified")
    if enable_analysis and review.get("analysis_mode_verified") is not True:
        raise ValueError("Analysis mode has not been verified")
    workflow = str(UUID(review["workflow_id"]))
    document = str(UUID(review["document_id"]))
    hashes = review["chunk_hashes"]
    if (
        not isinstance(hashes, dict)
        or not hashes
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value)
            for value in hashes.values()
        )
    ):
        raise ValueError("Invalid reviewed chunk hashes")
    if review.get("execution_mode") != "published_latest_with_response_version_check":
        raise ValueError("Execution policy not approved")
    if review.get("cost_basis") != "groq_free_full_text_no_rerank":
        raise ValueError("Cost basis not verified")
    try:
        bound = Decimal(str(review["call_bound_usd"]))
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid call bound") from exc
    if not bound.is_finite() or bound <= 0:
        raise ValueError("Invalid call bound")
    grade_bound = None
    if enable_grade:
        try:
            grade_bound = Decimal(str(review["grade_call_bound_usd"]))
        except (KeyError, InvalidOperation, TypeError) as exc:
            raise ValueError("Invalid grade call bound") from exc
        if not grade_bound.is_finite() or grade_bound <= 0:
            raise ValueError("Invalid grade call bound")
    extra_bounds: dict[str, Decimal | None] = {}
    for name, enabled in (("practice", enable_practice), ("analysis", enable_analysis)):
        if not enabled:
            extra_bounds[name] = None
            continue
        try:
            value = Decimal(str(review[f"{name}_call_bound_usd"]))
        except (KeyError, InvalidOperation, TypeError) as exc:
            raise ValueError(f"Invalid {name} call bound") from exc
        if not value.is_finite() or value <= 0:
            raise ValueError(f"Invalid {name} call bound")
        extra_bounds[name] = value
    return {
        "workflow": workflow,
        "corpus": f"sentinel-learner-knowledge-1.0.0-{review['observed_at']}",
        "documents": json.dumps([document]),
        "hashes": json.dumps(list(hashes.values())),
        "bound": bound,
        "grade_bound": grade_bound,
        "grade": enable_grade,
        "practice": enable_practice,
        "analysis": enable_analysis,
        "practice_bound": extra_bounds["practice"],
        "analysis_bound": extra_bounds["analysis"],
    }


async def activate(
    database: Database,
    review: dict[str, Any],
    expected_version: int,
    *,
    enable_grade: bool = False,
    enable_practice: bool = False,
    enable_analysis: bool = False,
) -> int:
    values = reviewed_policy(
        review,
        enable_grade=enable_grade,
        enable_practice=enable_practice,
        enable_analysis=enable_analysis,
    )
    async with database.sessions() as session, session.begin():
        if await session.scalar(text("SELECT current_user")) != "migration_owner":
            raise ValueError("Dedicated operator role required")
        await session.execute(text("SELECT pg_advisory_xact_lock(73102007)"))
        before = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1 FOR UPDATE")))
            .mappings()
            .one()
        )
        if before["version"] != expected_version:
            raise ValueError("Policy version changed; inspect before activation")
        after = (
            (
                await session.execute(
                    text("""UPDATE app.tutor_policy SET version=version+1,
                    enabled=true,grade_enabled=:grade,practice_enabled=:practice,
                    analysis_enabled=:analysis,cost_bound_verified=true,workflow_id=:workflow,
                    corpus_revision=:corpus,document_ids=CAST(:documents AS jsonb),
                    chunk_hashes=CAST(:hashes AS jsonb),call_bound_usd=:bound,
                    grade_call_bound_usd=:grade_bound,
                    practice_call_bound_usd=:practice_bound,
                    analysis_call_bound_usd=:analysis_bound
                    WHERE id=1 RETURNING *"""),
                    values,
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            text("""INSERT INTO app.audit_logs
            (id,actor_role,action,entity_type,before_json,after_json,reason)
            VALUES(:id,'system','tutor.release.activate','tutor_policy',
            CAST(:before AS jsonb),CAST(:after AS jsonb),:reason)"""),
            {
                "id": uuid4(),
                "before": json.dumps(dict(before), default=str),
                "after": json.dumps(dict(after), default=str),
                "reason": (
                    "User approved published-latest execution with post-response version check. "
                    "Operator verified Groq Free + Full Text/no rerank; account the full "
                    "per-call ceiling, never infer a zero bill from token counts."
                ),
            },
        )
        return int(after["version"])


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-file", type=Path, required=True)
    parser.add_argument("--expected-version", type=int, required=True)
    parser.add_argument("--enable-grade", action="store_true")
    parser.add_argument("--enable-practice", action="store_true")
    parser.add_argument("--enable-analysis", action="store_true")
    args = parser.parse_args()
    review = json.loads(args.review_file.read_text(encoding="utf8"))
    database = Database(database_url("migration_owner"))
    try:
        version = await activate(
            database,
            review,
            args.expected_version,
            enable_grade=args.enable_grade,
            enable_practice=args.enable_practice,
            enable_analysis=args.enable_analysis,
        )
    finally:
        await database.close()
    print(f"Tutor policy activated: version {version}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        raise SystemExit(
            "Tutor release failed; transaction rolled back. Inspect configuration."
        ) from None

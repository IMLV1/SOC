"""Explicit one-shot operator activation; never called by runtime startup."""

import argparse
import asyncio
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.db.config import database_url
from app.db.session import Database


def reviewed_policy(review: dict[str, Any]) -> dict[str, Any]:
    if review.get("status") != "approved_for_lesson_tutor":
        raise ValueError("Review is not approved")
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
    bound = Decimal(review["call_bound_usd"])
    if not Decimal("0") < bound <= Decimal("0.25"):
        raise ValueError("Invalid call bound")
    return {
        "workflow": workflow,
        "corpus": f"sentinel-learner-knowledge-1.0.0-{review['observed_at']}",
        "documents": json.dumps([document]),
        "hashes": json.dumps(list(hashes.values())),
        "bound": bound,
    }


async def activate(database: Database, review: dict[str, Any], expected_version: int) -> int:
    values = reviewed_policy(review)
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
                    enabled=true,cost_bound_verified=true,workflow_id=:workflow,
                    corpus_revision=:corpus,document_ids=CAST(:documents AS jsonb),
                    chunk_hashes=CAST(:hashes AS jsonb),daily_usd=0.25,call_bound_usd=:bound
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
    args = parser.parse_args()
    review = json.loads(args.review_file.read_text(encoding="utf8"))
    database = Database(database_url("migration_owner"))
    try:
        version = await activate(database, review, args.expected_version)
    finally:
        await database.close()
    print(f"Tutor policy activated: version {version}; daily ceiling USD 0.25")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        raise SystemExit(
            "Tutor release failed; transaction rolled back. Inspect configuration."
        ) from None

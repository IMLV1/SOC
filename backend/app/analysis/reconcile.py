"""Operator-only reconciliation using confirmed provider usage, never an estimate."""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import text

from app.db.config import database_url
from app.db.session import Database


async def reconcile(
    database: Database, analysis: UUID, tokens: int, reason: str, experiment: bool = False
) -> None:
    if tokens < 0 or not reason.strip() or len(reason) > 500:
        raise ValueError("Confirmed nonnegative tokens and audit reference required")
    async with database.sessions() as session, session.begin():
        column = "experiment_arm_id" if experiment else "analysis_id"
        table = "app.experiment_arms" if experiment else "app.analyses"
        run_query = (
            "SELECT b.dataset_run_id AS run_id FROM app.experiment_arms a "
            "JOIN app.experiment_batches b ON b.id=a.batch_id WHERE a.id=:id"
            if experiment
            else "SELECT run_id FROM app.analyses WHERE id=:id"
        )
        row = (await session.execute(text(run_query), {"id": analysis})).first()
        if row is None:
            raise ValueError("Analysis not found")
        await session.execute(
            text("SELECT id FROM app.runs WHERE id=:id FOR UPDATE"), {"id": row.run_id}
        )
        status = await session.scalar(
            text(f"SELECT status FROM {table} WHERE id=:id FOR UPDATE"), {"id": analysis}
        )
        if status in {"queued", "running", "pending"}:
            raise ValueError("Active analysis cannot be reconciled")
        await session.execute(text("SELECT id FROM app.provider_policy WHERE id=1 FOR UPDATE"))
        changed = await session.scalar(
            text(f"""UPDATE app.provider_calls SET status='consumed',
            actual_tokens=:tokens,reconciled_at=clock_timestamp(),reconciliation_reason=:reason
            WHERE {column}=:id AND status='unknown' RETURNING {column}"""),
            {"id": analysis, "tokens": tokens, "reason": reason.strip()},
        )
        if changed is None:
            raise ValueError("No unknown call to reconcile")
        ledgers = (
            (
                await session.execute(
                    text(f"""SELECT l.id FROM app.quota_ledgers l
            JOIN app.quota_reservations r ON r.ledger_id=l.id
            WHERE r.{column}=:id AND r.status='unknown'
            ORDER BY l.scope_key,l.period_start FOR UPDATE OF l"""),
                    {"id": analysis},
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
            text(f"""UPDATE app.quota_reservations SET status='consumed',
            actual_tokens=:tokens,settled_at=clock_timestamp()
            WHERE {column}=:id AND status='unknown'"""),
            {"id": analysis, "tokens": tokens},
        )


async def execute(args: argparse.Namespace) -> None:
    database = Database(database_url("migration_owner"))
    try:
        await reconcile(
            database,
            args.arm or args.analysis,
            args.tokens,
            args.reason,
            experiment=args.arm is not None,
        )
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--analysis", type=UUID)
    target.add_argument("--arm", type=UUID)
    parser.add_argument("--tokens", type=int, required=True)
    parser.add_argument(
        "--reason", required=True, help="Provider usage report reference; no secrets"
    )
    try:
        asyncio.run(execute(parser.parse_args()))
    except Exception:
        raise SystemExit(
            "Reconciliation rejected; check confirmed usage and owner access"
        ) from None


if __name__ == "__main__":
    main()

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from app.db.config import database_url, password_from_file
from app.db.session import Database
from app.knowledge.corpus import load_manifest
from app.knowledge.service import admit, publish, revoke, validate_release


async def run() -> None:
    parser = argparse.ArgumentParser(description="Explicit offline knowledge publisher")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("admit").add_argument("manifest", type=Path)
    prepare_args = sub.add_parser("prepare-real")
    prepare_args.add_argument("release", type=UUID)
    prepare_args.add_argument("--calibration-id")
    calibration_args = sub.add_parser("calibrate-real")
    calibration_args.add_argument("release", type=UUID)
    calibration_args.add_argument("suite", type=Path)
    calibration_args.add_argument("--nonce", required=True)
    validate_args = sub.add_parser("validate")
    validate_args.add_argument("release", type=UUID)
    validate_args.add_argument("suite", type=Path)
    publish_args = sub.add_parser("publish")
    publish_args.add_argument("release", type=UUID)
    publish_args.add_argument("--expected-version", type=int, required=True)
    sub.add_parser("revoke").add_argument("version", type=UUID)
    args = parser.parse_args()
    db = Database(database_url("migration_owner"))
    try:
        if args.command == "calibrate-real":
            from app.knowledge.calibration import calibrate

            url = database_url("migration_owner").set(
                username="worker_runtime",
                password=password_from_file(os.environ["KNOWLEDGE_WORKER_PASSWORD_FILE"]),
            )
            worker = Database(url)
            try:
                await calibrate(
                    db,
                    worker,
                    args.release,
                    json.loads(args.suite.read_text(encoding="utf-8")),
                    args.nonce,
                )
            finally:
                await worker.close()
            print("calibration_passed")
            return
        async with db.sessions() as session, session.begin():
            await session.execute(text("SET LOCAL ROLE knowledge_publisher"))
            if args.command == "admit":
                print(await admit(session, load_manifest(args.manifest)))
            elif args.command == "prepare-real":
                from app.knowledge.real_ingestion import prepare_real

                print(await prepare_real(session, args.release, args.calibration_id))
            elif args.command == "validate":
                result = await validate_release(
                    session, args.release, json.loads(args.suite.read_text(encoding="utf-8"))
                )
                if not result:
                    raise ValueError("Golden validation failed")
                print("validation_passed")
            elif args.command == "publish":
                await publish(session, args.release, args.expected_version)
            else:
                await revoke(session, args.version)
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception:
        raise SystemExit("Knowledge operation failed; no changes committed") from None

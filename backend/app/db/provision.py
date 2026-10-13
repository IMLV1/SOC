"""Explicit, repeatable local provisioning; no public auth/admin routes."""

import argparse
import asyncio
import getpass
import re
from pathlib import Path
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from sqlalchemy import text

from app.db.config import database_url
from app.db.session import Database

PASSWORDS = PasswordHasher()


async def provision_user(
    database: Database,
    *,
    email: str,
    display_name: str,
    password: str,
    role: str,
    daily_runs: int,
    daily_ai_requests: int,
) -> UUID:
    email = email.strip().lower()
    display_name = display_name.strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("Invalid email.")
    if not 1 <= len(display_name) <= 60 or not 12 <= len(password) <= 128:
        raise ValueError("Invalid display name or password length.")
    if role not in ("analyst", "instructor") or min(daily_runs, daily_ai_requests) < 0:
        raise ValueError("Invalid role or explicit quota.")
    async with database.sessions() as session, session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:email,73102003))"),
            {"email": email},
        )
        existing = (
            (
                await session.execute(
                    text("""SELECT u.id,u.display_name,u.password_hash,u.role,u.status,
                        q.daily_runs,q.daily_ai_requests FROM app.users u
                        JOIN app.user_quotas q ON q.user_id=u.id
                        WHERE normalized_email=:email FOR UPDATE OF u,q"""),
                    {"email": email},
                )
            )
            .mappings()
            .first()
        )
        if existing:
            same = (
                existing["display_name"] == display_name
                and existing["role"] == role
                and existing["status"] == "active"
                and existing["daily_runs"] == daily_runs
                and existing["daily_ai_requests"] == daily_ai_requests
            )
            if not same or not PASSWORDS.verify(existing["password_hash"], password):
                raise ValueError("Existing account differs; provisioning never overrides it.")
            return UUID(str(existing["id"]))
        user_id = uuid4()
        password_hash = await asyncio.to_thread(PASSWORDS.hash, password)
        await session.execute(
            text("""INSERT INTO app.users
                    (id,normalized_email,display_name,password_hash,role,status)
                    VALUES (:id,:email,:name,:hash,:role,'active')"""),
            {
                "id": user_id,
                "email": email,
                "name": display_name,
                "hash": password_hash,
                "role": role,
            },
        )
        await session.execute(
            text("""INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests)
                    VALUES (:id,:runs,:ai)"""),
            {"id": user_id, "runs": daily_runs, "ai": daily_ai_requests},
        )
        await session.execute(
            text("""INSERT INTO app.audit_logs(id,actor_role,action,entity_type,entity_id,reason)
                    VALUES (:id,'system','user.provision','user',:user,
                            'Explicit operator provisioning')"""),
            {"id": uuid4(), "user": user_id},
        )
        return user_id


async def assign(database: Database, instructor: UUID, analyst: UUID) -> None:
    if instructor == analyst:
        raise ValueError("Self assignment is not valid.")
    async with database.sessions() as session, session.begin():
        users = (
            (
                await session.execute(
                    text("""SELECT id,role,status FROM app.users WHERE id IN (:a,:b)
                        ORDER BY id FOR UPDATE"""),
                    {"a": instructor, "b": analyst},
                )
            )
            .mappings()
            .all()
        )
        expected = {instructor: "instructor", analyst: "analyst"}
        if len(users) != 2 or any(
            row["role"] != expected[row["id"]] or row["status"] != "active" for row in users
        ):
            raise ValueError("Assignment needs an active Instructor and Analyst.")
        created = await session.scalar(
            text("""INSERT INTO app.instructor_assignments
                    (instructor_user_id,analyst_user_id)
                    VALUES (:a,:b) ON CONFLICT DO NOTHING RETURNING analyst_user_id"""),
            {"a": instructor, "b": analyst},
        )
        if created:
            await session.execute(
                text("""INSERT INTO app.audit_logs
                        (id,actor_role,action,entity_type,entity_id,reason)
                        VALUES (:id,'system','assignment.provision','user',:user,:reason)"""),
                {"id": uuid4(), "user": analyst, "reason": f"Assigned by operator to {instructor}"},
            )


async def execute(args: argparse.Namespace) -> None:
    database = Database(database_url("migration_owner"))
    try:
        if args.command == "user":
            if args.password_file:
                password = Path(args.password_file).read_text(encoding="utf-8").rstrip("\r\n")
            else:
                password = getpass.getpass("Password (12–128 characters): ")
                if password != getpass.getpass("Confirm password: "):
                    raise ValueError("Password confirmation differs.")
            user_id = await provision_user(
                database,
                email=args.email,
                display_name=args.display_name,
                password=password,
                role=args.role,
                daily_runs=args.daily_runs,
                daily_ai_requests=args.daily_ai_requests,
            )
            print(f"Account ready: {user_id}")
        else:
            await assign(database, UUID(args.instructor), UUID(args.analyst))
            print("Assignment ready.")
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    user = commands.add_parser("user")
    user.add_argument("--email", required=True)
    user.add_argument("--display-name", required=True)
    user.add_argument("--role", choices=["analyst", "instructor"], required=True)
    user.add_argument("--daily-runs", type=int, required=True)
    user.add_argument("--daily-ai-requests", type=int, required=True)
    user.add_argument("--password-file")
    assignment = commands.add_parser("assign")
    assignment.add_argument("--instructor", required=True)
    assignment.add_argument("--analyst", required=True)
    try:
        asyncio.run(execute(parser.parse_args()))
    except Exception:
        raise SystemExit(
            "Provisioning failed; check input, existing account and owner configuration."
        ) from None


if __name__ == "__main__":
    main()

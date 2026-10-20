import hashlib
import hmac
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserView
from app.db.session import Database

SESSION = "soc_session"
CHALLENGE = "soc_challenge"


class AuthError(Exception):
    def __init__(self, status: int, code: str) -> None:
        self.status = status
        self.code = code


def digest(value: str) -> str:
    # Database rows store only a digest of opaque tokens; plaintext stays in cookies.
    return hashlib.sha256(value.encode()).hexdigest()


def csrf(token: str) -> str:
    # Domain-separated derivation permits re-reading CSRF without storing raw tokens.
    return hmac.new(token.encode(), b"soc:csrf:v1", hashlib.sha256).hexdigest()


def database(request: Request) -> Database:
    value: Database | None = request.app.state.database
    if value is None:
        raise AuthError(503, "SERVICE_UNAVAILABLE")
    return value


def origin(request: Request) -> None:
    # Origin validation applies even to login/register, where no session exists yet.
    allowed = os.getenv("AUTH_ORIGINS", "https://localhost").split(",")
    if request.headers.get("origin") not in allowed:
        raise AuthError(403, "CSRF_INVALID")


def set_cookie(response: Response, name: str, token: str, age: int) -> None:
    # HttpOnly prevents script reads; Secure is enabled by default outside explicit local setup.
    response.set_cookie(
        name,
        token,
        max_age=age,
        httponly=True,
        secure=os.getenv("AUTH_COOKIE_SECURE", "true") != "false",
        samesite="lax",
        path="/",
    )


def clear_cookie(response: Response, name: str) -> None:
    response.delete_cookie(
        name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=os.getenv("AUTH_COOKIE_SECURE", "true") != "false",
    )


def view(row: Mapping[str, Any]) -> UserView:
    return UserView(
        id=row["id"],
        display_name=row["display_name"],
        email=row["normalized_email"],
        role=row["role"],
        status=row["status"],
    )


async def identity(session: AsyncSession, request: Request) -> Mapping[str, Any] | None:
    token = request.cookies.get(SESSION, "")
    if not token or len(token) > 128:
        return None
    # Lock the user first, then its session, matching account-disable lock ordering.
    row = (
        (
            await session.execute(
                text("""
        SELECT u.id,u.normalized_email,u.display_name,u.role,u.status,
               s.id AS session_id,s.expires_at,s.csrf_hash
        FROM app.users u JOIN app.auth_sessions s ON s.user_id=u.id
        WHERE s.token_hash=:hash AND s.revoked_at IS NULL AND s.expires_at>now()
        FOR SHARE OF u
    """),
                {"hash": digest(token)},
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["status"] != "active":
        return None
    active = await session.scalar(
        text("""SELECT id FROM app.auth_sessions
        WHERE id=:id AND revoked_at IS NULL AND expires_at>now() FOR UPDATE"""),
        {"id": row["session_id"]},
    )
    return dict(row) if active else None


async def require_user(session: AsyncSession, request: Request) -> Mapping[str, Any]:
    row = await identity(session, request)
    if row is None:
        raise AuthError(401, "AUTH_REQUIRED")
    return row


async def csrf_check(session: AsyncSession, request: Request) -> None:
    # Logged-in mutations use the session token; anonymous auth forms use a short-lived challenge.
    origin(request)
    supplied = request.headers.get("x-csrf-token", "")
    user = await identity(session, request)
    if user:
        expected = user["csrf_hash"]
    else:
        token = request.cookies.get(CHALLENGE, "")
        expected = (
            await session.scalar(
                text("""SELECT csrf_hash FROM app.auth_challenges
            WHERE token_hash=:hash AND consumed_at IS NULL AND expires_at>now() FOR UPDATE"""),
                {"hash": digest(token)},
            )
            if token and len(token) <= 128
            else None
        )
    if expected is None or not hmac.compare_digest(digest(supplied), expected):
        raise AuthError(403, "CSRF_INVALID")


async def consume_challenge(session: AsyncSession, request: Request) -> None:
    await session.execute(
        text("""UPDATE app.auth_challenges SET consumed_at=now()
        WHERE token_hash=:hash AND consumed_at IS NULL"""),
        {"hash": digest(request.cookies.get(CHALLENGE, ""))},
    )


async def authorize_owner(user: Mapping[str, Any], owner: UUID) -> None:
    if user["id"] != owner:
        raise AuthError(404, "NOT_FOUND")


async def authorize_assignment(session: AsyncSession, user: Mapping[str, Any], owner: UUID) -> None:
    # Instructor role alone is insufficient: each analyst must be assigned explicitly.
    if user["role"] != "instructor":
        raise AuthError(403, "FORBIDDEN")
    assigned = await session.scalar(
        text("""SELECT 1 FROM app.instructor_assignments
        WHERE instructor_user_id=:instructor AND analyst_user_id=:owner"""),
        {"instructor": user["id"], "owner": owner},
    )
    if not assigned:
        raise AuthError(404, "NOT_FOUND")


async def audit(session: AsyncSession, action: str, user: UUID, request: Request) -> None:
    await session.execute(
        text("""INSERT INTO app.audit_logs
        (id,actor_user_id,actor_role,action,entity_type,entity_id,request_id)
        VALUES (:id,:user,'system',:action,'user',:user,:request)"""),
        {"id": uuid4(), "user": user, "action": action, "request": request.state.request_id},
    )


async def rate_limit(request: Request, operation: str, email: str = "") -> None:
    # Independent commit: failed passwords also consume the rate limit across API processes.
    # Sort keys to acquire per-operation counters in a stable order when both IP and email apply.
    keys = [f"{operation}:ip:{request.client.host if request.client else 'unknown'}"]
    if email:
        keys.append(f"{operation}:email:{email}")
    window = datetime.now(UTC).replace(second=0, microsecond=0)
    counts = []
    async with database(request).sessions() as session, session.begin():
        for key in sorted(keys):
            count = await session.scalar(
                text("""INSERT INTO app.auth_rate_limits
                (key_hash,window_start,request_count) VALUES (:key,:window,1)
                ON CONFLICT(key_hash,window_start) DO UPDATE
                SET request_count=app.auth_rate_limits.request_count+1 RETURNING request_count"""),
                {"key": digest(key), "window": window},
            )
            counts.append(int(count or 0))
    if any(count > (30 if operation == "csrf" else 10) for count in counts):
        raise AuthError(429, "RATE_LIMITED")

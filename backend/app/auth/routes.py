import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text

from app.auth import service as auth
from app.auth.models import (
    AuthMeta,
    CsrfData,
    CsrfEnvelope,
    LoginInput,
    QuotaData,
    QuotaEnvelope,
    RegisterInput,
    SessionData,
    SessionEnvelope,
    Strict,
    UserEnvelope,
)
from app.db.provision import PASSWORDS
from app.http_models import ErrorEnvelope

DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


async def json_only(request: Request) -> None:
    if request.method == "POST":
        auth.origin(request)
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            raise auth.AuthError(415, "UNSUPPORTED_MEDIA_TYPE")


router = APIRouter(
    prefix="/api/v1",
    tags=["Auth"],
    dependencies=[Depends(json_only)],
    responses={
        status: {"model": ErrorEnvelope} for status in (400, 401, 403, 409, 413, 415, 422, 429, 503)
    },
)


def meta(request: Request) -> AuthMeta:
    return AuthMeta(request_id=request.state.request_id)


@router.get("/auth/csrf", response_model=CsrfEnvelope, operation_id="auth_csrf")
async def csrf_token(request: Request, response: Response) -> CsrfEnvelope:
    await auth.rate_limit(request, "csrf")
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.identity(session, request)
        if user:
            token = request.cookies[auth.SESSION]
        else:
            token = request.cookies.get(auth.CHALLENGE, "")
            valid = (
                await session.scalar(
                    text("""SELECT id FROM app.auth_challenges
                WHERE token_hash=:hash AND consumed_at IS NULL AND expires_at>now()"""),
                    {"hash": auth.digest(token)},
                )
                if token and len(token) <= 128
                else None
            )
            if not valid:
                token = secrets.token_urlsafe(32)
                await session.execute(
                    text("""INSERT INTO app.auth_challenges
                    (id,token_hash,csrf_hash,expires_at) VALUES (:id,:token,:csrf,:expires)"""),
                    {
                        "id": uuid4(),
                        "token": auth.digest(token),
                        "csrf": auth.digest(auth.csrf(token)),
                        "expires": datetime.now(UTC) + timedelta(minutes=15),
                    },
                )
                auth.set_cookie(response, auth.CHALLENGE, token, 900)
    return CsrfEnvelope(data=CsrfData(csrf_token=auth.csrf(token)), meta=meta(request))


@router.post(
    "/auth/register", response_model=UserEnvelope, status_code=201, operation_id="auth_register"
)
async def register(body: RegisterInput, request: Request, response: Response) -> UserEnvelope:
    await auth.rate_limit(request, "register", body.email)
    async with auth.database(request).sessions() as session, session.begin():
        await auth.csrf_check(session, request)
        hashed = await asyncio.to_thread(PASSWORDS.hash, body.password)
        user_id = uuid4()
        row = (
            (
                await session.execute(
                    text("""INSERT INTO app.users
            (id,normalized_email,display_name,password_hash,role,status)
            VALUES (:id,:email,:name,:hash,'analyst','active')
            ON CONFLICT(normalized_email) DO NOTHING RETURNING *"""),
                    {"id": user_id, "email": body.email, "name": body.display_name, "hash": hashed},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise auth.AuthError(409, "REGISTRATION_FAILED")
        await session.execute(
            text("""INSERT INTO app.user_quotas
            (user_id,daily_runs,daily_ai_requests) VALUES (:id,10,20)"""),
            {"id": user_id},
        )
        await auth.consume_challenge(session, request)
        await auth.audit(session, "auth.register", user_id, request)
        result = auth.view(dict(row))
    auth.clear_cookie(response, auth.CHALLENGE)
    return UserEnvelope(data=result, meta=meta(request))


@router.post("/auth/login", response_model=SessionEnvelope, operation_id="auth_login")
async def login(body: LoginInput, request: Request, response: Response) -> SessionEnvelope:
    await auth.rate_limit(request, "login", body.email)
    async with auth.database(request).sessions() as session, session.begin():
        await auth.csrf_check(session, request)
        row = (
            (
                await session.execute(
                    text("""SELECT * FROM app.users
            WHERE normalized_email=:email FOR SHARE"""),
                    {"email": body.email},
                )
            )
            .mappings()
            .first()
        )
        correct: bool
        try:
            correct = await asyncio.to_thread(
                PASSWORDS.verify, row["password_hash"] if row else DUMMY_HASH, body.password
            )
        except VerificationError:
            correct = False
        if not correct or row is None or row["status"] != "active":
            raise auth.AuthError(401, "LOGIN_FAILED")
        await session.execute(
            text("""UPDATE app.auth_sessions SET revoked_at=now()
            WHERE token_hash=:hash AND revoked_at IS NULL"""),
            {"hash": auth.digest(request.cookies.get(auth.SESSION, ""))},
        )
        token = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + timedelta(hours=24)
        await session.execute(
            text("""INSERT INTO app.auth_sessions
            (id,user_id,token_hash,csrf_hash,expires_at)
            VALUES (:id,:user,:token,:csrf,:expires)"""),
            {
                "id": uuid4(),
                "user": row["id"],
                "token": auth.digest(token),
                "csrf": auth.digest(auth.csrf(token)),
                "expires": expires,
            },
        )
        await auth.consume_challenge(session, request)
        await auth.audit(session, "auth.login", row["id"], request)
        result = SessionData(
            user=auth.view(dict(row)), expires_at=expires, csrf_token=auth.csrf(token)
        )
    auth.set_cookie(response, auth.SESSION, token, 86400)
    auth.clear_cookie(response, auth.CHALLENGE)
    return SessionEnvelope(data=result, meta=meta(request))


@router.get("/auth/session", response_model=SessionEnvelope, operation_id="auth_session")
async def current_session(request: Request) -> SessionEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        return SessionEnvelope(
            data=SessionData(
                user=auth.view(user),
                expires_at=user["expires_at"],
                csrf_token=auth.csrf(request.cookies[auth.SESSION]),
            ),
            meta=meta(request),
        )


@router.post("/auth/logout", status_code=204, operation_id="auth_logout")
async def logout(body: Strict, request: Request) -> Response:
    auth.origin(request)
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.identity(session, request)
        if user:
            await auth.csrf_check(session, request)
            await session.execute(
                text("UPDATE app.auth_sessions SET revoked_at=now() WHERE id=:id"),
                {"id": user["session_id"]},
            )
            await auth.audit(session, "auth.logout", user["id"], request)
    response = Response(status_code=204)
    auth.clear_cookie(response, auth.SESSION)
    auth.clear_cookie(response, auth.CHALLENGE)
    return response


@router.get("/me", response_model=UserEnvelope, operation_id="auth_me")
async def me(request: Request) -> UserEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        return UserEnvelope(data=auth.view(user), meta=meta(request))


@router.get("/me/quota", response_model=QuotaEnvelope, operation_id="auth_quota")
async def quota(request: Request) -> QuotaEnvelope:
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.require_user(session, request)
        row = (
            (
                await session.execute(
                    text("""SELECT q.daily_runs,q.daily_ai_requests,
            coalesce(l.run_count,0) AS run_count,coalesce(l.ai_request_count,0) AS ai_request_count,
            coalesce(l.reserved_tokens,0) AS reserved_tokens,
            coalesce(l.consumed_tokens,0) AS consumed_tokens
            FROM app.user_quotas q LEFT JOIN app.quota_ledgers l ON l.user_id=q.user_id
            AND l.period_start=(now() AT TIME ZONE 'UTC')::date WHERE q.user_id=:id"""),
                    {"id": user["id"]},
                )
            )
            .mappings()
            .one()
        )
        reset = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        return QuotaEnvelope(data=QuotaData(**row, reset_at=reset), meta=meta(request))

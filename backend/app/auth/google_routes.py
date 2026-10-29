"""Server-side OAuth. Never automatically bind an existing account by email."""

import asyncio
import hmac
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import Field
from sqlalchemy import text

from app.auth import google_oidc as oidc
from app.auth import service as auth
from app.auth.models import AuthMeta, Strict
from app.auth.routes import DUMMY_HASH, json_only
from app.db.provision import PASSWORDS
from app.http_models import ErrorEnvelope
from app.input_validation import InputModel

BINDING = "soc_google_flow"


class GoogleStartInput(InputModel):
    purpose: Literal["login", "link"] = "login"
    password: str | None = Field(default=None, min_length=5, max_length=128)


class GoogleStartData(Strict):
    authorization_url: str


class GoogleStartEnvelope(Strict):
    data: GoogleStartData
    meta: AuthMeta


class GoogleStatusData(Strict):
    available: bool
    linked: bool
    link_available: bool = True
    provider_origin: str | None = None


class GoogleStatusEnvelope(Strict):
    data: GoogleStatusData
    meta: AuthMeta


router = APIRouter(
    prefix="/api/v1/auth/google",
    tags=["Auth"],
    responses={
        status: {"model": ErrorEnvelope} for status in (400, 401, 403, 409, 415, 422, 429, 503)
    },
)


def configuration() -> oidc.GoogleConfig:
    try:
        config = oidc.config_from_env(os.environ)
    except oidc.GoogleOIDCError:
        config = None
    if config is None:
        raise auth.AuthError(503, "GOOGLE_UNAVAILABLE")
    return config


@router.get("/status", response_model=GoogleStatusEnvelope, operation_id="google_status")
async def status(request: Request) -> GoogleStatusEnvelope:
    from app.auth import supabase_provider

    if supabase_provider.enabled():
        settings = await supabase_provider.call("GET", "/settings")
        identity = getattr(request.state, "supabase_identity", None)
        async with auth.database(request).sessions() as session, session.begin():
            user = await auth.identity(session, request)
            linked = bool(user and identity and identity.google_linked)
        return GoogleStatusEnvelope(
            data=GoogleStatusData(
                available=bool(settings.get("external", {}).get("google")),
                linked=linked,
                link_available=False,
                provider_origin=supabase_provider.configuration()[0],
            ),
            meta=AuthMeta(request_id=request.state.request_id),
        )
    linked = False
    async with auth.database(request).sessions() as session, session.begin():
        user = await auth.identity(session, request)
        if user:
            linked = bool(
                await session.scalar(
                    text("SELECT 1 FROM app.google_identities WHERE user_id=:user"),
                    {"user": user["id"]},
                )
            )
    return GoogleStatusEnvelope(
        data=GoogleStatusData(available=oidc.configured(), linked=linked),
        meta=AuthMeta(request_id=request.state.request_id),
    )


@router.post(
    "/start",
    response_model=GoogleStartEnvelope,
    operation_id="google_start",
    dependencies=[Depends(json_only)],
)
async def start(
    body: GoogleStartInput, request: Request, response: Response
) -> GoogleStartEnvelope:
    from app.auth import supabase_provider, supabase_service

    if supabase_provider.enabled():
        return GoogleStartEnvelope(
            data=GoogleStartData(
                authorization_url=await supabase_service.google_start(
                    request, response, body.purpose
                )
            ),
            meta=AuthMeta(request_id=request.state.request_id),
        )
    config = configuration()
    await auth.rate_limit(request, "google_start")
    state, binding, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
    async with auth.database(request).sessions() as session, session.begin():
        await auth.csrf_check(session, request)
        user = await auth.identity(session, request)
        if body.purpose == "link":
            if user is None:
                raise auth.AuthError(401, "AUTH_REQUIRED")
            hashed = await session.scalar(
                text("SELECT password_hash FROM app.users WHERE id=:id"), {"id": user["id"]}
            )
            correct: bool
            try:
                correct = await asyncio.to_thread(
                    PASSWORDS.verify, hashed or DUMMY_HASH, body.password or ""
                )
            except VerificationError:
                correct = False
            if not hashed or not correct:
                raise auth.AuthError(401, "REAUTH_REQUIRED")
        elif user is not None or body.password is not None:
            raise auth.AuthError(409, "GOOGLE_FLOW_INVALID")
        await session.execute(
            text("""INSERT INTO app.google_flows
            (state_hash,binding_hash,session_hash,nonce_hash,verifier,purpose,user_id,session_id)
            VALUES (:state,:binding,:session,:nonce,:verifier,:purpose,:user,:sid)"""),
            {
                "state": auth.digest(state),
                "binding": auth.digest(binding),
                "session": auth.digest(request.cookies.get(auth.SESSION, "")),
                "nonce": auth.digest(nonce),
                "verifier": verifier,
                "purpose": body.purpose,
                "user": user["id"] if user else None,
                "sid": user["session_id"] if user else None,
            },
        )
        await auth.consume_challenge(session, request)
    # JSON POST sets the browser binding cookie before navigation to Google.
    auth.set_cookie(response, BINDING, binding, 300)
    return GoogleStartEnvelope(
        data=GoogleStartData(
            authorization_url=oidc.authorization_url(config, state, nonce, verifier)
        ),
        meta=AuthMeta(request_id=request.state.request_id),
    )


@router.get(
    "/callback", response_class=RedirectResponse, operation_id="google_callback", status_code=303
)
async def callback(request: Request) -> RedirectResponse:
    from app.auth import supabase_provider, supabase_service

    if supabase_provider.enabled():
        return await supabase_service.google_callback(request)
    destination = "/login?google=failed"
    token = None
    try:
        config = configuration()
        await auth.rate_limit(request, "google_callback")
        params = request.query_params
        state = params.get("state", "")
        binding = request.cookies.get(BINDING, "")
        if (
            len(params.getlist("state")) != 1
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", state)
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", binding)
        ):
            raise auth.AuthError(400, "GOOGLE_FLOW_INVALID")
        async with auth.database(request).sessions() as session, session.begin():
            row = (
                (
                    await session.execute(
                        text("""SELECT * FROM app.google_flows
                WHERE state_hash=:state AND consumed_at IS NULL AND expires_at>now()
                FOR UPDATE"""),
                        {"state": auth.digest(state)},
                    )
                )
                .mappings()
                .first()
            )
            if (
                row is None
                or not hmac.compare_digest(row["binding_hash"], auth.digest(binding))
                or not hmac.compare_digest(
                    row["session_hash"], auth.digest(request.cookies.get(auth.SESSION, ""))
                )
            ):
                raise auth.AuthError(400, "GOOGLE_FLOW_INVALID")
            flow = dict(row)
            await session.execute(
                text("""UPDATE app.google_flows SET consumed_at=now(),verifier=NULL
                WHERE state_hash=:state"""),
                {"state": auth.digest(state)},
            )
        # Commit consume BEFORE external IO: failures/denial/timeout cannot replay the code.
        if params.get("error") or len(params.getlist("code")) != 1:
            raise auth.AuthError(400, "GOOGLE_LOGIN_FAILED")
        identity = await oidc.exchange(config, params["code"], flow["verifier"], flow["nonce_hash"])
        async with auth.database(request).sessions() as session, session.begin():
            # Serialize identity creation/link decisions; unique DB keys remain authoritative.
            await session.execute(text("SELECT pg_advisory_xact_lock(73102018)"))
            if not await session.scalar(
                text("SELECT now()<:expires"), {"expires": flow["expires_at"]}
            ):
                raise auth.AuthError(400, "GOOGLE_FLOW_INVALID")
            existing = (
                (
                    await session.execute(
                        text("""SELECT u.* FROM app.users u
                JOIN app.google_identities g ON g.user_id=u.id
                WHERE g.issuer=:issuer AND g.subject=:subject FOR UPDATE OF u"""),
                        {"issuer": identity.issuer, "subject": identity.subject},
                    )
                )
                .mappings()
                .first()
            )
            if flow["purpose"] == "link":
                user = await auth.require_user(session, request)
                if user["id"] != flow["user_id"] or user["session_id"] != flow["session_id"]:
                    raise auth.AuthError(401, "AUTH_REQUIRED")
                if existing and existing["id"] != user["id"]:
                    raise auth.AuthError(409, "GOOGLE_LINK_FAILED")
                if identity.email != user["normalized_email"]:
                    raise auth.AuthError(409, "GOOGLE_LINK_FAILED")
                user_id = user["id"]
            elif existing:
                user_id = existing["id"]
                if existing["status"] != "active":
                    raise auth.AuthError(401, "AUTH_REQUIRED")
            else:
                user_id = uuid4()
                created = await session.scalar(
                    text("""INSERT INTO app.users
                    (id,normalized_email,display_name,password_hash,role,status)
                    VALUES (:id,:email,:name,NULL,'analyst','active')
                    ON CONFLICT(normalized_email) DO NOTHING RETURNING id"""),
                    {"id": user_id, "email": identity.email, "name": identity.display_name},
                )
                if created is None:
                    destination = "/login?google=link_required"
                    raise auth.AuthError(409, "GOOGLE_LINK_REQUIRED")
                await session.execute(
                    text("""INSERT INTO app.user_quotas
                    (user_id,daily_runs,daily_ai_requests) VALUES (:id,10,20)"""),
                    {"id": user_id},
                )
                await auth.audit(session, "auth.google.register", user_id, request)
            if existing is None:
                inserted = await session.scalar(
                    text("""INSERT INTO app.google_identities
                    (user_id,issuer,subject) VALUES (:user,:issuer,:subject)
                    ON CONFLICT DO NOTHING RETURNING user_id"""),
                    {"user": user_id, "issuer": identity.issuer, "subject": identity.subject},
                )
                if inserted is None:
                    raise auth.AuthError(409, "GOOGLE_LINK_FAILED")
            # Rotate the SOC session on both login and linking. Google tokens are never sessions.
            await session.execute(
                text("""UPDATE app.auth_sessions SET revoked_at=now()
                WHERE token_hash=:hash AND revoked_at IS NULL"""),
                {"hash": auth.digest(request.cookies.get(auth.SESSION, ""))},
            )
            token = secrets.token_urlsafe(32)
            await session.execute(
                text("""INSERT INTO app.auth_sessions
                (id,user_id,token_hash,csrf_hash,expires_at)
                VALUES (:id,:user,:token,:csrf,:expires)"""),
                {
                    "id": uuid4(),
                    "user": user_id,
                    "token": auth.digest(token),
                    "csrf": auth.digest(auth.csrf(token)),
                    "expires": datetime.now(UTC) + timedelta(hours=24),
                },
            )
            await auth.audit(session, "auth.google." + flow["purpose"], user_id, request)
        destination = "/account?google=success"
    except (auth.AuthError, oidc.GoogleOIDCError):
        token = None
    # Relative fixed destinations prevent Host-header/open redirect and never echo Google input.
    response = RedirectResponse(destination, status_code=303)
    auth.clear_cookie(response, BINDING)
    auth.clear_cookie(response, auth.CHALLENGE)
    response.headers["Referrer-Policy"] = "no-referrer"
    if token:
        auth.set_cookie(response, auth.SESSION, token, 86400)
    return response

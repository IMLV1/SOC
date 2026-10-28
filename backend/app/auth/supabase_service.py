"""Supabase authentication bridged to SOC's existing opaque-cookie/CSRF boundary."""

import base64
import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text

from app.auth import service as auth
from app.auth import supabase_provider as provider
from app.auth.models import LoginInput, RegisterInput, SessionData, SessionEnvelope, UserEnvelope

BINDING = "soc_supabase_flow"


async def prepare(request: Request) -> None:
    """Network validation/refresh completes before any domain transaction is opened."""
    cookie = request.cookies.get(auth.SESSION, "")
    if not cookie or len(cookie) > 128:
        return
    async with auth.database(request).sessions() as session, session.begin():
        row = (
            (
                await session.execute(
                    text("""
            SELECT p.*,s.expires_at FROM app.supabase_sessions p
            JOIN app.auth_sessions s ON s.id=p.session_id
            JOIN app.users u ON u.id=s.user_id AND u.status='active'
            JOIN app.supabase_identities i ON i.subject=p.subject AND i.user_id=u.id
            WHERE s.token_hash=:hash AND s.revoked_at IS NULL AND s.expires_at>now()
        """),
                    {"hash": auth.digest(cookie)},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        return
    tokens = provider.unseal(row["encrypted_tokens"])
    if row["access_expires_at"].timestamp() < time.time() + 60:
        if row["refresh_lease"] is not None and row["refresh_deadline"].timestamp() <= time.time():
            raise auth.AuthError(401, "AUTH_REQUIRED")
        lease = uuid4()
        async with auth.database(request).sessions() as session, session.begin():
            claimed = await session.scalar(
                text("""
                UPDATE app.supabase_sessions p SET refresh_lease=:lease,
                refresh_deadline=now()+interval '45 seconds'
                WHERE session_id=:id AND version=:version
                AND refresh_lease IS NULL
                AND EXISTS(SELECT 1 FROM app.auth_sessions s WHERE s.id=p.session_id
                  AND s.revoked_at IS NULL AND s.expires_at>now()) RETURNING session_id
            """),
                {"id": row["session_id"], "version": row["version"], "lease": lease},
            )
        # Do not reuse a refresh token after a crash/unknown outcome. Re-login is safe.
        if claimed is None:
            raise auth.AuthError(503, "AUTH_REFRESH_PENDING")
        try:
            tokens = await provider.call(
                "POST",
                "/token?grant_type=refresh_token",
                payload={"refresh_token": tokens["refresh_token"]},
            )
            identity = await provider.verify(tokens)
            if (
                identity.subject != row["subject"]
                or identity.session_id != row["provider_session_id"]
            ):
                raise auth.AuthError(401, "AUTH_REQUIRED")
            encrypted = provider.seal(tokens)
            async with auth.database(request).sessions() as session, session.begin():
                changed = await session.scalar(
                    text("""
                    UPDATE app.supabase_sessions p SET encrypted_tokens=:tokens,
                    access_expires_at=:expires,version=version+1,
                    refresh_lease=NULL,refresh_deadline=NULL
                    WHERE session_id=:id AND version=:version AND refresh_lease=:lease
                    AND refresh_deadline>now()
                    AND EXISTS(SELECT 1 FROM app.auth_sessions s WHERE s.id=p.session_id
                      AND s.revoked_at IS NULL AND s.expires_at>now()) RETURNING session_id
                """),
                    {
                        "id": row["session_id"],
                        "version": row["version"],
                        "lease": lease,
                        "tokens": encrypted,
                        "expires": datetime.fromtimestamp(identity.expires_at, UTC),
                    },
                )
                if changed is None:
                    raise auth.AuthError(401, "AUTH_REQUIRED")
        except auth.AuthError:
            # Keep the lease on unknown network failure: never dispatch the same token twice.
            raise
    else:
        identity = await provider.verify(tokens)
    if identity.subject != row["subject"] or identity.session_id != row["provider_session_id"]:
        raise auth.AuthError(401, "AUTH_REQUIRED")
    request.state.supabase_identity = identity
    request.state.supabase_access_token = tokens["access_token"]


async def establish(
    request: Request,
    response: Response,
    tokens: dict[str, Any],
) -> SessionData:
    from app.auth.routes import create_session

    identity = await provider.verify(tokens)
    encrypted = provider.seal(tokens)
    async with auth.database(request).sessions() as session, session.begin():
        # Identity guard precedes users/sessions/quota for concurrent first login.
        await session.execute(text("SELECT pg_advisory_xact_lock(73102021)"))
        active = await session.scalar(
            text("SELECT ops.supabase_session_active(:subject,:session)"),
            {"subject": identity.subject, "session": identity.session_id},
        )
        if not active:
            raise auth.AuthError(401, "AUTH_REQUIRED")
        row = (
            (
                await session.execute(
                    text("""
            SELECT u.* FROM app.users u JOIN app.supabase_identities i ON i.user_id=u.id
            WHERE i.subject=:subject FOR UPDATE OF u
        """),
                    {"subject": identity.subject},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            user_id = uuid4()
            row = (
                (
                    await session.execute(
                        text("""
                INSERT INTO app.users(id,normalized_email,display_name,password_hash,role,status)
                VALUES (:id,:email,:name,NULL,'analyst','active')
                ON CONFLICT(normalized_email) DO NOTHING RETURNING *
            """),
                        {"id": user_id, "email": identity.email, "name": identity.display_name},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                # Equal email is not proof of ownership of an existing SOC account.
                raise auth.AuthError(409, "ACCOUNT_LINK_REQUIRED")
            await session.execute(
                text("""
                INSERT INTO app.supabase_identities(subject,user_id) VALUES (:subject,:user)
            """),
                {"subject": identity.subject, "user": user_id},
            )
            await session.execute(
                text("""
                INSERT INTO app.user_quotas(user_id,daily_runs,daily_ai_requests) VALUES (:id,10,20)
            """),
                {"id": user_id},
            )
            await auth.audit(session, "auth.supabase.register", user_id, request)
        if row["status"] != "active":
            raise auth.AuthError(401, "AUTH_REQUIRED")
        token, expires = await create_session(session, request, row["id"])
        await session.execute(
            text("""
            INSERT INTO app.supabase_sessions
              (session_id,subject,provider_session_id,encrypted_tokens,access_expires_at)
            SELECT id,:subject,:provider,:tokens,:expires FROM app.auth_sessions
            WHERE token_hash=:hash
        """),
            {
                "subject": identity.subject,
                "provider": identity.session_id,
                "tokens": encrypted,
                "expires": datetime.fromtimestamp(identity.expires_at, UTC),
                "hash": auth.digest(token),
            },
        )
        await auth.audit(session, "auth.supabase.login", row["id"], request)
        result = SessionData(
            user=auth.view(dict(row)), expires_at=expires, csrf_token=auth.csrf(token)
        )
    auth.set_cookie(response, auth.SESSION, token, 86400)
    auth.clear_cookie(response, auth.CHALLENGE)
    return result


async def password_auth(
    body: LoginInput,
    request: Request,
    response: Response,
    *,
    register: bool,
) -> UserEnvelope | SessionEnvelope | JSONResponse:
    from app.auth.routes import meta

    provider.configuration()
    provider.cipher()
    await auth.rate_limit(request, "register" if register else "login", body.email)
    async with auth.database(request).sessions() as session, session.begin():
        await auth.csrf_check(session, request)
        await auth.consume_challenge(session, request)
    if register:
        if not isinstance(body, RegisterInput):
            raise auth.AuthError(422, "VALIDATION_ERROR")
        tokens = await provider.call(
            "POST",
            "/signup",
            payload={
                "email": body.email,
                "password": body.password,
                "data": {"display_name": body.display_name},
            },
        )
        if not tokens.get("access_token"):
            # Confirmation policy belongs to Supabase; never manufacture a session.
            return JSONResponse(
                status_code=202,
                content={
                    "data": {"status": "email_confirmation_required"},
                    "meta": {"request_id": request.state.request_id},
                },
            )
    else:
        tokens = await provider.call(
            "POST",
            "/token?grant_type=password",
            payload={"email": body.email, "password": body.password},
        )
    result = await establish(request, response, tokens)
    if register:
        return UserEnvelope(data=result.user, meta=meta(request))
    return SessionEnvelope(data=result, meta=meta(request))


async def google_start(request: Request, response: Response, purpose: str) -> str:
    url, _ = provider.configuration()
    provider.cipher()
    if purpose != "login":
        raise auth.AuthError(409, "ACCOUNT_LINK_UNAVAILABLE")
    await auth.rate_limit(request, "google_start")
    binding, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    async with auth.database(request).sessions() as session, session.begin():
        await auth.csrf_check(session, request)
        if await auth.identity(session, request):
            raise auth.AuthError(409, "GOOGLE_FLOW_INVALID")
        await session.execute(
            text("""
            INSERT INTO app.supabase_flows(binding_hash,session_hash,verifier)
            VALUES (:binding,:session,:verifier)
        """),
            {
                "binding": auth.digest(binding),
                "session": auth.digest(request.cookies.get(auth.SESSION, "")),
                "verifier": verifier,
            },
        )
        await auth.consume_challenge(session, request)
    auth.set_cookie(response, BINDING, binding, 300)
    import os

    callback = os.environ.get("SUPABASE_AUTH_CALLBACK_URL", "")
    if callback not in [
        origin + "/api/v1/auth/google/callback"
        for origin in os.environ.get("AUTH_ORIGINS", "").split(",")
    ]:
        raise auth.AuthError(503, "GOOGLE_UNAVAILABLE")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    return (
        url
        + "/auth/v1/authorize?"
        + urlencode(
            {
                "provider": "google",
                "redirect_to": callback,
                "code_challenge": challenge,
                "code_challenge_method": "s256",
            }
        )
    )


async def google_callback(request: Request) -> RedirectResponse:
    response = RedirectResponse("/login?google=failed", status_code=303)
    try:
        await auth.rate_limit(request, "google_callback")
        binding = request.cookies.get(BINDING, "")
        if len(binding) != 43 or len(request.query_params.getlist("code")) != 1:
            raise auth.AuthError(400, "GOOGLE_FLOW_INVALID")
        async with auth.database(request).sessions() as session, session.begin():
            row = (
                (
                    await session.execute(
                        text("""
                SELECT * FROM app.supabase_flows WHERE binding_hash=:hash
                AND consumed_at IS NULL AND expires_at>now() FOR UPDATE
            """),
                        {"hash": auth.digest(binding)},
                    )
                )
                .mappings()
                .first()
            )
            if row is None or not hmac.compare_digest(
                row["session_hash"], auth.digest(request.cookies.get(auth.SESSION, ""))
            ):
                raise auth.AuthError(400, "GOOGLE_FLOW_INVALID")
            verifier = row["verifier"]
            await session.execute(
                text("""
                UPDATE app.supabase_flows SET consumed_at=now(),verifier=NULL
                WHERE binding_hash=:hash
            """),
                {"hash": auth.digest(binding)},
            )
        code = request.query_params["code"]
        if len(code) > 2048 or request.query_params.get("error"):
            raise auth.AuthError(400, "GOOGLE_FLOW_INVALID")
        tokens = await provider.call(
            "POST", "/token?grant_type=pkce", payload={"auth_code": code, "code_verifier": verifier}
        )
        response = RedirectResponse("/account?google=success", status_code=303)
        await establish(request, response, tokens)
    except auth.AuthError:
        response = RedirectResponse("/login?google=failed", status_code=303)
    auth.clear_cookie(response, BINDING)
    auth.clear_cookie(response, auth.CHALLENGE)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

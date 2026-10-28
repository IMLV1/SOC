"""Offline provider validation. No real Supabase requests or credentials."""

import asyncio
import base64
import json
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.auth import supabase_provider as provider
from app.auth.service import AuthError

URL = "https://abcdefghijklmnopqrst.supabase.co"


@pytest.fixture
def config(monkeypatch, tmp_path):
    key = tmp_path / "tokens.key"
    key.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")
    monkeypatch.setenv("SUPABASE_TOKEN_KEY_FILE", str(key))


def test_refresh_tokens_are_encrypted_and_tampering_fails(config):
    tokens = {"access_token": "access", "refresh_token": "private-refresh"}
    encrypted = provider.seal(tokens)
    assert "private-refresh" not in encrypted
    assert provider.unseal(encrypted) == tokens
    extra = provider.seal({**tokens, "provider_token": "unused-google-token"})
    assert provider.unseal(extra) == tokens
    with pytest.raises(AuthError):
        provider.unseal(encrypted[:-4] + "AAAA")


@pytest.mark.parametrize("url", ["http://localhost", URL + ".evil.test", URL + "/path"])
def test_provider_host_is_fixed(config, monkeypatch, url):
    monkeypatch.setenv("SUPABASE_URL", url)
    with pytest.raises(AuthError):
        provider.configuration()


def test_service_role_key_cannot_be_used(config, monkeypatch):
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_secret_never_browser")
    with pytest.raises(AuthError):
        provider.configuration()


@pytest.mark.parametrize(
    "invalid", ["issuer", "audience", "expired", "subject", "unconfirmed", "anonymous"]
)
def test_remote_verified_identity_still_requires_claims_and_confirmation(
    config, monkeypatch, invalid
):
    subject = str(uuid4())
    claims = {
        "iss": URL + "/auth/v1",
        "aud": "authenticated",
        "sub": subject,
        "session_id": str(uuid4()),
        "exp": time.time() + 3600,
    }
    user = {"id": subject, "email": "learner@example.test", "email_confirmed_at": "now"}
    if invalid == "issuer":
        claims["iss"] = "https://evil.test/auth/v1"
    if invalid == "audience":
        claims["aud"] = "service_role"
    if invalid == "expired":
        claims["exp"] = 1
    if invalid == "subject":
        claims["sub"] = str(uuid4())
    if invalid == "unconfirmed":
        user["email_confirmed_at"] = None
    if invalid == "anonymous":
        user["is_anonymous"] = True

    async def remote(*args, **kwargs):
        return user

    monkeypatch.setattr(provider, "call", remote)
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    with pytest.raises(AuthError):
        asyncio.run(
            provider.verify(
                {
                    "access_token": "header." + encoded + ".signature",
                    "refresh_token": "test-refresh",
                }
            )
        )


def test_unsigned_claims_never_bypass_remote_rejection(config, monkeypatch):
    async def reject(*args, **kwargs):
        raise AuthError(401, "AUTH_PROVIDER_REJECTED")

    monkeypatch.setattr(provider, "call", reject)
    with pytest.raises(AuthError):
        asyncio.run(
            provider.verify(
                {"access_token": "header.claims.signature", "refresh_token": "test-refresh"}
            )
        )


@pytest.mark.parametrize("providers,linked", [(["google"], True), (["email"], False), ([], False)])
def test_google_linked_uses_verified_identities_not_user_metadata(
    config, monkeypatch, providers, linked
):
    subject = str(uuid4())
    claims = {
        "iss": URL + "/auth/v1",
        "aud": "authenticated",
        "sub": subject,
        "session_id": str(uuid4()),
        "exp": int(time.time()) + 3600,
    }
    user = {
        "id": subject,
        "email": "learner@example.test",
        "email_confirmed_at": "now",
        "identities": [{"provider": name} for name in providers],
        "user_metadata": {"providers": ["google"], "google_linked": True},
    }

    async def remote(method, path, **kwargs):
        assert (method, path) == ("GET", "/user")
        return user

    monkeypatch.setattr(provider, "call", remote)
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    identity = asyncio.run(
        provider.verify(
            {"access_token": "header." + encoded + ".signature", "refresh_token": "test-refresh"}
        )
    )
    assert identity.google_linked is linked


@pytest.mark.parametrize(
    "active,linked,expected", [(True, True, True), (True, False, False), (False, True, False)]
)
def test_status_requires_active_soc_session_and_verified_google_identity(
    config, monkeypatch, active, linked, expected
):
    from starlette.requests import Request

    from app.auth import google_routes

    @asynccontextmanager
    async def transaction():
        yield SimpleNamespace(begin=transaction)

    async def identity(*args):
        return {"id": uuid4()} if active else None

    async def settings(*args):
        return {"external": {"google": True}}

    monkeypatch.setenv("AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(provider, "call", settings)
    monkeypatch.setattr(google_routes.auth, "identity", identity)
    monkeypatch.setattr(
        google_routes.auth, "database", lambda _: SimpleNamespace(sessions=transaction)
    )
    request = Request({"type": "http", "path": "/api/v1/auth/google/status", "headers": []})
    request.state.request_id = "offline-status-test"
    request.state.supabase_identity = SimpleNamespace(google_linked=linked)
    result = asyncio.run(google_routes.status(request))
    assert result.data.linked is expected
    assert result.data.available is True

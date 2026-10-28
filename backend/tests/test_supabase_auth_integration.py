"""Real PostgreSQL transactions with fake Auth HTTP; never uses a managed project."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from test_auth import clients as clients
from test_auth import csrf
from test_database import sql

from app.auth import service as auth
from app.auth import supabase_provider as provider

pytestmark = pytest.mark.integration


@pytest.fixture
def supabase(clients, monkeypatch, tmp_path):
    client, url = clients
    key = tmp_path / "tokens.key"
    key.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("AUTH_PROVIDER", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://abcdefghijklmnopqrst.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")
    monkeypatch.setenv("SUPABASE_TOKEN_KEY_FILE", str(key))
    # Test-only provider-session predicate, inside the disposable test database.
    asyncio.run(
        sql(
            url("postgres"),
            """
        CREATE FUNCTION ops.supabase_session_active(uuid,uuid) RETURNS boolean
        LANGUAGE sql AS 'SELECT true'
    """,
        )
    )
    asyncio.run(
        sql(
            url("postgres"),
            """
        GRANT EXECUTE ON FUNCTION ops.supabase_session_active(uuid,uuid) TO api_runtime
    """,
        )
    )
    subject, sid = uuid4(), uuid4()
    tokens = {"access_token": "test-access", "refresh_token": "test-refresh"}
    calls = []

    async def call(method, path, **kwargs):
        calls.append(path)
        return dict(tokens)

    async def verify(value):
        return provider.Identity(
            subject, sid, "cloud@example.test", "Cloud", int(time.time() + 3600)
        )

    monkeypatch.setattr(provider, "call", call)
    monkeypatch.setattr(provider, "verify", verify)
    return client, url, calls


def login(client):
    return client.post(
        "/api/v1/auth/login",
        headers=csrf(client),
        json={"email": "cloud@example.test", "password": "Test123!9"},
    )


def test_supabase_login_creates_only_analyst_and_server_quota(supabase):
    client, url, _ = supabase
    result = login(client)
    assert result.status_code == 200, result.text
    assert result.json()["data"]["user"]["role"] == "analyst"
    assert "test-access" not in result.text and "test-refresh" not in result.text
    assert client.get("/api/v1/auth/session").status_code == 200
    limits = client.get("/api/v1/me/quota").json()["data"]
    assert (limits["daily_runs"], limits["daily_ai_requests"]) == (10, 20)
    count = asyncio.run(sql(url("migration_owner"), "SELECT count(*) FROM app.users"))
    assert count[0][0] == 1
    assert login(client).status_code == 200
    assert asyncio.run(sql(url("migration_owner"), "SELECT count(*) FROM app.users"))[0][0] == 1
    encrypted = asyncio.run(
        sql(url("migration_owner"), "SELECT encrypted_tokens FROM app.supabase_sessions")
    )
    assert all("test-refresh" not in row[0] for row in encrypted)


def test_confirmation_does_not_create_fake_account_or_cookie(supabase, monkeypatch):
    client, url, _ = supabase

    async def pending(*args, **kwargs):
        return {"user": {"id": str(uuid4())}}

    monkeypatch.setattr(provider, "call", pending)
    result = client.post(
        "/api/v1/auth/register",
        headers=csrf(client),
        json={"email": "cloud@example.test", "display_name": "Cloud", "password": "Test123!9"},
    )
    assert result.status_code == 202
    assert result.json()["data"] == {"status": "email_confirmation_required"}
    assert auth.SESSION not in client.cookies
    assert asyncio.run(sql(url("migration_owner"), "SELECT count(*) FROM app.users"))[0][0] == 0


def test_provider_revocation_disables_domain_session(supabase):
    client, url, _ = supabase
    assert login(client).status_code == 200
    asyncio.run(
        sql(
            url("postgres"),
            """
        CREATE OR REPLACE FUNCTION ops.supabase_session_active(uuid,uuid) RETURNS boolean
        LANGUAGE sql AS 'SELECT false'
    """,
        )
    )
    assert client.get("/api/v1/auth/session").status_code == 401


def test_refresh_is_once_and_logout_revokes_even_if_provider_is_down(supabase, monkeypatch):
    client, url, calls = supabase
    assert login(client).status_code == 200
    cookie = client.cookies[auth.SESSION]
    asyncio.run(
        sql(
            url("migration_owner"),
            """
        UPDATE app.supabase_sessions SET access_expires_at=now()-interval '1 minute'
    """,
        )
    )
    assert client.get("/api/v1/auth/session").status_code == 200
    assert client.get("/api/v1/auth/session").status_code == 200
    assert calls.count("/token?grant_type=refresh_token") == 1

    async def unavailable(*args, **kwargs):
        raise auth.AuthError(503, "AUTH_PROVIDER_UNAVAILABLE")

    headers = csrf(client)
    monkeypatch.setattr(provider, "call", unavailable)
    assert client.post("/api/v1/auth/logout", headers=headers, json={}).status_code == 204
    client.cookies.set(auth.SESSION, cookie)
    assert client.get("/api/v1/auth/session").status_code == 401


def test_old_email_is_not_automatically_merged(supabase):
    client, url, _ = supabase
    asyncio.run(
        sql(
            url("migration_owner"),
            """
        INSERT INTO app.users(id,normalized_email,display_name,password_hash,role,status)
        VALUES (gen_random_uuid(),'cloud@example.test','Legacy',NULL,'instructor','active')
    """,
        )
    )
    response = login(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACCOUNT_LINK_REQUIRED"
    assert auth.SESSION not in client.cookies


def test_refresh_lease_and_logout_fence_inflight_provider_response(supabase, monkeypatch):
    client, url, calls = supabase
    result = login(client)
    csrf_token = result.json()["data"]["csrf_token"]
    cookie = client.cookies[auth.SESSION]
    asyncio.run(
        sql(
            url("migration_owner"),
            """
        UPDATE app.supabase_sessions SET access_expires_at=now()-interval '1 minute'
    """,
        )
    )
    entered, release = threading.Event(), threading.Event()
    original = provider.call

    async def blocked(method, path, **kwargs):
        if path == "/token?grant_type=refresh_token":
            entered.set()
            assert await asyncio.to_thread(release.wait, 5)
        return await original(method, path, **kwargs)

    monkeypatch.setattr(provider, "call", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.get, "/api/v1/auth/session")
        try:
            assert entered.wait(5)
            # A second request must not send the same rotating refresh token.
            assert client.get("/api/v1/auth/session").status_code == 503
            assert (
                client.post(
                    "/api/v1/auth/logout", json={}, headers={"X-CSRF-Token": csrf_token}
                ).status_code
                == 204
            )
        finally:
            release.set()
        assert future.result(timeout=5).status_code == 401
    client.cookies.set(auth.SESSION, cookie)
    assert client.get("/api/v1/auth/session").status_code == 401
    assert calls.count("/token?grant_type=refresh_token") == 1
    encrypted = asyncio.run(
        sql(url("migration_owner"), "SELECT encrypted_tokens FROM app.supabase_sessions")
    )
    assert encrypted == [("",)]


def test_invalid_origin_does_not_dispatch_password_to_provider(supabase):
    client, _, calls = supabase
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.test"},
        json={"email": "cloud@example.test", "password": "Test123!9"},
    )
    assert response.status_code == 403
    assert calls == []


def test_google_flow_is_browser_bound_and_consumed_once(supabase, monkeypatch):
    client, _, calls = supabase
    monkeypatch.setenv(
        "SUPABASE_AUTH_CALLBACK_URL", "http://testserver/api/v1/auth/google/callback"
    )
    start = client.post(
        "/api/v1/auth/google/start", headers=csrf(client), json={"purpose": "login"}
    )
    assert start.status_code == 200
    assert "code_challenge=" in start.json()["data"]["authorization_url"]
    assert "code_challenge_method=s256" in start.json()["data"]["authorization_url"]
    response = client.get("/api/v1/auth/google/callback?code=offline-code", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/account?google=success"
    assert client.get("/api/v1/auth/session").status_code == 200
    replay = client.get("/api/v1/auth/google/callback?code=offline-code", follow_redirects=False)
    assert replay.headers["location"] == "/login?google=failed"
    assert calls.count("/token?grant_type=pkce") == 1

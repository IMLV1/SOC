import asyncio
import secrets
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import pytest
from test_auth import PASSWORD, csrf, login, register
from test_auth import clients as clients
from test_database import sql

from app.auth import google_oidc as oidc
from app.auth import service as auth
from app.auth.google_routes import BINDING

pytestmark = pytest.mark.integration


@pytest.fixture
def google(clients, monkeypatch, tmp_path):
    client, url = clients
    secret = tmp_path / "secret.txt"
    secret.write_text("test-only-secret", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_OAUTH_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", str(secret))
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:13014/api/v1/auth/google/callback"
    )
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver,http://127.0.0.1:13014")
    identity = oidc.GoogleIdentity(
        oidc.ISSUER, "subject-one", "google@example.test", "Google Analyst", False
    )
    calls = []

    async def exchange(config, code, verifier, nonce_hash):
        calls.append(code)
        assert len(verifier) == 43 and len(nonce_hash) == 64
        return identity

    monkeypatch.setattr(oidc, "exchange", exchange)
    return client, url, monkeypatch, calls


def start(client, **body):
    result = client.post("/api/v1/auth/google/start", json=body, headers=csrf(client))
    assert result.status_code == 200, result.text
    query = parse_qs(urlsplit(result.json()["data"]["authorization_url"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["openid email profile"]
    assert "test-only-secret" not in result.text
    return query["state"][0]


def callback(client, state, **kwargs):
    return client.get(
        "/api/v1/auth/google/callback",
        params={"state": state, "code": "test-code", **kwargs},
        follow_redirects=False,
    )


def test_new_google_account_quota_session_and_subject_stability(google):
    client, url, patch, calls = google
    assert client.get("/api/v1/auth/google/status").json()["data"] == {
        "available": True,
        "linked": False,
        "link_available": True,
        "provider_origin": None,
    }
    state = start(client)
    binding = client.cookies[BINDING]
    result = callback(client, state)
    assert result.status_code == 303 and result.headers["location"] == "/account?google=success"
    assert result.headers["referrer-policy"] == "no-referrer"
    user = client.get("/api/v1/me").json()["data"]
    assert user["role"] == "analyst" and user["email"] == "google@example.test"
    quota = client.get("/api/v1/me/quota").json()["data"]
    assert quota["daily_runs"] == 10 and quota["daily_ai_requests"] == 20
    assert client.get("/api/v1/auth/google/status").json()["data"]["linked"]
    rows = asyncio.run(
        sql(
            url("migration_owner"),
            "SELECT state_hash,binding_hash,nonce_hash,verifier,consumed_at FROM app.google_flows",
        )
    )
    assert rows[0][0] != state and rows[0][1] != binding and rows[0][3] is None and rows[0][4]
    assert len(calls) == 1
    client.cookies.clear()
    client.cookies.set(BINDING, binding)
    assert callback(client, state).headers["location"] == "/login?google=failed"
    assert len(calls) == 1
    client.cookies.clear()

    # Email changes never transfer account ownership: stable Google subject resolves original ID.
    async def changed(*args):
        return oidc.GoogleIdentity(
            oidc.ISSUER, "subject-one", "changed@example.test", "Changed", False
        )

    patch.setattr(oidc, "exchange", changed)
    assert callback(client, start(client)).headers["location"] == "/account?google=success"
    assert client.get("/api/v1/me").json()["data"]["id"] == user["id"]
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=csrf(client),
            json={"email": user["email"], "password": PASSWORD},
        ).status_code
        == 401
    )


def test_existing_email_requires_password_link_and_preserves_account(google):
    client, url, patch, calls = google
    original = register(client, "google@example.test")
    client.cookies.clear()
    assert callback(client, start(client)).headers["location"] == "/login?google=link_required"
    assert client.get("/api/v1/me").status_code == 401
    login(client, "google@example.test")
    old_session = client.cookies[auth.SESSION]
    failed = client.post(
        "/api/v1/auth/google/start",
        headers=csrf(client),
        json={"purpose": "link", "password": "wrong-password-123"},
    )
    assert failed.status_code == 401
    result = callback(client, start(client, purpose="link", password=PASSWORD))
    assert result.headers["location"] == "/account?google=success"
    assert client.cookies[auth.SESSION] != old_session
    assert client.get("/api/v1/me").json()["data"] == original
    rows = asyncio.run(
        sql(
            url("migration_owner"),
            "SELECT (SELECT count(*) FROM app.users),"
            "(SELECT count(*) FROM app.google_identities),"
            "(SELECT count(*) FROM app.audit_logs WHERE action='auth.google.link')",
        )
    )
    assert tuple(rows[0]) == (1, 1, 1)
    client.cookies.clear()
    assert callback(client, start(client)).headers["location"] == "/account?google=success"
    assert client.get("/api/v1/me").json()["data"]["id"] == original["id"]


@pytest.mark.parametrize(
    "failure", ["wrong_binding", "expired", "session_changed", "denied", "provider_failure"]
)
def test_failed_flow_cannot_authenticate_or_replay(google, failure):
    client, url, patch, calls = google
    state = start(client)
    binding = client.cookies[BINDING]
    if failure == "wrong_binding":
        client.cookies.set(BINDING, secrets.token_urlsafe(32), domain="testserver.local", path="/")
    if failure == "session_changed":
        client.cookies.set(auth.SESSION, secrets.token_urlsafe(32))
    if failure == "expired":
        asyncio.run(
            sql(
                url("migration_owner"),
                "UPDATE app.google_flows SET created_at=now()-interval '10 minutes',"
                "expires_at=now()-interval '1 minute'",
            )
        )
    if failure == "provider_failure":

        async def unavailable(*args):
            raise oidc.GoogleOIDCError("GOOGLE_LOGIN_UNAVAILABLE")

        patch.setattr(oidc, "exchange", unavailable)
    response = callback(
        client, state, **({"error": "access_denied"} if failure == "denied" else {})
    )
    assert response.headers["location"] == "/login?google=failed"
    assert client.get("/api/v1/me").status_code == 401
    assert not asyncio.run(sql(url("migration_owner"), "SELECT id FROM app.users"))
    assert not calls
    if failure in {"denied", "provider_failure"}:
        client.cookies.clear()
        client.cookies.set(BINDING, binding)
        assert callback(client, state).headers["location"] == "/login?google=failed"


def test_link_rechecks_session_after_network_and_disabled_users(google):
    client, url, patch, calls = google
    register(client, "google@example.test")
    login(client, "google@example.test")
    state = start(client, purpose="link", password=PASSWORD)

    async def revoked(*args):
        await sql(url("migration_owner"), "UPDATE app.auth_sessions SET revoked_at=now()")
        return oidc.GoogleIdentity(
            oidc.ISSUER, "subject-one", "google@example.test", "Google", False
        )

    patch.setattr(oidc, "exchange", revoked)
    assert callback(client, state).headers["location"] == "/login?google=failed"
    assert not asyncio.run(sql(url("migration_owner"), "SELECT user_id FROM app.google_identities"))
    client.cookies.clear()

    async def success(*args):
        return oidc.GoogleIdentity(
            oidc.ISSUER, "subject-one", "google@example.test", "Google", False
        )

    patch.setattr(oidc, "exchange", success)
    login(client, "google@example.test")
    assert (
        callback(client, start(client, purpose="link", password=PASSWORD)).headers["location"]
        == "/account?google=success"
    )
    client.cookies.clear()
    asyncio.run(sql(url("migration_owner"), "UPDATE app.users SET status='disabled'"))
    assert callback(client, start(client)).headers["location"] == "/login?google=failed"
    assert client.get("/api/v1/me").status_code == 401


def test_start_csrf_origin_disabled_and_link_email_mismatch(google):
    client, url, patch, calls = google
    assert client.post("/api/v1/auth/google/start", json={}).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/google/start",
            json={},
            headers={**csrf(client), "Origin": "https://evil.test"},
        ).status_code
        == 403
    )
    register(client, "other@example.test")
    login(client, "other@example.test")
    assert (
        callback(client, start(client, purpose="link", password=PASSWORD)).headers["location"]
        == "/login?google=failed"
    )
    assert not asyncio.run(sql(url("migration_owner"), "SELECT user_id FROM app.google_identities"))
    patch.setenv("GOOGLE_OAUTH_ENABLED", "false")
    assert not client.get("/api/v1/auth/google/status").json()["data"]["available"]
    assert (
        client.post("/api/v1/auth/google/start", headers=csrf(client), json={}).status_code == 503
    )


def test_concurrent_same_subject_creates_one_identity_and_quota(google):
    client, url, patch, calls = google
    states = []
    for _ in range(2):
        client.cookies.clear()
        state = start(client)
        states.append((state, client.cookies[BINDING]))
    client.cookies.clear()

    def send(item):
        state, binding = item
        response = client.get(
            "/api/v1/auth/google/callback",
            params={"state": state, "code": "test-code"},
            headers={"Cookie": f"{BINDING}={binding}"},
            follow_redirects=False,
        )
        return response.headers["location"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(send, states)) == ["/account?google=success"] * 2
    rows = asyncio.run(
        sql(
            url("migration_owner"),
            "SELECT (SELECT count(*) FROM app.users),"
            "(SELECT count(*) FROM app.google_identities),"
            "(SELECT count(*) FROM app.user_quotas)",
        )
    )
    assert tuple(rows[0]) == (1, 1, 1)


def test_concurrent_callback_consumes_flow_once(google):
    client, url, patch, calls = google
    state = start(client)
    binding = client.cookies[BINDING]
    client.cookies.clear()

    def send(_):
        response = client.get(
            "/api/v1/auth/google/callback",
            params={"state": state, "code": "test-code"},
            headers={"Cookie": f"{BINDING}={binding}"},
            follow_redirects=False,
        )
        return response.headers["location"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(send, range(2))) == [
            "/account?google=success",
            "/login?google=failed",
        ]
    assert calls == ["test-code"]
    rows = asyncio.run(sql(url("migration_owner"), "SELECT count(*) FROM app.auth_sessions"))
    assert rows[0][0] == 1


def test_subject_cannot_move_to_another_user_and_runtime_roles_are_restricted(google):
    client, url, patch, calls = google
    assert callback(client, start(client)).headers["location"] == "/account?google=success"
    original = client.get("/api/v1/me").json()["data"]["id"]
    client.cookies.clear()
    register(client, "second@example.test")
    login(client, "second@example.test")

    async def same_subject(*args):
        return oidc.GoogleIdentity(
            oidc.ISSUER, "subject-one", "second@example.test", "Second", False
        )

    patch.setattr(oidc, "exchange", same_subject)
    assert (
        callback(client, start(client, purpose="link", password=PASSWORD)).headers["location"]
        == "/login?google=failed"
    )
    rows = asyncio.run(sql(url("migration_owner"), "SELECT user_id FROM app.google_identities"))
    assert str(rows[0][0]) == original
    grants = asyncio.run(
        sql(
            url("migration_owner"),
            """SELECT
      has_table_privilege('worker_runtime','app.google_flows','SELECT'),
      has_table_privilege('evaluator_runtime','app.google_identities','SELECT'),
      has_table_privilege('api_runtime','app.google_identities','UPDATE'),
      has_table_privilege('api_runtime','app.google_identities','DELETE')""",
        )
    )
    assert tuple(grants[0]) == (False, False, False, False)

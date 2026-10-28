import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_database import sql

from app.auth import service as auth
from app.db.provision import assign, provision_user
from app.db.session import Database
from app.main import app

pytestmark = pytest.mark.integration
PASSWORD = "Test123!9"
PROVISION_PASSWORD = "Only-a-test-password-123"


@pytest.fixture
def clients(migrated, monkeypatch):
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    # Lifespan owns the engine on TestClient's loop, never reuse an engine across test loops.
    monkeypatch.setattr("app.main.database_url", lambda role: migrated(role))
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        yield client, migrated


def csrf(client):
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["data"]["csrf_token"]}


def register(client, email="person@example.test"):
    response = client.post(
        "/api/v1/auth/register",
        headers=csrf(client),
        json={"email": email, "display_name": " Person ", "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def login(client, email="person@example.test"):
    response = client.post(
        "/api/v1/auth/login", headers=csrf(client), json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.parametrize("length,expected_status", [(5, 422), (6, 201), (12, 201), (13, 422)])
def test_registration_password_boundaries(clients, length, expected_status):
    client, _ = clients
    response = client.post(
        "/api/v1/auth/register",
        headers=csrf(client),
        json={
            "email": "boundary@example.test",
            "display_name": "Boundary",
            "password": "x" * length,
        },
    )
    assert response.status_code == expected_status


def test_provisioned_long_password_still_logs_in(clients):
    client, url = clients

    async def create():
        db = Database(url("migration_owner"))
        try:
            await provision_user(
                db,
                email="existing@example.test",
                display_name="Existing",
                password=PROVISION_PASSWORD,
                role="analyst",
                daily_runs=10,
                daily_ai_requests=20,
            )
        finally:
            await db.close()

    asyncio.run(create())
    response = client.post(
        "/api/v1/auth/login",
        headers=csrf(client),
        json={"email": "existing@example.test", "password": PROVISION_PASSWORD},
    )
    assert response.status_code == 200


def test_register_session_rotation_logout_and_quota(clients):
    client, url = clients
    user = register(client, "PERSON@Example.Test")
    assert user["role"] == "analyst" and user["email"] == "person@example.test"
    registered_session = client.get("/api/v1/auth/session")
    assert registered_session.status_code == 200
    assert registered_session.json()["data"]["user"] == user
    registration_cookie = client.cookies[auth.SESSION]
    assert auth.CHALLENGE not in client.cookies
    first = login(client)
    cookie = client.cookies[auth.SESSION]
    assert cookie != registration_cookie
    assert client.get("/api/v1/me").json()["data"] == user
    assert client.get("/api/v1/auth/session").json()["data"]["csrf_token"] == first["csrf_token"]
    limits = client.get("/api/v1/me/quota").json()["data"]
    assert (limits["daily_runs"], limits["daily_ai_requests"], limits["run_count"]) == (10, 20, 0)
    second = login(client)
    assert client.cookies[auth.SESSION] != cookie
    assert second["csrf_token"] != first["csrf_token"]
    assert (
        client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": first["csrf_token"]}, json={}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": second["csrf_token"]}, json={}
        ).status_code
        == 204
    )
    client.cookies.set(auth.SESSION, cookie)
    assert client.get("/api/v1/me").status_code == 401
    assert client.post("/api/v1/auth/logout", json={}).status_code == 204
    rows = asyncio.run(
        sql(url("migration_owner"), "SELECT token_hash,csrf_hash FROM app.auth_sessions")
    )
    assert all(len(r[0]) == 64 and r[0] != cookie and r[1] != first["csrf_token"] for r in rows)


def test_registration_rotates_existing_browser_session(clients):
    client, _ = clients
    register(client, "first@example.test")
    original_cookie = client.cookies[auth.SESSION]
    second = register(client, "second@example.test")
    assert client.cookies[auth.SESSION] != original_cookie
    assert client.get("/api/v1/me").json()["data"] == second
    client.cookies.set(auth.SESSION, original_cookie)
    assert client.get("/api/v1/me").status_code == 401


def test_registration_session_failure_rolls_back_account_and_quota(clients, monkeypatch):
    from app.auth import routes

    client, url = clients
    original = routes.create_session

    async def fail_after_session_insert(*args):
        await original(*args)
        raise RuntimeError("simulated session failure")

    monkeypatch.setattr(routes, "create_session", fail_after_session_insert)
    with pytest.raises(RuntimeError, match="simulated session failure"):
        register(client)
    assert auth.SESSION not in client.cookies
    rows = asyncio.run(
        sql(
            url("migration_owner"),
            """SELECT (SELECT count(*) FROM app.users),
            (SELECT count(*) FROM app.user_quotas),
            (SELECT count(*) FROM app.auth_sessions),
            (SELECT count(*) FROM app.audit_logs)""",
        )
    )
    assert tuple(rows[0]) == (0, 0, 0, 0)


def test_origin_csrf_unknown_fields_and_generic_failures(clients):
    client, _ = clients
    malformed = client.post(
        "/api/v1/auth/login",
        content='{"password":"do-not-reflect"',
        headers={"Content-Type": "application/json"},
    )
    assert malformed.status_code == 400 and "do-not-reflect" not in malformed.text
    body = {"email": "person@example.test", "password": PASSWORD, "display_name": "Person"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 403
    token = csrf(client)
    assert (
        client.post(
            "/api/v1/auth/register", headers={**token, "Origin": "https://evil.test"}, json=body
        ).status_code
        == 403
    )
    for field in ("role", "status", "daily_runs", "user_id"):
        assert (
            client.post(
                "/api/v1/auth/register", headers=token, json={**body, field: "instructor"}
            ).status_code
            == 422
        )
    register(client)
    failures = []
    for email in ("person@example.test", "absent@example.test"):
        response = client.post(
            "/api/v1/auth/login",
            headers=csrf(client),
            json={"email": email, "password": "incorrect-password-123"},
        )
        assert response.status_code == 401
        failures.append(response.json()["error"])
    assert failures[0] == failures[1]
    response = client.post("/api/v1/auth/register", headers=csrf(client), json=body)
    assert response.status_code == 409
    assert "email" not in response.json()["error"]["message"]


@pytest.mark.parametrize("change", ["expired", "revoked", "disabled"])
def test_expired_revoked_disabled_cannot_read(clients, change):
    client, url = clients
    register(client)
    login(client)
    statement = {
        "expired": "UPDATE app.auth_sessions SET created_at=now()-interval '2 days', "
        "expires_at=now()-interval '1 day'",
        "revoked": "UPDATE app.auth_sessions SET revoked_at=now()",
        "disabled": "UPDATE app.users SET status='disabled'",
    }[change]
    asyncio.run(sql(url("migration_owner"), statement))
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/auth/session").status_code == 401
    assert client.get("/api/v1/me/quota").status_code == 401


def test_identity_isolation_and_assignment_policy(clients):
    client, url = clients
    a = register(client, "a@example.test")
    register(client, "b@example.test")
    login(client, "a@example.test")
    assert client.get("/api/v1/me?user_id=" + a["id"]).json()["data"]["email"] == "a@example.test"
    login(client, "b@example.test")
    assert client.get("/api/v1/me?user_id=" + a["id"]).json()["data"]["email"] == "b@example.test"

    async def check():
        db = Database(url("migration_owner"))
        try:
            teacher = await provision_user(
                db,
                email="teacher@example.test",
                display_name="Teacher",
                password=PROVISION_PASSWORD,
                role="instructor",
                daily_runs=10,
                daily_ai_requests=20,
            )
            from uuid import UUID

            owner = UUID(a["id"])
            await assign(db, teacher, owner)
            runtime = Database(url("api_runtime"))
            async with runtime.sessions() as session:
                await auth.authorize_assignment(
                    session, {"id": teacher, "role": "instructor"}, owner
                )
                with pytest.raises(auth.AuthError) as error:
                    await auth.authorize_assignment(
                        session, {"id": teacher, "role": "instructor"}, uuid4()
                    )
                assert error.value.status == 404
                with pytest.raises(auth.AuthError) as error:
                    await auth.authorize_assignment(
                        session, {"id": owner, "role": "analyst"}, owner
                    )
                assert error.value.status == 403
                with pytest.raises(auth.AuthError) as error:
                    await auth.authorize_owner({"id": teacher}, owner)
                assert error.value.status == 404
            await runtime.close()
        finally:
            await db.close()

    asyncio.run(check())


def test_secure_cookie_and_challenge_replay(clients, monkeypatch):
    client, url = clients
    challenge = csrf(client)
    original = client.cookies[auth.CHALLENGE]
    register(client)
    client.cookies.clear()
    client.cookies.set(auth.CHALLENGE, original)
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=challenge,
            json={"email": "person@example.test", "password": PASSWORD},
        ).status_code
        == 403
    )
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    client.cookies.clear()
    response = client.get("/api/v1/auth/csrf")
    cookie = response.headers["set-cookie"]
    assert (
        "Secure" in cookie
        and "HttpOnly" in cookie
        and "SameSite=lax" in cookie
        and "Path=/" in cookie
    )
    assert response.headers["cache-control"] == "no-store"
    asyncio.run(
        sql(
            url("migration_owner"),
            "UPDATE app.auth_challenges SET created_at=:a,expires_at=:b",
            {
                "a": datetime.now(UTC) - timedelta(days=2),
                "b": datetime.now(UTC) - timedelta(days=1),
            },
        )
    )
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    token = response.json()["data"]["csrf_token"]
    raw = client.cookies[auth.CHALLENGE]
    response = client.post(
        "/api/v1/auth/login",
        headers={"X-CSRF-Token": token, "Cookie": f"{auth.CHALLENGE}={raw}"},
        json={"email": "person@example.test", "password": PASSWORD},
    )
    assert response.status_code == 403


def test_login_rate_limit_is_shared_and_no_demo_mutations(clients, monkeypatch):
    # Keep every request in the same limiter bucket even if the test crosses a minute.
    fixed_now = datetime.now(UTC)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is UTC else fixed_now.astimezone(tz)

    monkeypatch.setattr(auth, "datetime", FixedDatetime)
    client, _ = clients
    token = csrf(client)
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/login",
                headers=token,
                json={"email": "none@example.test", "password": PASSWORD},
            ).status_code
            == 401
        )
    response = client.post(
        "/api/v1/auth/login",
        headers=token,
        json={"email": "none@example.test", "password": PASSWORD},
    )
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    # Public demo now depends on published DB content; no hard-coded fallback.
    assert client.get("/api/v1/demo/events").json()["data"] == []
    assert client.post("/api/v1/demo/events", json={}).status_code == 405
    assert client.get("/api/v1/me").status_code == 401


def test_concurrent_registration_is_atomic(clients):
    client, url = clients
    headers = []
    for _ in range(2):
        client.cookies.clear()
        token = csrf(client)
        headers.append({**token, "Cookie": f"{auth.CHALLENGE}={client.cookies[auth.CHALLENGE]}"})

    def send(header):
        return client.post(
            "/api/v1/auth/register",
            headers=header,
            json={"email": "race@example.test", "display_name": "Race", "password": PASSWORD},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(send, headers)) == [201, 409]
    rows = asyncio.run(
        sql(
            url("migration_owner"),
            """SELECT
        (SELECT count(*) FROM app.users), (SELECT count(*) FROM app.user_quotas),
        (SELECT count(*) FROM app.audit_logs WHERE action='auth.register')""",
        )
    )
    assert tuple(rows[0]) == (1, 1, 1)

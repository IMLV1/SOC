import ssl

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL

from app.db.config import runtime_password, tls_connect_args
from app.main import app


def test_external_render_tls_checks_hostname_and_certificate():
    context = tls_connect_args(URL.create("postgresql+asyncpg", host="preview.render.com"))["ssl"]
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert tls_connect_args(URL.create("postgresql+asyncpg", host="localhost")) == {}


def test_runtime_secret_requires_one_explicit_strong_source(monkeypatch, tmp_path):
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("DB_PASSWORD", "x" * 48)
    assert runtime_password() == "x" * 48
    secret = tmp_path / "runtime.txt"
    secret.write_text("y" * 48)
    monkeypatch.setenv("DB_PASSWORD_FILE", str(secret))
    with pytest.raises(ValueError, match="only one"):
        runtime_password()
    monkeypatch.delenv("DB_PASSWORD")
    assert runtime_password() == "y" * 48
    monkeypatch.delenv("DB_PASSWORD_FILE")
    with pytest.raises(ValueError, match="required"):
        runtime_password()


def test_auth_preview_refuses_background_work_without_database(monkeypatch):
    monkeypatch.setenv("SOC_PREVIEW_MODE", "auth_only")
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)
    with TestClient(app) as client:
        response = client.post("/api/v1/runs", json={})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "PREVIEW_UNAVAILABLE"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-request-id"]
        assert client.get("/health/live").status_code == 200
        # Auth still enforces its origin guard instead of being hidden by preview mode.
        assert client.post("/api/v1/auth/login", json={}).status_code == 403

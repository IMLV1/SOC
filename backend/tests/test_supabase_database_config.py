"""Offline Supabase URL/TLS preparation; no database connections are opened."""

import ssl
from unittest.mock import Mock

import pytest
from sqlalchemy import URL

from app.db.config import ROLES, database_url, tls_connect_args

PROJECT = "abcdefghijklmnopqrst"


@pytest.fixture(autouse=True)
def config(monkeypatch):
    for key in (
        "DB_PROVIDER",
        "DB_PROJECT_REF",
        "DB_CONNECTION_MODE",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_PASSWORD",
        "DB_PASSWORD_FILE",
        "DB_SSL_CA_FILE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DB_PASSWORD", "test-only-secret-" + "x" * 32)


def supabase(monkeypatch, mode="direct"):
    monkeypatch.setenv("DB_PROVIDER", "supabase")
    monkeypatch.setenv("DB_PROJECT_REF", PROJECT)
    monkeypatch.setenv("DB_CONNECTION_MODE", mode)
    monkeypatch.setenv(
        "DB_HOST",
        f"db.{PROJECT}.supabase.co"
        if mode == "direct"
        else "aws-0-ap-southeast-1.pooler.supabase.com",
    )


def test_existing_local_database_defaults_are_unchanged():
    url = database_url("api_runtime")
    assert (url.host, url.port, url.database, url.username) == (
        "127.0.0.1",
        5432,
        "soc",
        "api_runtime",
    )
    assert tls_connect_args(url) == {}


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("mode", ["direct", "session"])
def test_cloud_connections_preserve_each_dedicated_role(monkeypatch, role, mode):
    supabase(monkeypatch, mode)
    url = database_url(role)
    assert url.username == (role if mode == "direct" else f"{role}.{PROJECT}")
    assert url.database == "postgres"
    assert url.port == 5432
    assert "test-only-secret" not in str(url)
    context = tls_connect_args(url)["ssl"]
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize(
    "key,value",
    [
        ("DB_PROJECT_REF", ""),
        ("DB_PROJECT_REF", "../not-a-project"),
        ("DB_HOST", "localhost"),
        ("DB_HOST", "db.otherproject.supabase.co"),
        ("DB_PORT", "6543"),
        ("DB_CONNECTION_MODE", "transaction"),
        ("DB_PROVIDER", "unknown"),
    ],
)
def test_unsafe_or_mismatched_configuration_is_rejected(monkeypatch, key, value):
    supabase(monkeypatch)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        database_url("api_runtime")


def test_session_pooler_does_not_accept_lookalike_host_or_arbitrary_role(monkeypatch):
    supabase(monkeypatch, "session")
    monkeypatch.setenv("DB_HOST", "pooler.supabase.com.attacker.test")
    with pytest.raises(ValueError, match="pooler host"):
        database_url("api_runtime")
    with pytest.raises(ValueError, match="Unsupported database role"):
        database_url("service_role")


def test_custom_ca_is_added_without_disabling_verification(monkeypatch):
    context = Mock(spec=ssl.SSLContext)
    monkeypatch.setattr("app.db.config.ssl.create_default_context", lambda: context)
    monkeypatch.setenv("DB_SSL_CA_FILE", "/runtime/provider-ca.crt")
    url = URL.create("postgresql+asyncpg", host=f"db.{PROJECT}.supabase.co")
    assert tls_connect_args(url)["ssl"] is context
    context.load_verify_locations.assert_called_once_with(cafile="/runtime/provider-ca.crt")


def test_secret_special_characters_are_not_lost_by_url_construction(monkeypatch):
    supabase(monkeypatch)
    secret = "long-test-only-password:@/?#&%" * 2
    monkeypatch.setenv("DB_PASSWORD", secret)
    url = database_url("worker_runtime")
    assert url.password == secret
    assert secret not in str(url)

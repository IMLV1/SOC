"""Offline Google OIDC adapter tests; no Google account, real key or network."""

import asyncio
import hashlib
import json
import time
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt

from app.auth import google_oidc as oidc

CLIENT = "test-client.apps.googleusercontent.com"
NONCE = "n" * 43
VERIFIER = "v" * 43
NONCE_HASH = hashlib.sha256(NONCE.encode()).hexdigest()


@pytest.fixture
def config(tmp_path):
    secret = tmp_path / "oauth-secret.txt"
    secret.write_text("synthetic-test-secret-only", encoding="utf-8")
    return oidc.GoogleConfig(CLIENT, "http://127.0.0.1:13014" + oidc.CALLBACK_PATH, secret)


def test_config_disabled_and_rejects_untrusted_callback_or_missing_secret(config):
    assert oidc.config_from_env({}) is None
    env = {
        "GOOGLE_OAUTH_ENABLED": "true",
        "GOOGLE_OAUTH_CLIENT_ID": CLIENT,
        "GOOGLE_OAUTH_REDIRECT_URI": config.redirect_uri,
        "GOOGLE_OAUTH_CLIENT_SECRET_FILE": str(config.secret_file),
        "AUTH_ORIGINS": "http://127.0.0.1:13014",
    }
    assert oidc.config_from_env(env) == config
    for value in (
        "https://attacker.test" + oidc.CALLBACK_PATH,
        config.redirect_uri + "?next=https://attacker.test",
        config.redirect_uri + "#fragment",
        "http://example.test" + oidc.CALLBACK_PATH,
        "http://user:password@127.0.0.1:13014" + oidc.CALLBACK_PATH,
    ):
        with pytest.raises(oidc.GoogleOIDCError, match="NOT_CONFIGURED"):
            oidc.config_from_env({**env, "GOOGLE_OAUTH_REDIRECT_URI": value})
    with pytest.raises(oidc.GoogleOIDCError, match="NOT_CONFIGURED"):
        oidc.config_from_env({**env, "GOOGLE_OAUTH_CLIENT_SECRET_FILE": "does-not-exist"})
    assert "synthetic-test-secret" not in repr(config)


def test_authorization_contains_state_nonce_pkce_and_no_secret(config):
    url = oidc.authorization_url(config, "s" * 43, NONCE, VERIFIER)
    assert urlsplit(url).hostname == "accounts.google.com"
    query = parse_qs(urlsplit(url).query)
    assert query["scope"] == ["openid email profile"]
    assert query["state"] == ["s" * 43] and query["nonce"] == [NONCE]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0] != VERIFIER
    assert "client_secret" not in query and "synthetic-test-secret" not in url
    with pytest.raises(oidc.GoogleOIDCError, match="FLOW_INVALID"):
        oidc.authorization_url(config, "short", NONCE, VERIFIER)


def signed_fixture(payload):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    signer = crypt.RSASigner.from_string(private, key_id="test-key")
    token = jwt.encode(signer, payload).decode()
    return token, public


def claims():
    now = int(time.time())
    return {
        "iss": oidc.ISSUER,
        "aud": CLIENT,
        "sub": "google-subject-123",
        "iat": now,
        "exp": now + 300,
        "nonce": NONCE,
        "email": "Person@gmail.com",
        "email_verified": True,
        "name": " Person ",
    }


def configure_transport(monkeypatch, token, public):
    class TokenResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return json.dumps({"id_token": token, "access_token": "must-not-persist"}).encode()

    def open_request(request, timeout):
        assert request.full_url == oidc.TOKEN_ENDPOINT and timeout == 8
        assert b"code_verifier=" in request.data
        return TokenResponse()

    class CertRequest:
        def __call__(self, url, method="GET", timeout=0, **kwargs):
            assert url.startswith("https://www.googleapis.com/") and timeout == 5
            return type(
                "Response", (), {"status": 200, "data": json.dumps({"test-key": public}).encode()}
            )()

    monkeypatch.setattr(oidc.urllib.request, "urlopen", open_request)
    monkeypatch.setattr(oidc, "GoogleRequest", CertRequest)


def test_real_signature_verification_and_identity_mapping_without_network(config, monkeypatch):
    token, public = signed_fixture(claims())
    configure_transport(monkeypatch, token, public)
    identity = asyncio.run(oidc.exchange(config, "synthetic-code", VERIFIER, NONCE_HASH))
    assert identity.subject == "google-subject-123" and identity.issuer == oidc.ISSUER
    assert identity.email == "person@gmail.com" and identity.authoritative_email is True
    assert identity.display_name == "Person"
    assert not hasattr(identity, "access_token") and not hasattr(identity, "id_token")


@pytest.mark.parametrize(
    "change",
    [
        {"aud": "another-client"},
        {"iss": "https://attacker.test"},
        {"exp": 1},
        {"iat": 9999999999, "exp": 10000000000},
        {"nonce": "other-nonce"},
        {"email_verified": False},
        {"email_verified": "true"},
        {"sub": ""},
        {"email": "invalid"},
        {"azp": "another-client"},
        {"aud": [CLIENT, "another-client"]},
    ],
)
def test_signature_claims_fail_closed(config, monkeypatch, change):
    token, public = signed_fixture({**claims(), **change})
    configure_transport(monkeypatch, token, public)
    with pytest.raises(oidc.GoogleOIDCError, match="^GOOGLE_LOGIN_FAILED$"):
        asyncio.run(oidc.exchange(config, "synthetic-code", VERIFIER, NONCE_HASH))


def test_bad_signature_and_transport_error_are_sanitized(config, monkeypatch):
    token, _ = signed_fixture(claims())
    _, other_public = signed_fixture(claims())
    configure_transport(monkeypatch, token, other_public)
    with pytest.raises(oidc.GoogleOIDCError, match="^GOOGLE_LOGIN_FAILED$"):
        asyncio.run(oidc.exchange(config, "synthetic-code", VERIFIER, NONCE_HASH))

    def unavailable(*args, **kwargs):
        raise RuntimeError("upstream response with code and secret must never escape")

    monkeypatch.setattr(oidc.urllib.request, "urlopen", unavailable)
    with pytest.raises(oidc.GoogleOIDCError, match="^GOOGLE_LOGIN_FAILED$"):
        asyncio.run(oidc.exchange(config, "synthetic-code", VERIFIER, NONCE_HASH))
    with pytest.raises(oidc.GoogleOIDCError, match="FLOW_INVALID"):
        asyncio.run(oidc.exchange(config, "", VERIFIER, NONCE_HASH))
    with pytest.raises(oidc.GoogleOIDCError, match="NOT_CONFIGURED"):
        replace(config, secret_file=config.secret_file.parent / "missing").secret()

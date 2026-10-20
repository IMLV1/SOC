"""Google OIDC server-side transport; tokens never leave this adapter."""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, cast

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

ISSUER = "https://accounts.google.com"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
CALLBACK_PATH = "/api/v1/auth/google/callback"


class GoogleOIDCError(ValueError):
    """Only constant safe codes may leave this adapter; never upstream bodies/tokens."""


@dataclass(frozen=True)
class GoogleConfig:
    client_id: str
    redirect_uri: str
    secret_file: Path = field(repr=False)

    def secret(self) -> str:
        try:
            value = self.secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            raise GoogleOIDCError("GOOGLE_NOT_CONFIGURED") from None
        if not value or len(value) > 4096 or any(c.isspace() for c in value):
            raise GoogleOIDCError("GOOGLE_NOT_CONFIGURED")
        return value


@dataclass(frozen=True)
class GoogleIdentity:
    issuer: str
    subject: str
    email: str
    display_name: str
    authoritative_email: bool


def config_from_env(env: Mapping[str, str]) -> GoogleConfig | None:
    # Treat partial/mismatched OAuth configuration as unavailable rather than
    # constructing a redirect that could escape the registered origin.
    if env.get("GOOGLE_OAUTH_ENABLED", "false") == "false":
        return None
    client = env.get("GOOGLE_OAUTH_CLIENT_ID", "")
    callback = env.get("GOOGLE_OAUTH_REDIRECT_URI", "")
    secret = env.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE", "")
    parsed = urllib.parse.urlsplit(callback)
    local = parsed.hostname in {"127.0.0.1", "localhost"} and parsed.scheme == "http"
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if (
        env.get("GOOGLE_OAUTH_ENABLED") != "true"
        or not re.fullmatch(r"[A-Za-z0-9.-]{1,200}\.apps\.googleusercontent\.com", client)
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or not (local or parsed.scheme == "https")
        or parsed.path != CALLBACK_PATH
        or parsed.query
        or parsed.fragment
        or origin not in env.get("AUTH_ORIGINS", "").split(",")
        or not secret
    ):
        raise GoogleOIDCError("GOOGLE_NOT_CONFIGURED")
    config = GoogleConfig(client, callback, Path(secret))
    config.secret()  # Validate locally; no network, and never return this value to a client.
    return config


def authorization_url(config: GoogleConfig, state: str, nonce: str, verifier: str) -> str:
    # PKCE binds the later code exchange to this browser flow; state and nonce
    # are separately checked when Google redirects back.
    if not all(re.fullmatch(r"[A-Za-z0-9_-]{43,128}", value) for value in (state, nonce, verifier)):
        raise GoogleOIDCError("GOOGLE_FLOW_INVALID")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    return (
        AUTHORIZATION_ENDPOINT
        + "?"
        + urllib.parse.urlencode(
            {
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "prompt": "select_account",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge.decode(),
                "code_challenge_method": "S256",
            }
        )
    )


def _identity_from_verified_claims(
    claims: Mapping[str, Any], config: GoogleConfig, nonce_hash: str
) -> GoogleIdentity:
    # Signature/audience/expiry MUST already be verified by google-auth below.
    # These checks bind the signed identity to this client, redirect, and stored nonce.
    nonce = claims.get("nonce")
    audience = claims.get("aud")
    aud = audience if isinstance(audience, list) else [audience]
    subject, email = claims.get("sub"), claims.get("email")
    if (
        claims.get("iss") not in {ISSUER, "accounts.google.com"}
        or config.client_id not in aud
        or (len(aud) > 1 and claims.get("azp") != config.client_id)
        or (claims.get("azp") is not None and claims["azp"] != config.client_id)
        or not isinstance(subject, str)
        or not 1 <= len(subject) <= 255
        or claims.get("email_verified") is not True
        or not isinstance(email, str)
        or len(email) > 254
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
        or not isinstance(nonce, str)
        or not re.fullmatch(r"[0-9a-f]{64}", nonce_hash)
        or not hmac.compare_digest(hashlib.sha256(nonce.encode()).hexdigest(), nonce_hash)
    ):
        raise GoogleOIDCError("GOOGLE_IDENTITY_INVALID")
    normalized = email.strip().lower()
    name = claims.get("name")
    display = name.strip()[:60] if isinstance(name, str) and name.strip() else "Google user"
    return GoogleIdentity(
        ISSUER,
        subject,
        normalized,
        display,
        normalized.endswith("@gmail.com") or bool(claims.get("hd")),
    )


def _exchange(config: GoogleConfig, code: str, verifier: str, nonce_hash: str) -> GoogleIdentity:
    # This synchronous adapter runs in a thread from the async wrapper below.
    body = urllib.parse.urlencode(
        {
            "client_id": config.client_id,
            "client_secret": config.secret(),
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": config.redirect_uri,
        }
    ).encode()
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Response too large")
        token = json.loads(raw).get("id_token")
        if not isinstance(token, str) or not 1 <= len(token) <= 20000:
            raise ValueError("Missing identity token")
        # Certificates are fetched from the fixed Google endpoint, never a JWT-supplied URL.
        # Upstream verifier is unannotated; keep the typed adapter boundary explicit.
        verify_jwt = cast(Callable[..., Mapping[str, Any]], id_token.verify_oauth2_token)
        claims = verify_jwt(
            token,
            partial(GoogleRequest(), timeout=5),
            audience=config.client_id,
            clock_skew_in_seconds=0,
        )
        return _identity_from_verified_claims(claims, config, nonce_hash)
    except Exception:
        # No upstream error_description, code, access/refresh/id token, or secret in diagnostics.
        raise GoogleOIDCError("GOOGLE_LOGIN_FAILED") from None


async def exchange(
    config: GoogleConfig, code: str, verifier: str, nonce_hash: str
) -> GoogleIdentity:
    if not 1 <= len(code) <= 4096 or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", verifier):
        raise GoogleOIDCError("GOOGLE_FLOW_INVALID")
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_exchange, config, code, verifier, nonce_hash), timeout=15
        )
    except TimeoutError:
        raise GoogleOIDCError("GOOGLE_LOGIN_UNAVAILABLE") from None


def configured() -> bool:
    try:
        return config_from_env(os.environ) is not None
    except GoogleOIDCError:
        return False

"""Server-only Supabase Auth transport. Never return provider tokens to the browser."""

import asyncio
import base64
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import requests
from cryptography.fernet import Fernet, InvalidToken

from app.auth.service import AuthError


def enabled() -> bool:
    return os.getenv("AUTH_PROVIDER", "local") == "supabase"


def configuration() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", url):
        raise AuthError(503, "AUTH_PROVIDER_UNAVAILABLE")
    if not re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]+", key):
        raise AuthError(503, "AUTH_PROVIDER_UNAVAILABLE")
    return url, key


def cipher() -> Fernet:
    try:
        return Fernet(Path(os.environ["SUPABASE_TOKEN_KEY_FILE"]).read_bytes().strip())
    except (KeyError, OSError, ValueError):
        raise AuthError(503, "AUTH_PROVIDER_UNAVAILABLE") from None


def seal(tokens: dict[str, Any]) -> str:
    # A separate runtime key protects refresh tokens in database backups.
    # Google provider tokens/profile fields are not needed for SOC authentication.
    stored = {key: tokens[key] for key in ("access_token", "refresh_token")}
    return cipher().encrypt(json.dumps(stored).encode()).decode()


def unseal(value: str) -> dict[str, Any]:
    try:
        result = json.loads(cipher().decrypt(value.encode()))
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (InvalidToken, ValueError, TypeError):
        raise AuthError(401, "AUTH_REQUIRED") from None


async def call(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    url, key = configuration()

    def send() -> dict[str, Any]:
        try:
            response = requests.request(
                method,
                url + "/auth/v1" + path,
                headers={"apikey": key, **({"Authorization": f"Bearer {token}"} if token else {})},
                json=payload,
                timeout=(5, 15),
                allow_redirects=False,
            )
            if response.status_code == 429:
                raise AuthError(429, "RATE_LIMITED")
            if response.status_code >= 500 or 300 <= response.status_code < 400:
                raise AuthError(503, "AUTH_PROVIDER_UNAVAILABLE")
            if not response.ok:
                raise AuthError(401, "AUTH_PROVIDER_REJECTED")
            if response.status_code == 204:
                return {}
            if len(response.content) > 128_000:
                raise ValueError()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (requests.RequestException, ValueError):
            raise AuthError(503, "AUTH_PROVIDER_UNAVAILABLE") from None

    return await asyncio.to_thread(send)


@dataclass(frozen=True)
class Identity:
    subject: UUID
    session_id: UUID
    email: str
    display_name: str
    expires_at: int
    google_linked: bool = False


async def verify(tokens: dict[str, Any]) -> Identity:
    token = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    if (
        not isinstance(token, str)
        or len(token) > 16000
        or not isinstance(refresh, str)
        or not 1 <= len(refresh) <= 4096
    ):
        raise AuthError(401, "AUTH_REQUIRED")
    # The Auth server verifies the JWT signature and user state over trusted HTTPS.
    # Claims are decoded ONLY after that remote validation, never trusted on their own.
    user = await call("GET", "/user", token=token)
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError()
        claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        url, _ = configuration()
        if (
            claims["iss"] != url + "/auth/v1"
            or claims["aud"] != "authenticated"
            or claims["sub"] != user["id"]
            or claims["exp"] <= time.time()
            or not user.get("email_confirmed_at")
            or user.get("is_anonymous")
        ):
            raise ValueError()
        email = user["email"].strip().lower()
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError()
        metadata = user.get("user_metadata") or {}
        name = str(metadata.get("display_name") or metadata.get("full_name") or email.split("@")[0])
        return Identity(
            UUID(user["id"]),
            UUID(claims["session_id"]),
            email,
            name.strip()[:60] or "Analyst",
            int(claims["exp"]),
            any(
                isinstance(identity, dict) and identity.get("provider") == "google"
                for identity in (user.get("identities") or [])
            ),
        )
    except (ValueError, KeyError, TypeError):
        raise AuthError(401, "AUTH_REQUIRED") from None

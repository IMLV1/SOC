import os
import re
import ssl
from pathlib import Path

from sqlalchemy import URL

ROLES = (
    "migration_owner",
    "api_runtime",
    "worker_runtime",
    "evaluator_runtime",
    "retention_runtime",
)


def tls_connect_args(url: URL) -> dict[str, ssl.SSLContext]:
    # Cloud database connections verify both the certificate and hostname.
    # A provider CA file adds trust without disabling OS roots or verification.
    if url.host and url.host.endswith((".render.com", ".supabase.co", ".pooler.supabase.com")):
        context = ssl.create_default_context()
        if ca_file := os.environ.get("DB_SSL_CA_FILE", ""):
            context.load_verify_locations(cafile=ca_file)
        return {"ssl": context}
    return {}


def password_from_file(path: str) -> str:
    password = Path(path).read_text(encoding="utf-8").strip()
    if len(password) < 24 or "\x00" in password:
        raise ValueError("Database password file must contain at least 24 characters.")
    return password


def runtime_password() -> str:
    path = os.environ.get("DB_PASSWORD_FILE", "")
    inline = os.environ.get("DB_PASSWORD", "")
    if path and inline:
        raise ValueError("Configure only one database password source.")
    if path:
        return password_from_file(path)
    if len(inline) < 24 or "\x00" in inline:
        raise ValueError("A database runtime secret is required (at least 24 characters).")
    return inline


def database_url(role: str) -> URL:
    if role not in (*ROLES, "postgres"):
        raise ValueError("Unsupported database role.")
    provider = os.environ.get("DB_PROVIDER", "postgres")
    if provider not in {"postgres", "supabase"}:
        raise ValueError("Unsupported database provider.")
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = int(os.environ.get("DB_PORT", "5432"))
    username = role
    if provider == "supabase":
        mode = os.environ.get("DB_CONNECTION_MODE", "direct")
        project = os.environ.get("DB_PROJECT_REF", "")
        if not re.fullmatch(r"[a-z0-9]{20}", project):
            raise ValueError("A valid Supabase database project reference is required.")
        if port != 5432 or mode not in {"direct", "session"}:
            raise ValueError("Supabase requires direct or session mode on port 5432.")
        if mode == "direct":
            if host != f"db.{project}.supabase.co":
                raise ValueError("Supabase direct host does not match the project reference.")
        else:
            if not re.fullmatch(r"[a-z0-9-]+\.pooler\.supabase\.com", host):
                raise ValueError("A Supabase shared session pooler host is required.")
            # The pooler tenant suffix is not the PostgreSQL role itself.
            username = f"{role}.{project}"
    # No arbitrary DB_USER override: every process retains its allowlisted role.
    return URL.create(
        "postgresql+asyncpg",
        username=username,
        password=runtime_password(),
        host=host,
        port=port,
        database=os.environ.get("DB_NAME", "postgres" if provider == "supabase" else "soc"),
    )

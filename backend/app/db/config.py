import os
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
    # External Render connections require TLS. Use OS trusted CAs and hostname
    # validation explicitly; asyncpg's verify-full string expects a root.crt file.
    if url.host and url.host.endswith(".render.com"):
        return {"ssl": ssl.create_default_context()}
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
    # Each process receives only its role's secret, never owner/evaluator credentials.
    return URL.create(
        "postgresql+asyncpg",
        username=role,
        password=runtime_password(),
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "soc"),
    )

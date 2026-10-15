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


def database_url(role: str) -> URL:
    if role not in (*ROLES, "postgres"):
        raise ValueError("Unsupported database role.")
    # Per-process secret mount: API receives only its own file, never owner/evaluator secrets.
    path = os.environ.get("DB_PASSWORD_FILE", "")
    if not path:
        raise ValueError("DB_PASSWORD_FILE is required.")
    return URL.create(
        "postgresql+asyncpg",
        username=role,
        password=password_from_file(path),
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "soc"),
    )

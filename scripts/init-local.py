"""Create local-only database passwords. Repeat preserves all existing files."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
private = root / ".local"
private.mkdir(mode=0o700, exist_ok=True)
if os.name == "posix":
    private.chmod(0o700)
directory = private / "secrets"
directory.mkdir(parents=True, exist_ok=True)
if os.name == "posix":
    # Parent .local is private on the host. Mounted files must be readable by container users.
    directory.chmod(0o755)
for role in (
    "postgres",
    "migration_owner",
    "api_runtime",
    "worker_runtime",
    "evaluator_runtime",
    "retention_runtime",
):
    path = directory / f"{role}.txt"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        continue
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(secrets.token_urlsafe(48))
    if os.name == "posix":
        path.chmod(0o444)
print(
    "Local password files ready in .local/secrets "
    "(no passwords printed, no existing files replaced)."
)

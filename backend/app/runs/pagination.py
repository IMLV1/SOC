"""Opaque keyset cursors bound to a list's active filters."""

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from app.auth.service import AuthError


def signature(filters: Mapping[str, object]) -> str:
    # The cursor is only valid for the filter set that created it; canonical JSON
    # makes that binding independent of mapping insertion order.
    data = json.dumps(filters, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def encode_cursor(created_at: datetime, identity: UUID, filters: Mapping[str, object]) -> str:
    body = {"at": created_at.isoformat(), "id": str(identity), "filters": signature(filters)}
    return base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode()


def decode_cursor(
    value: str | None, filters: Mapping[str, object]
) -> tuple[datetime | None, UUID | None]:
    if value is None:
        return None, None
    try:
        # Treat cursor contents as untrusted input and collapse parse failures to
        # the contract's single public error, without leaking decoder details.
        data = json.loads(base64.urlsafe_b64decode(value.encode()).decode())
        at = datetime.fromisoformat(data["at"])
        identity = UUID(data["id"])
        if at.tzinfo is None or data["filters"] != signature(filters):
            raise ValueError
        return at, identity
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, binascii.Error):
        raise AuthError(400, "BAD_CURSOR") from None

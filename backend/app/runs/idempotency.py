"""Atomic request-key cache for domain POST operations."""

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthError


def body_hash(body: object) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


async def reserve(
    session: AsyncSession, user_id: UUID, route: str, key: UUID, body: object
) -> tuple[UUID, dict[str, Any] | None]:
    digest = body_hash(body)
    identity = uuid4()
    created = await session.scalar(
        text("""INSERT INTO app.idempotency_keys
        (id,user_id,method,route_key,key,request_hash,status,expires_at)
        VALUES (:id,:user,'POST',:route,:key,:hash,'reserved',
                clock_timestamp() + interval '30 days')
        ON CONFLICT(user_id,method,route_key,key) DO NOTHING RETURNING id"""),
        {"id": identity, "user": user_id, "route": route, "key": key, "hash": digest},
    )
    if created is not None:
        return identity, None
    row = (
        (
            await session.execute(
                text("""SELECT id,request_hash,status,response_json
        FROM app.idempotency_keys WHERE user_id=:user AND method='POST'
        AND route_key=:route AND key=:key FOR UPDATE"""),
                {"user": user_id, "route": route, "key": key},
            )
        )
        .mappings()
        .one()
    )
    if row["request_hash"] != digest:
        raise AuthError(409, "IDEMPOTENCY_CONFLICT")
    if row["status"] != "completed" or row["response_json"] is None:
        raise AuthError(409, "REQUEST_IN_PROGRESS")
    return row["id"], dict(row["response_json"])


async def complete(
    session: AsyncSession,
    identity: UUID,
    result: dict[str, Any],
    resource_id: UUID,
    response_status: int = 201,
) -> None:
    await session.execute(
        text("""UPDATE app.idempotency_keys SET status='completed',
        response_status=:status,response_json=CAST(:body AS jsonb),resource_id=:resource
        WHERE id=:id AND status='reserved'"""),
        {
            "id": identity,
            "status": response_status,
            "body": json.dumps(result, default=str),
            "resource": resource_id,
        },
    )

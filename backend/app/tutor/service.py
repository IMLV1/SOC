"""Tutor admission: owner guard, immutable question, shared logical quota and USD hold."""

import hashlib
import os
import re
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthError
from app.knowledge.generation import redact
from app.learning.access import require_level
from app.learning.practice_routes import digest, encoded
from app.tutor.models import TutorResult, TutorSource, TutorView

SECTION = re.compile(r"\bSOC-\d{3}\b")
NO_MATCH_ANSWER = (
    "ข้อมูลจากคู่มือที่ได้รับยังไม่เพียงพอ กรุณาระบุหัวข้อหรือรายละเอียดคำถามเพิ่มเติม ไม่พบแหล่งอ้างอิงที่รองรับในบริบทที่ได้รับ"
)


class NoKnowledgeMatch(ValueError):
    """The published retrieval-only branch found no supporting material."""


def answer_without_reasoning(value: str) -> str:
    """Only remove a complete leading reasoning block; malformed output is rejected."""
    answer = value.strip()
    if answer.startswith("<think>"):
        end = answer.find("</think>")
        if end < 0:
            raise ValueError("Incomplete reasoning block")
        reasoning = answer[len("<think>") : end]
        if "<think" in reasoning.lower():
            raise ValueError("Nested reasoning block")
        answer = answer[end + len("</think>") :].strip()
    if not answer or re.search(r"</?think\b", answer, re.IGNORECASE):
        raise ValueError("Invalid reasoning output")
    return answer


def redact_question(value: str) -> str:
    value = str(redact(value))
    value = re.sub(r"\b(?:app-|sb_secret_|AIza)[A-Za-z0-9_-]{16,}", "[redacted-key]", value)
    value = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", value)
    return re.sub(r"(?i)\b(password|token|api_key|secret)\s*[:=]\s*\S+", r"\1=[redacted]", value)


def readiness(policy: Any) -> str | None:
    if not policy["enabled"] or not policy["cost_bound_verified"]:
        return "DIFY_RELEASE_NOT_APPROVED"
    key_path = os.getenv("DIFY_APP_KEY_FILE", "")
    if not key_path or not Path(key_path).is_file():
        return "DIFY_CREDENTIAL_UNAVAILABLE"
    return None


async def release_drift(session: AsyncSession, version: int) -> bool:
    """Stop new dispatches after observing drift until operator re-approval."""
    return bool(
        await session.scalar(
            text("""SELECT EXISTS(SELECT 1 FROM app.tutor_questions
            WHERE policy_version=:version AND error_code='DIFY_WORKFLOW_VERSION_MISMATCH')
            OR EXISTS(SELECT 1 FROM app.written_feedback
            WHERE policy_version=:version AND error_code='DIFY_WORKFLOW_VERSION_MISMATCH')
            OR EXISTS(SELECT 1 FROM app.practice_ai_questions
            WHERE policy_version=:version AND error_code='DIFY_WORKFLOW_VERSION_MISMATCH')"""),
            {"version": version},
        )
    )


def question_view(row: Any, policy: Any) -> TutorView:
    withdrawn = (
        not policy["enabled"]
        or policy["version"] != row["policy_version"]
        or policy["corpus_revision"] != row["corpus_revision"]
    )
    if row["result_json"] is not None:
        for source in row["result_json"]["sources"]:
            if (
                source["document_id"] not in policy["document_ids"]
                or hashlib.sha256(source["excerpt"].encode()).hexdigest()
                not in policy["chunk_hashes"]
            ):
                withdrawn = True
    return TutorView(
        id=row["id"],
        lesson_id=row["lesson_id"],
        question=row["question"],
        status="withdrawn" if withdrawn else row["status"],
        result=None if withdrawn else row["result_json"],
        error_code="KNOWLEDGE_WITHDRAWN" if withdrawn else row["error_code"],
        created_at=row["created_at"],
    )


def validate_outputs(
    outputs: dict[str, Any], document_ids: list[str], chunk_hashes: list[str]
) -> TutorResult:
    answer = outputs.get("answer")
    sources = outputs.get("sources")
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 12000:
        raise ValueError("Invalid answer")
    answer = answer_without_reasoning(answer)
    if sources == [] and answer == NO_MATCH_ANSWER:
        raise NoKnowledgeMatch("No supporting retrieval")
    # Some models typeset identifiers with a non-breaking hyphen. Normalize only
    # this exact identifier shape, never source bytes (their hashes are pinned).
    answer = re.sub(r"\bSOC[\u2010\u2011](\d{3})\b", r"SOC-\1", answer)
    if not isinstance(sources, list) or not 1 <= len(sources) <= 5:
        raise ValueError("Retrieval sources required")
    projected = []
    for item in sources:
        if not isinstance(item, dict):
            raise ValueError("Invalid source")
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("Source metadata required")
        document = metadata.get("document_id")
        content, title = item.get("content"), item.get("title")
        if document not in document_ids or not isinstance(document, str):
            raise ValueError("Unauthorized source")
        if not isinstance(content, str) or not 1 <= len(content) <= 6000:
            raise ValueError("Invalid source content")
        if hashlib.sha256(content.encode()).hexdigest() not in chunk_hashes:
            raise ValueError("Source content not in approved immutable release")
        if not isinstance(title, str) or not 1 <= len(title) <= 500:
            raise ValueError("Invalid source title")
        projected.append(
            TutorSource(
                document_id=document,
                title=title,
                excerpt=content,
                section_ids=sorted(set(SECTION.findall(content))),
            )
        )
    cited = set(SECTION.findall(answer))
    available = {section for source in projected for section in source.section_ids}
    if not cited or not cited.issubset(available):
        raise ValueError("Citation not present in retrieval snapshot")
    # Do not accept remembered URLs that are absent from the retrieved context.
    context = "\n".join(source.excerpt for source in projected)
    for url in re.findall(r"https?://[^\s<>\]\)]+", answer):
        if url not in context:
            raise ValueError("URL not present in retrieval snapshot")
    return TutorResult(answer=answer, sources=projected)


async def admit(
    session: AsyncSession, owner: UUID, lesson_id: UUID, question: str, key: UUID
) -> TutorView:
    lesson = (
        (
            await session.execute(
                text("SELECT level_id FROM app.lessons WHERE id=:id AND published_at<=now()"),
                {"id": lesson_id},
            )
        )
        .mappings()
        .first()
    )
    if lesson is None:
        raise AuthError(404, "NOT_FOUND")
    await require_level(session, owner, lesson["level_id"])
    await session.execute(text("SELECT pg_advisory_xact_lock(73102007)"))
    policy = (
        (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1"))).mappings().one()
    )
    fingerprint = digest({"lesson_id": str(lesson_id), "question": question})
    existing = (
        (
            await session.execute(
                text(
                    "SELECT * FROM app.tutor_questions "
                    "WHERE owner_user_id=:owner AND idempotency_key=:key"
                ),
                {"owner": owner, "key": key},
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        if existing["request_hash"] != fingerprint:
            raise AuthError(409, "IDEMPOTENCY_CONFLICT")
        return question_view(existing, policy)
    reason = readiness(policy)
    if reason:
        raise AuthError(503, reason)
    if await release_drift(session, policy["version"]):
        raise AuthError(503, "DIFY_WORKFLOW_VERSION_MISMATCH")
    await reserve_logical_request(session, owner)
    question_id = uuid4()
    row = (
        (
            await session.execute(
                text("""INSERT INTO app.tutor_questions
        (id,owner_user_id,lesson_id,question,idempotency_key,request_hash,
         policy_version,workflow_id,corpus_revision,reserved_usd)
        VALUES(:id,:owner,:lesson,:question,:key,:hash,:version,:workflow,:corpus,:cost)
        RETURNING *"""),
                {
                    "id": question_id,
                    "owner": owner,
                    "lesson": lesson_id,
                    "question": redact_question(question),
                    "key": key,
                    "hash": fingerprint,
                    "version": policy["version"],
                    "workflow": policy["workflow_id"],
                    "corpus": policy["corpus_revision"],
                    "cost": policy["call_bound_usd"],
                },
            )
        )
        .mappings()
        .one()
    )
    await session.execute(
        text("""INSERT INTO app.jobs(id,type,dedupe_key,payload)
        VALUES(:id,'tutor_question',:dedupe,CAST(:payload AS jsonb))"""),
        {
            "id": uuid4(),
            "dedupe": f"tutor:{question_id}",
            "payload": encoded({"question_id": str(question_id)}),
        },
    )
    return question_view(row, policy)


async def reserve_logical_request(session: AsyncSession, owner: UUID) -> None:
    """Consume one of the user's daily logical AI requests under locked ledgers."""
    quota = await session.scalar(
        text("SELECT daily_ai_requests FROM app.user_quotas WHERE user_id=:owner"), {"owner": owner}
    )
    if quota is None:
        raise AuthError(403, "FORBIDDEN")
    today = await session.scalar(text("SELECT (clock_timestamp() AT TIME ZONE 'UTC')::date"))
    for scope, user in (("system", None), (f"user:{owner}", owner)):
        await session.execute(
            text("""INSERT INTO app.quota_ledgers
            (id,scope_key,user_id,period_start) VALUES(:id,:scope,:user,:day)
            ON CONFLICT(scope_key,period_start) DO NOTHING"""),
            {"id": uuid4(), "scope": scope, "user": user, "day": today},
        )
        ledger = (
            (
                await session.execute(
                    text("""SELECT id,ai_request_count
            FROM app.quota_ledgers WHERE scope_key=:scope AND period_start=:day FOR UPDATE"""),
                    {"scope": scope, "day": today},
                )
            )
            .mappings()
            .one()
        )
        if user is not None and ledger["ai_request_count"] >= quota:
            raise AuthError(429, "AI_QUOTA_EXCEEDED")
        await session.execute(
            text("""UPDATE app.quota_ledgers
            SET ai_request_count=ai_request_count+1,version=version+1 WHERE id=:id"""),
            {"id": ledger["id"]},
        )

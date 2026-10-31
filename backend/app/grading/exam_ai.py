"""Post-submit Dify grading. Private case truth never leaves the evaluator."""

import hashlib
import json
import re
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, StrictInt
from sqlalchemy import text

from app.db.session import Database
from app.grading.rubric import FOUNDATIONS_RUBRIC, score_rubric
from app.http_models import StrictModel
from app.knowledge.dify_client import DifyConfig, DifyUnavailable
from app.knowledge.dify_workflow import run_workflow
from app.tutor.service import answer_without_reasoning, redact_question
from app.worker.fencing import LeaseLost, lock_domain, require_lease


class ExamAIResult(StrictModel):
    analysis_score: StrictInt = Field(ge=0, le=2)
    reasoning_score: StrictInt = Field(ge=0, le=2)
    analysis_feedback: str = Field(min_length=1, max_length=400)
    reasoning_feedback: str = Field(min_length=1, max_length=400)
    evidence_refs: list[UUID] = Field(min_length=1, max_length=50)
    section_ids: list[str] = Field(max_length=5)


def validate_grade(outputs: dict[str, Any], event_ids: set[UUID], policy: Any) -> ExamAIResult:
    raw = outputs.get("answer")
    sources = outputs.get("sources")
    if not isinstance(raw, str) or len(raw) > 12000 or not isinstance(sources, list):
        raise ValueError("EXAM_AI_OUTPUT_INVALID")
    data = json.loads(answer_without_reasoning(raw))
    result = ExamAIResult.model_validate(data)
    if (
        len(set(result.evidence_refs)) != len(result.evidence_refs)
        or not set(result.evidence_refs) <= event_ids
    ):
        raise ValueError("EXAM_AI_EVIDENCE_INVALID")
    if len(sources) > 5:
        raise ValueError("EXAM_AI_CITATION_INVALID")
    allowed_sections: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("metadata"), dict):
            raise ValueError("EXAM_AI_CITATION_INVALID")
        content = source.get("content")
        if (
            source["metadata"].get("document_id") not in policy["document_ids"]
            or not isinstance(content, str)
            or hashlib.sha256(content.encode()).hexdigest() not in policy["chunk_hashes"]
        ):
            raise ValueError("EXAM_AI_CITATION_INVALID")
        allowed_sections.update(re.findall(r"\bSOC-\d{3}\b", content))
    if not set(result.section_ids) <= allowed_sections:
        raise ValueError("EXAM_AI_CITATION_INVALID")
    feedback = result.analysis_feedback + " " + result.reasoning_feedback
    if re.search(r"https?://|<think|</think", feedback, re.IGNORECASE):
        raise ValueError("EXAM_AI_OUTPUT_INVALID")
    if set(re.findall(r"\bSOC-\d{3}\b", feedback)) - set(result.section_ids):
        raise ValueError("EXAM_AI_CITATION_INVALID")
    return result


async def _mark_review(
    database: Database, job: dict[str, Any], code: str, *, dispatched: bool
) -> None:
    attempt_id = UUID(job["payload"]["attempt_id"])
    async with database.sessions() as session, session.begin():
        if not await lock_domain(session, job):
            raise LeaseLost("Exam grading lease lost")
        await session.execute(
            text("""UPDATE app.exam_ai_grades SET status='needs_review',error_code=:code,
              usage_status=:usage,finished_at=clock_timestamp() WHERE attempt_id=:attempt
              AND status IN ('queued','running')"""),
            {
                "code": code,
                "usage": "unknown" if dispatched else "released",
                "attempt": attempt_id,
            },
        )
        await session.execute(
            text("""UPDATE app.exam_attempts SET status='needs_review',version=version+1
              WHERE id=:attempt AND status='submitted'"""),
            {"attempt": attempt_id},
        )
        await require_lease(session, job)


async def process_exam_grade(database: Database, job: dict[str, Any]) -> None:
    attempt_id = UUID(job["payload"]["attempt_id"])
    async with database.sessions() as session, session.begin():
        if not await lock_domain(session, job):
            raise LeaseLost("Exam grading lease lost")
        row = (
            (
                await session.execute(
                    text("SELECT * FROM app.exam_ai_grades WHERE attempt_id=:id FOR UPDATE"),
                    {"id": attempt_id},
                )
            )
            .mappings()
            .one()
        )
        if row["status"] not in {"queued", "running"}:
            return
        if row["dispatch_started_at"] is not None:
            # A previous lease might have sent a paid call. Never dispatch it again.
            await session.execute(
                text("""UPDATE app.exam_ai_grades SET status='needs_review',
              error_code='DIFY_DISPATCH_OUTCOME_UNKNOWN',usage_status='unknown',
              finished_at=clock_timestamp() WHERE attempt_id=:id"""),
                {"id": attempt_id},
            )
            await session.execute(
                text("""UPDATE app.exam_attempts SET status='needs_review',
              version=version+1 WHERE id=:id AND status='submitted'"""),
                {"id": attempt_id},
            )
            await require_lease(session, job)
            return
        policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        if (
            not policy["enabled"]
            or not policy["exam_grade_enabled"]
            or not policy["cost_bound_verified"]
            or policy["version"] != row["policy_version"]
            or policy["corpus_revision"] != row["corpus_revision"]
        ):
            reason = "DIFY_EXAM_POLICY_UNAVAILABLE"
        else:
            reason = None
        answer = (
            (
                await session.execute(
                    text("SELECT * FROM app.exam_answers WHERE attempt_id=:id"),
                    {"id": attempt_id},
                )
            )
            .mappings()
            .one()
        )
        attempt = (
            (
                await session.execute(
                    text("""SELECT id,run_id,case_id,level_id,owner_user_id,status
          FROM app.exam_attempts WHERE id=:id FOR UPDATE"""),
                    {"id": attempt_id},
                )
            )
            .mappings()
            .one()
        )
        events = (
            (
                await session.execute(
                    text("""SELECT id,release_seq,fixture_event_key,event_time,
          source,asset_id,username,src_ip,request_json,response_json,log_json
          FROM app.events WHERE run_id=:run AND release_seq<=:cutoff ORDER BY release_seq"""),
                    {"run": attempt["run_id"], "cutoff": answer["release_cutoff"]},
                )
            )
            .mappings()
            .all()
        )
        if attempt["status"] != "submitted" or not events:
            reason = "EXAM_AI_SNAPSHOT_UNAVAILABLE"
        if reason:
            await session.execute(
                text("""UPDATE app.exam_ai_grades SET status='unavailable',
              error_code=:reason,usage_status='released',finished_at=clock_timestamp()
              WHERE attempt_id=:id"""),
                {"id": attempt_id, "reason": reason},
            )
            await session.execute(
                text("""UPDATE app.exam_attempts SET status='needs_review',
              version=version+1 WHERE id=:id AND status='submitted'"""),
                {"id": attempt_id},
            )
            await require_lease(session, job)
            return
        question = json.dumps(
            {
                "task": (
                    "Assess whether the learner's main conclusion is relevant and supported "
                    "by the frozen released evidence. Be encouraging and lenient: a concise, "
                    "on-point answer earns analysis_score at least 1 even if it omits secondary "
                    "checks or extra details. Give score 0 only when the conclusion is off-topic, "
                    "unsupported, or contradicted by the evidence. Treat reasoning_score as "
                    "coaching detail, not a pass requirement. Feedback should acknowledge what is "
                    "right first, then suggest one or two useful additions without revealing the "
                    "case answer. Do not grade severity/disposition or select evidence."
                ),
                "answer": {
                    "evidence_event_ids": answer["evidence_event_ids"],
                    "severity": answer["severity"],
                    "disposition": answer["disposition"],
                    "reason": redact_question(answer["reason"]),
                },
                "events": [
                    {
                        "id": str(event["id"]),
                        "event_time": str(event["event_time"]),
                        "request": event["request_json"],
                        "response": event["response_json"],
                        "log": event["log_json"],
                    }
                    for event in events
                ],
            },
            ensure_ascii=False,
            default=str,
        )
        if len(question) > 24000:
            await session.execute(
                text("""UPDATE app.exam_ai_grades SET status='unavailable',
              error_code='DIFY_CONTEXT_TOO_LONG',usage_status='released',finished_at=clock_timestamp()
              WHERE attempt_id=:id"""),
                {"id": attempt_id},
            )
            await session.execute(
                text("""UPDATE app.exam_attempts SET status='needs_review',
              version=version+1 WHERE id=:id AND status='submitted'"""),
                {"id": attempt_id},
            )
            await require_lease(session, job)
            return
        await session.execute(
            text("""UPDATE app.exam_ai_grades SET status='running',
          dispatch_started_at=clock_timestamp() WHERE attempt_id=:id"""),
            {"id": attempt_id},
        )
        await require_lease(session, job)

    try:
        config = DifyConfig.from_env()
        reply = await run_workflow(
            config,
            row["workflow_id"],
            question,
            f"exam-grade-{attempt_id}",
            mode="exam_grade",
        )
        ai = validate_grade(reply.outputs, {event["id"] for event in events}, policy)
    except (DifyUnavailable, ValueError, TypeError, KeyError) as exc:
        code = str(exc) if isinstance(exc, DifyUnavailable) else "EXAM_AI_OUTPUT_INVALID"
        await _mark_review(database, job, code, dispatched=True)
        return

    async with database.sessions() as session, session.begin():
        if not await lock_domain(session, job):
            raise LeaseLost("Exam grading lease lost")
        attempt = (
            (
                await session.execute(
                    text("""SELECT id,owner_user_id,level_id,case_id,status
          FROM app.exam_attempts WHERE id=:id FOR UPDATE"""),
                    {"id": attempt_id},
                )
            )
            .mappings()
            .one()
        )
        grade_row = (
            (
                await session.execute(
                    text("SELECT * FROM app.exam_ai_grades WHERE attempt_id=:id FOR UPDATE"),
                    {"id": attempt_id},
                )
            )
            .mappings()
            .one()
        )
        current_policy = (
            (await session.execute(text("SELECT * FROM app.tutor_policy WHERE id=1")))
            .mappings()
            .one()
        )
        if (
            attempt["status"] != "submitted"
            or grade_row["status"] != "running"
            or not current_policy["enabled"]
            or not current_policy["exam_grade_enabled"]
            or current_policy["version"] != grade_row["policy_version"]
            or current_policy["corpus_revision"] != grade_row["corpus_revision"]
        ):
            await session.execute(
                text("""UPDATE app.exam_ai_grades SET status='withdrawn',
              error_code='KNOWLEDGE_WITHDRAWN',usage_status='reconciled',
              reported_tokens=:tokens,finished_at=clock_timestamp() WHERE attempt_id=:id"""),
                {"id": attempt_id, "tokens": reply.total_tokens},
            )
            await session.execute(
                text("""UPDATE app.exam_attempts SET status='needs_review',
              version=version+1 WHERE id=:id AND status='submitted'"""),
                {"id": attempt_id},
            )
            await require_lease(session, job)
            return
        truth = (
            (
                await session.execute(
                    text("""SELECT t.expected_evidence_keys,t.expected_severity,
          t.expected_disposition FROM private.exam_case_truths t
          JOIN app.exam_cases c ON c.id=t.case_id
          JOIN app.scenarios s ON s.id=c.scenario_id AND s.version=t.version
          WHERE c.id=:case"""),
                    {"case": attempt["case_id"]},
                )
            )
            .mappings()
            .one()
        )
        answer = (
            (
                await session.execute(
                    text("SELECT * FROM app.exam_answers WHERE attempt_id=:id"),
                    {"id": attempt_id},
                )
            )
            .mappings()
            .one()
        )
        selected_ids = {UUID(str(item)) for item in answer["evidence_event_ids"]}
        event_keys = {event["id"]: event["fixture_event_key"] for event in events}
        selected_keys = {event_keys[item] for item in selected_ids if item in event_keys}
        expected_keys = set(truth["expected_evidence_keys"])
        evidence_score = (
            2 if selected_keys == expected_keys else (1 if selected_keys & expected_keys else 0)
        )
        classification_score = (
            2
            if (
                answer["severity"] == truth["expected_severity"]
                and answer["disposition"] == truth["expected_disposition"]
            )
            else 0
        )
        scores: dict[str, int | None] = {
            "evidence": evidence_score,
            "analysis": ai.analysis_score,
            "classification": classification_score,
            "reasoning": ai.reasoning_score,
        }
        grade = score_rubric(scores)
        feedback = {
            "analysis": ai.analysis_feedback,
            "reasoning": ai.reasoning_feedback,
            "evidence": (
                "เลือกหลักฐานที่เกี่ยวข้องกับประเด็นหลักได้แล้ว"
                if evidence_score == 2
                else "มีหลักฐานที่เกี่ยวข้องแล้ว; ลองเสริม event ที่เชื่อมกับข้อสรุปให้ชัดขึ้น"
                if evidence_score == 1
                else "ลองเทียบ event ที่เลือกกับข้อสรุปอีกครั้ง แล้วเลือกหลักฐานที่รองรับประเด็นหลัก"
            ),
            "classification": (
                "การจัดประเภทสอดคล้องกับหลักฐาน"
                if classification_score == 2
                else "ลองทบทวน severity/disposition และเพิ่มเหตุผลที่เชื่อมกับหลักฐาน"
            ),
        }
        criteria = [
            {
                "key": item.key,
                "score": scores[item.key],
                "maximum": 2,
                "feedback": feedback[item.key],
            }
            for item in FOUNDATIONS_RUBRIC.criteria
        ]
        grade_id = uuid4()
        await session.execute(
            text("""INSERT INTO app.grading_revisions
          (id,attempt_id,revision,source,rubric_version,status,score,criteria_json,model_id,reason)
          VALUES (:id,:attempt,1,'ai',:rubric,:status,:score,CAST(:criteria AS jsonb),
                  'dify:exam_grade',:reason)"""),
            {
                "id": grade_id,
                "attempt": attempt_id,
                "rubric": grade.rubric_version,
                "status": grade.status,
                "score": grade.score,
                "criteria": json.dumps(criteria, ensure_ascii=False),
                "reason": "Automated post-submission rubric evaluation",
            },
        )
        await session.execute(
            text("""UPDATE app.exam_attempts SET status=:status,
          version=version+1,finalized_at=clock_timestamp() WHERE id=:id"""),
            {"id": attempt_id, "status": grade.status},
        )
        await session.execute(
            text("""UPDATE app.exam_ai_grades SET status='succeeded',
          usage_status='reconciled',reported_tokens=:tokens,finished_at=clock_timestamp()
          WHERE attempt_id=:id"""),
            {"id": attempt_id, "tokens": reply.total_tokens},
        )
        if grade.status == "passed":
            cases = await session.scalar(
                text("""SELECT count(*) FROM app.exam_cases
              WHERE level_id=:level AND enabled"""),
                {"level": attempt["level_id"]},
            )
            passed_attempts = await session.scalar(
                text("""SELECT count(DISTINCT a.id)
              FROM app.exam_attempts a JOIN app.grading_revisions g ON g.attempt_id=a.id
              WHERE a.owner_user_id=:owner AND a.level_id=:level AND a.status='passed'
                AND g.status='passed'
              AND g.revision=(SELECT max(g2.revision) FROM app.grading_revisions g2
                WHERE g2.attempt_id=a.id)"""),
                {"owner": attempt["owner_user_id"], "level": attempt["level_id"]},
            )
            if cases and cases == passed_attempts:
                next_level = await session.scalar(
                    text("""SELECT id FROM app.learning_levels
                  WHERE ordinal=(SELECT ordinal+1 FROM app.learning_levels WHERE id=:level)
                  AND enabled ORDER BY version DESC LIMIT 1"""),
                    {"level": attempt["level_id"]},
                )
                if next_level:
                    await session.execute(
                        text("""INSERT INTO app.level_unlocks
                      (user_id,level_id,earned_from_revision_id) VALUES (:owner,:level,:revision)
                      ON CONFLICT(user_id,level_id) DO NOTHING"""),
                        {
                            "owner": attempt["owner_user_id"],
                            "level": next_level,
                            "revision": grade_id,
                        },
                    )
        await session.execute(
            text("""INSERT INTO app.audit_logs
          (id,actor_user_id,actor_role,action,entity_type,entity_id,reason)
          VALUES (:id,NULL,'system','exam.ai_grade','exam_attempt',:attempt,:reason)"""),
            {"id": uuid4(), "attempt": attempt_id, "reason": grade.status},
        )
        await require_lease(session, job)

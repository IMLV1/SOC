"""Typed provider boundary; this step supplies only deterministic mock output."""

from typing import Any, Protocol
from uuid import UUID

from pydantic import Field

from app.analysis.models import AnalysisResult
from app.auth.models import Strict


class EvidenceItem(Strict):
    id: UUID
    source: str
    username: str | None
    request: dict[str, Any] | None
    response: dict[str, Any] | None
    log: dict[str, Any]


class AnalysisInput(Strict):
    analysis_id: UUID
    evidence: list[EvidenceItem] = Field(min_length=1)
    prompt_version: str
    max_output_tokens: int = Field(ge=1, le=2048)


class AnalysisProvider(Protocol):
    async def analyze(self, data: AnalysisInput) -> dict[str, Any]: ...


class MockProvider:
    async def analyze(self, data: AnalysisInput) -> dict[str, Any]:
        kinds = [item.log.get("event_type") for item in data.evidence]
        read = "records_read" in kinds
        session = "session_created" in kinds
        blocked = "request_policy_denied" in kinds or any(
            item.response and item.response.get("status") == 403 for item in data.evidence
        )
        anomaly = "historical_read_rate" in kinds and read
        if blocked:
            summary = "พบ request ที่ถูกปฏิเสธ ยังไม่พบหลักฐานว่าการเข้าถึงสำเร็จ"
            observed = "Request ถูกปฏิเสธ"
            severity = "low"
        elif session and read:
            summary = "พบ session สำเร็จหลังความพยายาม login และมีการอ่านข้อมูล"
            observed = "มี session และการอ่านข้อมูลใน log"
            severity = "high"
        elif anomaly:
            summary = "ปริมาณการอ่านข้อมูลสูงกว่าค่า baseline ในหลักฐาน"
            observed = "มีการอ่านข้อมูลจริงตาม log แต่ยังไม่ทราบสาเหตุ"
            severity = "high"
        elif "scanner_request" in kinds:
            summary = "พบการสแกนเว็บ ควรเทียบ change record ก่อนตัดสิน"
            observed = "มี request จาก scanner"
            severity = "low" if "approved_scan_window" in kinds else "medium"
        else:
            summary = "พบสัญญาณที่ต้องตรวจเพิ่ม ยังไม่มีหลักฐานยืนยันผลกระทบ"
            observed = "พบเหตุการณ์ตามหลักฐานที่ปล่อยแล้ว"
            severity = "medium"
        refs = [item.id for item in data.evidence]
        result = AnalysisResult.model_validate(
            dict(
                summary=summary,
                hypotheses=[
                    {"text": "ควรตรวจความเชื่อมโยงและยืนยันเจ้าของกิจกรรม", "evidence_refs": refs}
                ],
                evidence_refs=refs,
                observed_impact=observed,
                potential_impact="อาจมีผลกระทบเพิ่มเติม แต่หลักฐานปัจจุบันยังไม่ยืนยัน",
                suggested_severity={"level": severity, "reason": "อ้างจากผลตอบกลับและ log ที่ปล่อยแล้ว"},
                confidence={"level": "medium", "reason": "เป็นการวิเคราะห์จำลอง ไม่ใช่ provider จริง"},
                unknowns=["เจ้าของบัญชีหรือผู้ดูแลยืนยันกิจกรรมหรือยัง"],
                recommended_checks=["ตรวจ timeline, request/response และยืนยันกับเจ้าของกิจกรรม"],
            )
        )
        return result.model_dump(mode="json")


def validate_citations(result: AnalysisResult, allowed: set[UUID]) -> None:
    refs = set(result.evidence_refs)
    for hypothesis in result.hypotheses:
        refs.update(hypothesis.evidence_refs)
    if not refs or not refs <= allowed:
        raise ValueError("EVIDENCE_OUTSIDE_SNAPSHOT")

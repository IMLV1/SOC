import hashlib
import json
from uuid import uuid4

import pytest

from app.analysis.dify_provider import validate_analysis_outputs
from app.analysis.provider import AnalysisInput


def sample():
    evidence_id = uuid4()
    context = "## SOC-003 — HTTP response\n403 แสดงการปฏิเสธคำขอ"
    data = AnalysisInput.model_validate(
        {
            "analysis_id": uuid4(),
            "evidence": [
                {
                    "id": evidence_id,
                    "source": "web",
                    "username": None,
                    "request": {"path": "/admin"},
                    "response": {"status": 403},
                    "log": {"event_type": "request_policy_denied"},
                }
            ],
            "prompt_version": "prompt-v1",
            "max_output_tokens": 2048,
        }
    )
    result = {
        "summary": "พบ 403 ตามหลักฐาน ไม่ยืนยันการเข้าถึงสำเร็จ SOC-003",
        "hypotheses": [{"text": "ผู้ส่งคำขออาจไม่มีสิทธิ์", "evidence_refs": [str(evidence_id)]}],
        "evidence_refs": [str(evidence_id)],
        "knowledge_refs": [],
        "observed_impact": "คำขอถูกปฏิเสธ",
        "potential_impact": "ยังไม่ทราบ",
        "suggested_severity": {"level": "low", "reason": "พบเพียง 403"},
        "confidence": {"level": "low", "reason": "หลักฐานจำกัด"},
        "unknowns": ["กิจกรรมก่อนหน้า"],
        "recommended_checks": ["ดู request อื่น"],
    }
    outputs = {
        "answer": json.dumps(result, ensure_ascii=False),
        "sources": [
            {
                "content": context,
                "title": "คู่มือ",
                "metadata": {"document_id": "approved"},
            }
        ],
    }
    policy = {
        "document_ids": ["approved"],
        "chunk_hashes": [hashlib.sha256(context.encode()).hexdigest()],
    }
    return data, outputs, policy, result


def test_analysis_accepts_only_frozen_evidence_and_approved_sources():
    data, outputs, policy, result = sample()
    assert validate_analysis_outputs(outputs, data, policy).summary == result["summary"]
    for change in (
        result | {"evidence_refs": [str(uuid4())]},
        result | {"knowledge_refs": [str(uuid4())]},
        result | {"summary": "อ้าง SOC-999"},
    ):
        with pytest.raises(ValueError):
            validate_analysis_outputs(outputs | {"answer": json.dumps(change)}, data, policy)
    with pytest.raises(ValueError):
        validate_analysis_outputs(outputs, data, policy | {"document_ids": ["other"]})


def test_analysis_rejects_missing_or_unapproved_retrieval():
    data, outputs, policy, _ = sample()
    for sources in (
        [],
        outputs["sources"] + [{"content": "unknown", "metadata": {"document_id": "approved"}}],
    ):
        with pytest.raises(ValueError):
            validate_analysis_outputs(outputs | {"sources": sources}, data, policy)

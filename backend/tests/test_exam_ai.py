"""Exam grading accepts only structured claims tied to the frozen evidence set."""

import hashlib
import json
from uuid import uuid4

import pytest

from app.grading.exam_ai import validate_grade


def test_grade_rejects_fabricated_evidence_and_citation():
    event = uuid4()
    content = "SOC-001: อ่าน request และ response ก่อนตีความ"
    policy = {
        "document_ids": ["approved"],
        "chunk_hashes": [hashlib.sha256(content.encode()).hexdigest()],
    }
    source = {"metadata": {"document_id": "approved"}, "content": content}
    answer = {
        "analysis_score": 2,
        "reasoning_score": 1,
        "analysis_feedback": "เชื่อมข้อมูลกับเหตุการณ์ SOC-001",
        "reasoning_feedback": "ยังอธิบายข้อจำกัดได้บางส่วน",
        "evidence_refs": [str(event)],
        "section_ids": ["SOC-001"],
    }
    outputs = {"answer": json.dumps(answer), "sources": [source]}
    assert validate_grade(outputs, {event}, policy).analysis_score == 2
    with pytest.raises(ValueError):
        validate_grade(
            outputs | {"answer": json.dumps(answer | {"evidence_refs": [str(uuid4())]})},
            {event},
            policy,
        )
    with pytest.raises(ValueError):
        validate_grade(
            outputs | {"answer": json.dumps(answer | {"section_ids": ["SOC-403"]})}, {event}, policy
        )
    with pytest.raises(ValueError):
        validate_grade(
            outputs | {"answer": json.dumps(answer | {"analysis_score": 3})}, {event}, policy
        )
    with pytest.raises(ValueError):
        validate_grade(
            outputs | {"answer": json.dumps(answer | {"extra": "private truth"})}, {event}, policy
        )

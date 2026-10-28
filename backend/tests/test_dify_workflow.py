import asyncio
import hashlib
from pathlib import Path

import pytest
import requests

from app.knowledge.dify_client import DifyConfig, DifyUnavailable
from app.knowledge.dify_workflow import parse_workflow, run_workflow
from app.tutor.service import NO_MATCH_ANSWER, NoKnowledgeMatch, redact_question, validate_outputs


def test_tutor_redacts_common_secrets_before_storage_and_dispatch():
    raw = "app-" + "x" * 24
    sanitized = redact_question(f"{raw} Bearer abc.def password=private a@example.test")
    assert raw not in sanitized and "abc.def" not in sanitized
    assert "private" not in sanitized and "a@example.test" not in sanitized


def outputs():
    return {
        "answer": "403 ยังไม่ยืนยันข้อมูลรั่ว อ้าง SOC-003",
        "sources": [
            {
                "title": "คู่มือ SOC",
                "content": "## SOC-003 — HTTP response\n403 คือการปฏิเสธคำขอ",
                "metadata": {"document_id": "approved-document"},
            }
        ],
    }


def hashes():
    return [hashlib.sha256(outputs()["sources"][0]["content"].encode()).hexdigest()]


def test_structural_citations_require_actual_sources_and_approved_document():
    result = validate_outputs(outputs(), ["approved-document"], hashes())
    assert result.sources[0].section_ids == ["SOC-003"]
    for invalid in (
        {"answer": "SOC-003"},
        outputs() | {"sources": []},
        outputs() | {"answer": "อ้าง SOC-403"},
        outputs() | {"answer": "SOC-003 https://invented.invalid"},
        outputs() | {"answer": "ไม่มีหัวข้อที่อ้างจริง"},
    ):
        with pytest.raises(ValueError):
            validate_outputs(invalid, ["approved-document"], hashes())
    with pytest.raises(ValueError, match="Unauthorized"):
        validate_outputs(outputs(), ["different-document"], hashes())
    with pytest.raises(ValueError, match="immutable"):
        validate_outputs(outputs(), ["approved-document"], ["changed-content"])


def test_reasoning_is_removed_before_citation_checks_and_result_storage():
    payload = outputs()
    payload["answer"] = (
        "<think>Internal text SOC-999 https://hidden.invalid</think>" + payload["answer"]
    )
    result = validate_outputs(payload, ["approved-document"], hashes())
    assert result.answer == outputs()["answer"]
    assert "Internal" not in result.model_dump_json()


@pytest.mark.parametrize("hyphen", ["\u2010", "\u2011"])
def test_typographic_citation_hyphens_do_not_change_source_hashes(hyphen):
    result = validate_outputs(
        outputs() | {"answer": f"อ้าง SOC{hyphen}003"}, ["approved-document"], hashes()
    )
    assert result.answer == "อ้าง SOC-003"
    assert result.sources[0].excerpt == outputs()["sources"][0]["content"]
    with pytest.raises(ValueError):
        validate_outputs(
            outputs() | {"answer": f"อ้าง SOC{hyphen}999"}, ["approved-document"], hashes()
        )


def test_no_match_accepts_only_the_fixed_retrieval_branch_not_an_uncited_answer():
    with pytest.raises(NoKnowledgeMatch):
        validate_outputs({"answer": NO_MATCH_ANSWER, "sources": []}, [], [])
    with pytest.raises(ValueError, match="Retrieval sources required"):
        validate_outputs({"answer": "คำตอบที่แต่งขึ้น", "sources": []}, [], [])


@pytest.mark.parametrize(
    "answer",
    [
        "<think>unfinished SOC-003",
        "<think>only reasoning SOC-003</think>",
        "<think>nested <think>x</think>SOC-003",
        "SOC-003 <think>embedded</think>",
        "<THINK>unexpected case</THINK>SOC-003",
        "<think>hidden SOC-003</think>ไม่มีแหล่งอ้างอิงในคำตอบ",
    ],
)
def test_reasoning_never_supplies_citations_or_leaks_on_malformed_output(answer):
    with pytest.raises(ValueError):
        validate_outputs(outputs() | {"answer": answer}, ["approved-document"], hashes())


@pytest.mark.parametrize("actual", [None, "different-version"])
def test_workflow_version_mismatch_fails_closed(actual):
    body = {
        "data": {"workflow_id": actual, "status": "succeeded", "id": "run", "outputs": outputs()}
    }
    with pytest.raises(DifyUnavailable, match="DIFY_WORKFLOW_VERSION_MISMATCH"):
        parse_workflow(body, expected_workflow_id="version-123")


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"status": "failed"},
        {"status": "succeeded", "outputs": {}, "id": "run", "total_tokens": True},
    ],
)
def test_workflow_rejects_invalid_or_failed_envelope(data):
    with pytest.raises(DifyUnavailable):
        parse_workflow({"data": data})


def test_published_workflow_checks_approved_version_and_keeps_secret_server_side(
    tmp_path: Path, monkeypatch
):
    secret = tmp_path / "key"
    secret.write_text("test-key-not-real", encoding="utf8")
    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {
                "data": {
                    "workflow_id": "version-123",
                    "status": "succeeded",
                    "id": "run",
                    "outputs": outputs(),
                }
            }

    def post(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return Response()

    monkeypatch.setattr(requests, "post", post)
    result = asyncio.run(
        run_workflow(
            DifyConfig("https://dify.example.test/v1", secret),
            "version-123",
            "403 คืออะไร",
            "anonymous-question-123",
        )
    )
    assert captured["url"] == "https://dify.example.test/v1/workflows/run"
    assert captured["json"]["inputs"] == {"question": "403 คืออะไร"}
    assert captured["allow_redirects"] is False
    assert result.total_tokens is None
    assert "test-key-not-real" not in repr(result)


@pytest.mark.parametrize("exception", [requests.Timeout, requests.ConnectionError])
def test_workflow_never_retries_unknown_dispatch(tmp_path: Path, monkeypatch, exception):
    secret = tmp_path / "key"
    secret.write_text("test-key-not-real", encoding="utf8")
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        raise exception()

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(DifyUnavailable):
        asyncio.run(
            run_workflow(
                DifyConfig("https://dify.example.test/v1", secret),
                "version",
                "question",
                "question-id",
            )
        )
    assert len(calls) == 1


def test_provider_rejection_never_retries_another_endpoint(tmp_path, monkeypatch):
    secret = tmp_path / "key"
    secret.write_text("test-key-not-real", encoding="utf8")
    calls = []

    class Response:
        status_code = 403

        def json(self):
            return {"code": "workflow_version_execution_not_allowed"}

    def post(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(DifyUnavailable, match="DIFY_PINNED_VERSION_UNAVAILABLE"):
        asyncio.run(
            run_workflow(
                DifyConfig("https://dify.example.test/v1", secret), "version", "403", "test"
            )
        )
    assert calls == ["https://dify.example.test/v1/workflows/run"]

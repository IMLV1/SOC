import asyncio
import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
import requests
import yaml

from app.analysis.dify_provider import (
    CONTRACT_VERSION,
    MAX_RESPONSE_BYTES,
    DifyAnalysisFailure,
    analyze,
    parse_analysis,
    request_inputs,
)
from app.analysis.provider import AnalysisInput, MockProvider
from app.knowledge.dify_client import DifyConfig, DifyUnavailable


@pytest.fixture
def evidence():
    return AnalysisInput.model_validate(
        {
            "analysis_id": uuid4(),
            "evidence": [
                {
                    "id": uuid4(),
                    "source": "web",
                    "username": "private-person",
                    "request": {"headers": {"Authorization": "Bearer private-value"}},
                    "response": {"status": 403},
                    "log": {"event_type": "request_policy_denied"},
                }
            ],
            "prompt_version": "triage-v1",
            "max_output_tokens": 2048,
        }
    )


@pytest.fixture
def reply(evidence):
    # Synthetic output is a parser fixture, never a claim of live AI quality.
    result = asyncio.run(MockProvider().analyze(evidence)).result.model_dump(mode="json")
    return {
        "data": {
            "workflow_id": "approved-investigation-version",
            "status": "succeeded",
            "id": "provider-run-id",
            "total_tokens": 42,
            "outputs": {"analysis": json.dumps(result), "contract_version": CONTRACT_VERSION},
        }
    }


def test_request_is_bounded_redacted_and_contains_only_snapshot(evidence):
    evidence.evidence[0].log["message"] = (
        "a@example.test password=secret-value Bearer secret-token app-" + "x" * 24
    )
    inputs = request_inputs(evidence)
    assert set(inputs) == {"analysis_input"}
    text = inputs["analysis_input"]
    for secret in [
        "private-person",
        "private-value",
        "a@example.test",
        "secret-value",
        "secret-token",
        "app-" + "x" * 24,
    ]:
        assert secret not in text
    body = json.loads(text)
    assert body["evidence"][0]["id"] == str(evidence.evidence[0].id)
    assert body["response_schema"]["additionalProperties"] is False
    assert body["contract_version"] == CONTRACT_VERSION


def test_oversized_snapshot_is_rejected_without_truncating(evidence):
    evidence.evidence[0].log["message"] = "ก" * 32000
    with pytest.raises(DifyAnalysisFailure, match="INPUT_TOO_LARGE"):
        request_inputs(evidence)


def test_duplicate_snapshot_ids_are_rejected(evidence):
    evidence.evidence.append(evidence.evidence[0])
    with pytest.raises(DifyAnalysisFailure, match="INPUT_INVALID"):
        request_inputs(evidence)


def test_snapshot_must_use_the_reviewed_draft_output_ceiling(evidence):
    evidence.max_output_tokens = 1024
    with pytest.raises(DifyAnalysisFailure, match="INPUT_INVALID"):
        request_inputs(evidence)


def test_exact_contract_parses_usage_without_inventing_token_split(reply, evidence):
    parsed = parse_analysis(reply, "approved-investigation-version", {evidence.evidence[0].id})
    assert parsed.total_tokens == 42
    assert parsed.result.evidence_refs == [evidence.evidence[0].id]
    assert parsed.run_id == "provider-run-id"
    del reply["data"]["total_tokens"]
    assert (
        parse_analysis(
            reply, "approved-investigation-version", {evidence.evidence[0].id}
        ).total_tokens
        is None
    )


@pytest.mark.parametrize(
    "field", ["evidence_refs", "hypothesis", "knowledge_refs", "unknown_field", "reasoning"]
)
def test_invalid_analysis_is_never_returned_as_free_text(reply, evidence, field):
    result = json.loads(reply["data"]["outputs"]["analysis"])
    if field == "hypothesis":
        result["hypotheses"][0]["evidence_refs"] = [str(uuid4())]
    elif field == "unknown_field":
        result["passed"] = True
    elif field == "reasoning":
        result["summary"] = "<think>private reasoning</think>"
    else:
        result[field] = [str(uuid4())]
    reply["data"]["outputs"]["analysis"] = result
    with pytest.raises(DifyAnalysisFailure, match="OUTPUT_INVALID") as error:
        parse_analysis(reply, "approved-investigation-version", {evidence.evidence[0].id})
    assert error.value.total_tokens == 42


@pytest.mark.parametrize("bad", ["markdown ```json {} ```", {"summary": "raw text"}, None])
def test_malformed_result_never_falls_back_to_text(reply, evidence, bad):
    reply["data"]["outputs"]["analysis"] = bad
    with pytest.raises(DifyAnalysisFailure):
        parse_analysis(reply, "approved-investigation-version", {evidence.evidence[0].id})


def test_tutor_outputs_and_other_workflow_are_rejected(reply, evidence):
    other = copy.deepcopy(reply)
    other["data"]["workflow_id"] = "lesson-tutor"
    with pytest.raises(DifyUnavailable, match="VERSION_MISMATCH"):
        parse_analysis(other, "approved-investigation-version", {evidence.evidence[0].id})
    reply["data"]["outputs"] = {"answer": "Tutor answer", "sources": []}
    with pytest.raises(DifyAnalysisFailure, match="OUTPUT_INVALID"):
        parse_analysis(reply, "approved-investigation-version", {evidence.evidence[0].id})


def transport(tmp_path, monkeypatch, reply, *, status=200, exception=None, raw=None):
    key = tmp_path / "investigation-key"
    key.write_text("synthetic-test-key", encoding="utf8")
    calls = []

    class Response:
        status_code = status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_content(self, size):
            yield raw if raw is not None else json.dumps(reply).encode()

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if exception:
            raise exception("sensitive transport details must not leak")
        return Response()

    monkeypatch.setattr(requests, "post", post)
    return DifyConfig("https://dify.example.test/v1", key), calls


def test_one_request_no_redirect_and_only_opaque_id_sent(tmp_path, monkeypatch, reply, evidence):
    config, calls = transport(tmp_path, monkeypatch, reply)
    result = asyncio.run(analyze(config, "approved-investigation-version", evidence))
    assert result.total_tokens == 42
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://dify.example.test/v1/workflows/run"
    assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
    assert kwargs["json"]["user"] == f"analysis-{evidence.analysis_id}"
    assert kwargs["json"]["response_mode"] == "blocking"
    assert "synthetic-test-key" not in repr(result)


@pytest.mark.parametrize("exception", [requests.Timeout, requests.ConnectionError])
def test_unknown_network_outcome_never_retries(tmp_path, monkeypatch, reply, evidence, exception):
    config, calls = transport(tmp_path, monkeypatch, reply, exception=exception)
    with pytest.raises(DifyAnalysisFailure) as error:
        asyncio.run(analyze(config, "approved-investigation-version", evidence))
    assert len(calls) == 1
    assert error.value.total_tokens is None
    assert "sensitive" not in str(error.value)


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_http_errors_do_not_retry_or_assume_zero_usage(
    tmp_path, monkeypatch, reply, evidence, status
):
    config, calls = transport(tmp_path, monkeypatch, reply, status=status)
    with pytest.raises(DifyAnalysisFailure) as error:
        asyncio.run(analyze(config, "approved-investigation-version", evidence))
    assert len(calls) == 1 and error.value.total_tokens is None


@pytest.mark.parametrize("raw", [b"not-json", b"x" * (MAX_RESPONSE_BYTES + 1)])
def test_invalid_or_oversized_provider_body_is_safe(tmp_path, monkeypatch, reply, evidence, raw):
    config, calls = transport(tmp_path, monkeypatch, reply, raw=raw)
    with pytest.raises(DifyAnalysisFailure):
        asyncio.run(analyze(config, "approved-investigation-version", evidence))
    assert len(calls) == 1


def test_draft_workflow_has_no_retrieval_tools_secrets_or_automatic_retry():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / "knowledge/dify/SOC-investigation-draft.yml").read_text())
    assert workflow["app"]["mode"] == "workflow"
    assert "DRAFT" in workflow["app"]["name"]
    assert workflow["workflow"]["environment_variables"] == []
    nodes = workflow["workflow"]["graph"]["nodes"]
    assert sorted(node["data"]["type"] for node in nodes) == [
        "end",
        "llm",
        "start",
        "template-transform",
    ]
    llm = next(node["data"] for node in nodes if node["data"]["type"] == "llm")
    assert llm["retry_config"]["retry_enabled"] is False
    assert llm["context"]["enabled"] is False
    end = next(node["data"] for node in nodes if node["data"]["type"] == "end")
    assert {item["variable"] for item in end["outputs"]} == {"analysis", "contract_version"}

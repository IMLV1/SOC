"""Blocking Workflow transport only. No retries, tools, scoring or dispatch admission."""

import asyncio
from dataclasses import dataclass
from typing import Any

import requests

from app.knowledge.dify_client import DifyConfig, DifyUnavailable


@dataclass(frozen=True)
class WorkflowReply:
    outputs: dict[str, Any]
    total_tokens: int | None
    run_id: str


def parse_workflow(
    body: Any, *, expected_workflow_id: str | None = None, expected_mode: str | None = None
) -> WorkflowReply:
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise DifyUnavailable("DIFY_INVALID_RESPONSE")
    data = body["data"]
    if expected_workflow_id is not None and data.get("workflow_id") != expected_workflow_id:
        raise DifyUnavailable("DIFY_WORKFLOW_VERSION_MISMATCH")
    if data.get("status") != "succeeded":
        raise DifyUnavailable("DIFY_WORKFLOW_FAILED")
    if not isinstance(data.get("outputs"), dict) or not isinstance(data.get("id"), str):
        raise DifyUnavailable("DIFY_INVALID_RESPONSE")
    tokens = data.get("total_tokens")
    if tokens is not None and (type(tokens) is not int or tokens < 0):
        raise DifyUnavailable("DIFY_INVALID_RESPONSE")
    outputs = data["outputs"]
    if expected_mode is not None:
        if outputs.get("mode") != expected_mode:
            raise DifyUnavailable("DIFY_MODE_MISMATCH")
        if set(outputs) != {"mode", "answer", "sources"}:
            raise DifyUnavailable("DIFY_INVALID_RESPONSE")
        outputs = {"answer": outputs["answer"], "sources": outputs["sources"]}
    return WorkflowReply(outputs, tokens, data["id"])


def _request(
    config: DifyConfig, workflow_id: str, question: str, user: str, mode: str | None = None
) -> WorkflowReply:
    key = config.read_api_key()
    try:
        response = requests.post(
            # Free Cloud runs the published release. The response must still echo
            # the approved version; this detects drift after, not before, dispatch.
            f"{config.base_url}/workflows/run",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "inputs": {"question": question} | ({"mode": mode} if mode else {}),
                "response_mode": "blocking",
                "user": user,
            },
            timeout=(3.0, config.timeout_seconds),
            allow_redirects=False,
        )
    except requests.Timeout:
        raise DifyUnavailable("DIFY_TIMEOUT") from None
    except requests.RequestException:
        raise DifyUnavailable("DIFY_REQUEST_FAILED") from None
    if response.status_code == 403:
        try:
            error = response.json()
        except ValueError:
            error = None
        if (
            isinstance(error, dict)
            and error.get("code") == "workflow_version_execution_not_allowed"
        ):
            # Do not silently execute the mutable latest version or retry another endpoint.
            raise DifyUnavailable("DIFY_PINNED_VERSION_UNAVAILABLE")
    if not 200 <= response.status_code < 300:
        raise DifyUnavailable("DIFY_REQUEST_FAILED")
    try:
        return parse_workflow(response.json(), expected_workflow_id=workflow_id, expected_mode=mode)
    except ValueError:
        raise DifyUnavailable("DIFY_INVALID_RESPONSE") from None


async def run_workflow(
    config: DifyConfig, workflow_id: str, question: str, user: str, mode: str | None = None
) -> WorkflowReply:
    if not workflow_id or len(workflow_id) > 128:
        raise DifyUnavailable("DIFY_WORKFLOW_INVALID")
    if (
        not question.strip()
        or len(question) > (24000 if mode == "grade" else 2000)
        or not user
        or len(user) > 128
    ):
        raise DifyUnavailable("DIFY_QUERY_INVALID")
    if mode not in (None, "tutor", "grade"):
        raise DifyUnavailable("DIFY_QUERY_INVALID")
    return await asyncio.to_thread(_request, config, workflow_id, question, user, mode)

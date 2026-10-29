"""Client boundary regressions; no database or external provider is used."""

import asyncio
import json
import re
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.analysis.models import QuestionInput, RetryInput
from app.auth.google_routes import GoogleStartInput
from app.auth.models import LoginInput, RegisterInput, Strict
from app.evaluation.routes import CommentInput
from app.exams.models import ReviewInput, StartAttemptInput, SubmitInput
from app.input_validation import InputModel
from app.investigation.models import (
    DeleteInput,
    InstructorTicketPatch,
    NoteCreate,
    NotePatch,
    TicketCreate,
    TicketPatch,
)
from app.learning.models import ProgressInput
from app.learning.practice_models import (
    DraftInput,
    PracticeAnswer,
    PracticeDraft,
    WrittenAnswer,
    WrittenInput,
)
from app.main import app
from app.request_limits import MAX_API_BODY_BYTES, ApiBodyLimit
from app.runs.models import VersionInput
from app.scenarios.models import TrainingSelection
from app.tutor.models import TutorInput

IDENTITY = "15000000-0000-4000-8000-000000000001"
ANSWER = {
    "expected_version": 1,
    "evidence_event_ids": [IDENTITY],
    "severity": "medium",
    "disposition": "undetermined",
    "reason": "ตรวจตามหลักฐาน",
}
# Valid client JSON for every request model family, including nested inputs.
INPUTS = [
    (Strict, {}),  # Logout accepts an empty, closed JSON object only.
    (LoginInput, {"email": "user@example.test", "password": "a secret"}),
    (
        RegisterInput,
        {"email": "user@example.test", "password": "a secret", "display_name": "Learner"},
    ),
    (GoogleStartInput, {"purpose": "login"}),
    (TrainingSelection, {"scenario_ids": [IDENTITY], "seed": 0}),
    (VersionInput, {"expected_version": 1}),
    (
        TicketCreate,
        {"title": "Ticket", "severity": "medium", "evidence_ids": [IDENTITY], "reason": "ตรวจสอบ"},
    ),
    (TicketPatch, {"expected_version": 1, "reason": "ตรวจสอบ"}),
    (InstructorTicketPatch, {"expected_version": 1, "reason": "ตรวจสอบ"}),
    (DeleteInput, {"expected_version": 1, "reason": "ตรวจสอบ"}),
    (NoteCreate, {"body": "บันทึก"}),
    (NotePatch, {"body": "บันทึก", "expected_version": 1, "reason": "แก้ไข"}),
    (QuestionInput, {"question": "HTTP 403 หมายถึงอะไร", "expected_version": 1}),
    (RetryInput, {"expected_version": 1}),
    (CommentInput, {"body": "คำแนะนำ"}),
    (TutorInput, {"lesson_id": IDENTITY, "question": "HTTP 403 หมายถึงอะไร"}),
    (ProgressInput, {"expected_version": 0}),
    (StartAttemptInput, {"expected_progress_version": 1}),
    (SubmitInput, ANSWER),
    (
        ReviewInput,
        {"expected_version": 1, "criterion_scores": {"analysis": None}, "reason": "ทบทวน"},
    ),
    (
        PracticeAnswer,
        {
            "evidence_ids": [IDENTITY],
            "severity": "medium",
            "disposition": "undetermined",
            "reason": "ตรวจสอบ",
        },
    ),
    (PracticeDraft, {"reason": ""}),
    (DraftInput, {"expected_version": 0, "answer": {"reason": ""}}),
    (WrittenAnswer, {"question_id": IDENTITY, "answer": "คำตอบ"}),
    (
        WrittenInput,
        {"answers": [{"question_id": str(UUID(int=i)), "answer": "คำตอบ"} for i in range(10)]},
    ),
]


@pytest.mark.parametrize("model,payload", INPUTS, ids=[model.__name__ for model, _ in INPUTS])
def test_valid_client_json_and_unknown_fields(model, payload):
    model.model_validate_json(json.dumps(payload))
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(payload | {"owner_user_id": IDENTITY}))


def test_all_http_body_models_have_input_boundary_validation():
    assert HTTP_INPUTS, "The mutation route inventory must not be empty"
    for _, path, model in HTTP_INPUTS:
        assert model in {candidate for candidate, _ in INPUTS}, (path, model)
        if model.model_fields:
            assert issubclass(model, InputModel), (path, model)
        else:
            assert model.model_config["extra"] == "forbid"
    assert "/api/v1/tutor/questions" in {path for _, path, _ in HTTP_INPUTS}
    assert "/api/v1/exam/attempts/{attempt_id}/submit" in {path for _, path, _ in HTTP_INPUTS}


@pytest.mark.parametrize("invalid", [True, False, "1", 1.0, -1, None])
def test_versions_and_seed_reject_wrong_types_and_negative_values(invalid):
    for model, payload in INPUTS:
        for name in ("expected_version", "expected_progress_version", "seed"):
            if name in payload and not (name == "seed" and invalid is None):
                with pytest.raises(ValidationError):
                    model.model_validate(payload | {name: invalid})


@pytest.mark.parametrize("text", ["", " ", "\t\r\n", "\u2003"])
def test_required_human_text_cannot_be_blank(text):
    for model, payload in INPUTS:
        if model is PracticeDraft:
            continue  # Empty unsent drafts are intentionally allowed.
        for name in ("display_name", "title", "reason", "question", "body", "answer"):
            if isinstance(payload.get(name), str):
                with pytest.raises(ValidationError):
                    model.model_validate(payload | {name: text})


@pytest.mark.parametrize("model,payload", INPUTS, ids=[model.__name__ for model, _ in INPUTS])
def test_null_characters_are_rejected_before_persistence(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload | {"untrusted\x00": "value"})
    for name, value in payload.items():
        if isinstance(value, str):
            with pytest.raises(ValidationError):
                model.model_validate(payload | {name: value + "\x00"})


@pytest.mark.parametrize("text", ["bad\ud800text", "bad\udffftext"])
def test_invalid_unicode_is_rejected_including_nested_drafts(text):
    with pytest.raises(ValidationError):
        SubmitInput.model_validate(ANSWER | {"reason": text})
    with pytest.raises(ValidationError):
        DraftInput.model_validate({"expected_version": 0, "answer": {"reason": text}})


def test_deep_json_is_rejected_without_recursion_error():
    value = {}
    for _ in range(70):
        value = {"nested": value}
    with pytest.raises(ValidationError):
        PracticeDraft.model_validate(value)


def test_empty_draft_password_spaces_and_literal_markup_remain_valid():
    assert PracticeDraft.model_validate({"reason": ""}).reason == ""
    assert (
        LoginInput.model_validate(
            {"email": "  USER@example.test ", "password": "  secret  "}
        ).password
        == "  secret  "
    )
    text = "<script>alert(1)</script> SELECT * FROM users;"
    assert NoteCreate.model_validate({"body": text}).body == text
    assert SubmitInput.model_validate(ANSWER | {"reason": "  ตามหลักฐาน  "}).reason == "ตามหลักฐาน"


@pytest.mark.parametrize("name", ["reason", "question", "body", "answer", "display_name", "title"])
def test_text_length_boundaries(name):
    maximum = {"display_name": 60, "title": 120}.get(name, 2000)
    checked = 0
    for model, payload in INPUTS:
        if isinstance(payload.get(name), str):
            model.model_validate(payload | {name: "ก" * maximum})
            with pytest.raises(ValidationError):
                model.model_validate(payload | {name: "ก" * (maximum + 1)})
            checked += 1
    assert checked


def test_exam_evidence_requires_unique_uuids_and_bounded_count():
    for ids in ([], [IDENTITY, IDENTITY], ["invalid"], [str(UUID(int=i)) for i in range(51)]):
        with pytest.raises(ValidationError):
            SubmitInput.model_validate(ANSWER | {"evidence_event_ids": ids})


async def run_body_limit(chunks, headers=(), query=b"", path="/api/v1/auth/login"):
    calls = {"app": 0, "receive": 0}
    messages = iter(chunks)
    sent = []

    async def receive():
        calls["receive"] += 1
        return next(messages)

    async def send(message):
        sent.append(message)

    async def downstream(scope, receive, send):
        calls["app"] += 1
        body = await receive()
        assert body["type"] == "http.request"
        assert not body.get("more_body", False)
        calls["size"] = len(body["body"])

    await ApiBodyLimit(downstream)(
        {"type": "http", "path": path, "headers": headers, "query_string": query}, receive, send
    )
    return calls, sent


@pytest.mark.parametrize("size", [0, MAX_API_BODY_BYTES - 1, MAX_API_BODY_BYTES])
def test_body_limit_accepts_valid_sizes_and_replays_split_body(size):
    calls, sent = asyncio.run(
        run_body_limit(
            [
                {"type": "http.request", "body": b"a" * (size // 2), "more_body": True},
                {"type": "http.request", "body": b"b" * (size - size // 2)},
            ],
            [(b"content-length", str(size).encode())],
        )
    )
    assert calls["app"] == 1 and calls["size"] == size
    assert not sent


@pytest.mark.parametrize("declared", [None, b"1"])
def test_chunked_and_false_content_length_cannot_bypass_limit(declared):
    calls, sent = asyncio.run(
        run_body_limit(
            [
                {"type": "http.request", "body": b"a" * MAX_API_BODY_BYTES, "more_body": True},
                {"type": "http.request", "body": b"b"},
            ],
            [] if declared is None else [(b"content-length", declared)],
        )
    )
    assert calls["app"] == 0
    assert sent[0]["status"] == 413
    body = json.loads(sent[1]["body"])
    assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.parametrize(
    "length,status", [(b"-1", 400), (b"bad", 400), (b"1" * 5000, 413), (b"1048577", 413)]
)
def test_bad_or_oversized_declared_length_is_rejected_without_reading(length, status):
    calls, sent = asyncio.run(run_body_limit([], [(b"content-length", length)]))
    assert calls == {"app": 0, "receive": 0}
    assert sent[0]["status"] == status


def test_disconnected_client_does_not_dispatch_partial_body():
    calls, sent = asyncio.run(run_body_limit([{"type": "http.disconnect"}]))
    assert calls["app"] == 0 and not sent


@pytest.mark.parametrize(
    "headers", [[(b"content-length", b"1"), (b"content-length", b"1")], [(b"content-length", b"2")]]
)
def test_ambiguous_or_mismatched_content_length_is_rejected(headers):
    calls, sent = asyncio.run(run_body_limit([{"type": "http.request", "body": b"a"}], headers))
    assert calls["app"] == 0 and sent[0]["status"] == 400


@pytest.fixture
def offline_api(monkeypatch):
    from app.auth import service, supabase_provider

    def no_database(*args, **kwargs):
        raise AssertionError("Invalid input must not access the database")

    monkeypatch.setattr(service, "database", no_database)
    monkeypatch.setattr(supabase_provider, "enabled", lambda: False)
    monkeypatch.setenv("AUTH_ORIGINS", "http://testserver")
    monkeypatch.delenv("SOC_PREVIEW_MODE", raising=False)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "path,payload",
    [
        (f"/api/v1/exam/attempts/{IDENTITY}/submit", ANSWER | {"reason": "   "}),
        (
            f"/api/v1/exam/attempts/{IDENTITY}/submit",
            ANSWER | {"evidence_event_ids": [IDENTITY, IDENTITY]},
        ),
        (f"/api/v1/learning/levels/{IDENTITY}/attempts", {"expected_progress_version": True}),
        (f"/api/v1/lessons/{IDENTITY}/complete", {"expected_version": "1"}),
        (
            f"/api/v1/runs/{IDENTITY}/tickets",
            {"title": "\x00", "severity": "medium", "evidence_ids": [IDENTITY], "reason": "reason"},
        ),
        ("/api/v1/tutor/questions", {"lesson_id": IDENTITY, "question": " \t "}),
        (
            "/api/v1/auth/register",
            {"email": "invalid", "password": "dont-reflect", "display_name": "User"},
        ),
        (
            "/api/v1/auth/login",
            {"email": "user@example.test", "password": "dont-reflect", "role": "instructor"},
        ),
    ],
)
def test_invalid_http_json_returns_safe_422_without_database(offline_api, path, payload):
    response = offline_api.post(path, json=payload, headers={"Origin": "http://testserver"})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "dont-reflect" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_http_oversize_and_malformed_json_are_safe_before_auth(offline_api):
    response = offline_api.post("/api/v1/auth/login", content=b"x" * (MAX_API_BODY_BYTES + 1))
    assert response.status_code == 413
    assert response.json()["meta"]["request_id"] == response.headers["x-request-id"]
    response = offline_api.post(
        "/api/v1/auth/login",
        content='{"password":"dont-reflect",',
        headers={"Origin": "http://testserver", "Content-Type": "application/json"},
    )
    assert response.status_code == 400 and "dont-reflect" not in response.text


def test_null_query_and_path_are_rejected_before_database(offline_api):
    for path in (f"/api/v1/runs/{IDENTITY}/events?q=%00", "/api/v1/runs/%00"):
        assert offline_api.get(path).status_code == 422


@pytest.mark.parametrize(
    "suffix,status",
    [
        ("/runs?limit=0", 422),
        ("/runs?limit=101", 422),
        ("/runs?limit=true", 422),
        ("/runs?status=untrusted", 422),
        ("/runs/not-a-uuid", 422),
        (f"/runs/{IDENTITY}/events?after_seq=-1", 422),
        (f"/runs/{IDENTITY}/events?q=" + "a" * 201, 422),
        (f"/runs/{IDENTITY}/events?src_ip=999.999.999.999", 422),
        (f"/runs/{IDENTITY}/events?from=2026-10-29T00:00:00", 422),
        (f"/runs/{IDENTITY}/events?from=2026-10-30T00:00:00Z&to=2026-10-29T00:00:00Z", 422),
        (f"/runs/{IDENTITY}/events?cursor=bad&after_seq=0", 400),
        (f"/runs/{IDENTITY}/events?cursor=invalid", 400),
    ],
)
def test_invalid_filters_and_pagination_do_not_reach_database(offline_api, suffix, status):
    response = offline_api.get("/api/v1" + suffix)
    assert response.status_code == status, response.text


def api_routes(router):
    # FastAPI 0.143 defers included routers. OpenAPI omits working routes marked
    # include_in_schema=False, so inspect their original router as well.
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from api_routes(route.original_router)


HTTP_INPUTS = [
    (sorted(route.methods)[0], route.path, field.field_info.annotation)
    for route in api_routes(app.router)
    for field in route.dependant.body_params
]


@pytest.mark.parametrize(
    "method,path,model",
    HTTP_INPUTS,
    ids=[f"{method} {path}" for method, path, _ in HTTP_INPUTS],
)
def test_every_mutation_rejects_extra_owner_field_before_persistence(
    offline_api, method, path, model
):
    payload = next(payload for candidate, payload in INPUTS if candidate is model)
    path = re.sub(r"\{[^}]+\}", IDENTITY, path)
    response = offline_api.request(
        method,
        path,
        json=payload | {"owner_user_id": IDENTITY},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 422, (path, response.text)
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

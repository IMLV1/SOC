import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = yaml.safe_load((ROOT / "docs/openapi.yaml").read_text(encoding="utf-8"))


def test_health_does_not_claim_database_readiness() -> None:
    with TestClient(app) as client:
        live = client.get("/health/live", headers={"X-Request-ID": "untrusted-secret"})
        ready = client.get("/health/ready")
    assert live.status_code == 200
    assert live.json()["data"] == {"status": "alive"}
    assert live.headers["x-request-id"] == live.json()["meta"]["request_id"]
    assert "untrusted-secret" not in live.text
    assert ready.status_code == 503
    assert ready.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert ready.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", ["/api/v1/runs", "/api/v1/attempts/example/submit"])
def test_draft_routes_are_not_exposed(path: str) -> None:
    with TestClient(app) as client:
        response = client.post(path, json={"password": "do-not-reflect"})
    assert response.status_code == 404
    assert set(response.json()) == {"error", "meta"}
    assert "do-not-reflect" not in response.text


def test_health_disallows_mutation() -> None:
    with TestClient(app) as client:
        response = client.post("/health/live")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_worker_check_and_unimplemented_service_exit() -> None:
    for args, exit_code in [(["--check"], 0), ([], 2)]:
        result = subprocess.run(
            [sys.executable, "-m", "app.worker", *args],
            cwd=ROOT / "backend",
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == exit_code
        assert json.loads(result.stdout)["queue_ready"] is False


def test_openapi_valid_and_approved_contract_has_no_drift() -> None:
    validate(CONTRACT)
    actual = app.openapi()
    approved = {}
    for path, methods in CONTRACT["paths"].items():
        for method, operation in methods.items():
            if operation["x-contract-status"] == "approved":
                approved.setdefault(path, {})[method] = {
                    key: value
                    for key, value in operation.items()
                    if not key.startswith("x-") and key != "security"
                }
    # New routes fail until explicitly approved; comparison includes full response schemas.
    assert actual["paths"] == approved
    for name, schema in actual["components"]["schemas"].items():
        assert CONTRACT["components"]["schemas"][name] == schema


def test_all_api_inventory_operations_are_mapped_and_draft() -> None:
    source = (ROOT / "docs/api.md").read_text(encoding="utf-8")
    srs = (ROOT / "docs/srs.md").read_text(encoding="utf-8")
    for method, path in re.findall(r"\| (GET|POST|PATCH|DELETE) \| `([^`]+)`", source):
        path = path.replace("T/", "/runs/{run_id}/tickets/{ticket_id}/")
        operation = CONTRACT["paths"]["/api/v1" + path][method.lower()]
        assert operation["x-contract-status"] == "draft"
        assert operation["x-requirements"]
        assert all(requirement in srs for requirement in operation["x-requirements"])


def resolve_schema(value: object) -> object:
    if isinstance(value, dict):
        if "$ref" in value:
            name = str(value["$ref"]).rsplit("/", 1)[1]
            return resolve_schema(CONTRACT["components"]["schemas"][name])
        return {key: resolve_schema(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_schema(item) for item in value]
    return value


@pytest.mark.parametrize(
    "name", ["ExamRunView", "ExamAttemptView", "ExamTicketView", "ExamAlertView"]
)
def test_exam_draft_schemas_are_closed_allowlists(name: str) -> None:
    schema = resolve_schema(CONTRACT["components"]["schemas"][name])
    assert isinstance(schema, dict)
    validator = Draft202012Validator(schema)
    for field in ["answer_key", "rubric", "initial_severity", "ai_brief", "ground_truth", "score"]:
        errors = list(validator.iter_errors({field: "must-never-leak"}))
        assert any(error.validator == "additionalProperties" for error in errors)


def test_training_create_cannot_choose_exam_mode_or_owner() -> None:
    schema = resolve_schema(CONTRACT["components"]["schemas"]["TrainingRunCreate"])
    validator = Draft202012Validator(schema)
    payload = {"scenario_ids": ["5cda7831-66f2-407a-9dc2-e5f5e2953c8c"]}
    assert validator.is_valid(payload)
    for field in ["mode", "attempt_id", "owner_user_id", "passed"]:
        assert not validator.is_valid({**payload, field: "exam"})


def test_frontend_has_no_reference_assets_or_default_credentials() -> None:
    for path in (ROOT / "frontend/src").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "localStorage" not in text
            assert "prototype/" not in text
            assert "ground-truth" not in text
            assert "@demo.test" not in text
    assert "NEXT_PUBLIC_" not in (ROOT / "frontend/.env.example").read_text()

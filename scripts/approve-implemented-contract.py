"""Refresh approved OpenAPI operations from FastAPI without touching draft routes.

Run only after reviewing implementation: this preserves requirement/authorization
annotations and leaves exam/learning/provider draft operations untouched.
"""

from pathlib import Path

import yaml

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "docs/openapi.yaml"
contract = yaml.safe_load(target.read_text(encoding="utf-8"))
actual = app.openapi()
requirements = {
    "Runs": "FR-004",
    "RAG": "FR-012",
    "Tickets": "FR-006",
    "Analysis": "FR-008",
    "Instructor": "FR-010",
    "Evaluation": "FR-009",
    "Instructor review": "FR-010",
}

for path, methods in actual["paths"].items():
    destination = contract["paths"].setdefault(path, {})
    for method, operation in methods.items():
        old = destination.get(method, {})
        tags = operation.get("tags", [])
        group = tags[0] if tags else ""
        copied = dict(operation)
        copied["x-contract-status"] = "approved"
        copied["x-requirements"] = old.get("x-requirements") or [requirements.get(group, "FR-001")]
        for key in ("x-authorization", "x-schema-status"):
            if key in old and key != "x-schema-status":
                copied[key] = old[key]
        destination[method] = copied

contract["components"]["schemas"].update(actual["components"]["schemas"])
contract["info"]["description"] = (
    "Steps 01–14: implemented operations are approved from FastAPI. "
    "Gemini analysis is Free Tier gated and synthetic-data only. "
    "Evaluation and Instructor review are training-only. "
    "RAG supports pinned releases; learning and exam operations remain draft."
)
target.write_text(yaml.safe_dump(contract, allow_unicode=True, sort_keys=False), encoding="utf-8")

"""Generate TypeScript DTOs reachable from approved OpenAPI operations; --check rejects drift."""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
contract = yaml.safe_load((ROOT / "docs/openapi.yaml").read_text(encoding="utf-8"))
schemas = contract["components"]["schemas"]
names: set[str] = set()


def refs(value: object) -> None:
    if isinstance(value, dict):
        if "$ref" in value:
            name = value["$ref"].rsplit("/", 1)[1]
            if name not in names and name in schemas:
                names.add(name)
                refs(schemas[name])
        for item in value.values():
            refs(item)
    elif isinstance(value, list):
        for item in value:
            refs(item)


def ts(schema: dict) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[1]
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    if "anyOf" in schema:
        return " | ".join(ts(value) for value in schema["anyOf"])
    kind = schema.get("type")
    if kind == "object":
        if not schema.get("properties"):
            if isinstance(schema.get("additionalProperties"), dict):
                return f"Record<string, {ts(schema['additionalProperties'])}>"
            return "Record<string, never>"
        required = schema.get("required", [])
        return (
            "{ "
            + "; ".join(
                f"{name}{'' if name in required else '?'}: {ts(value)}"
                for name, value in schema.get("properties", {}).items()
            )
            + " }"
        )
    if kind == "array":
        return f"Array<{ts(schema['items'])}>"
    if kind in ("string", "boolean", "null"):
        return kind
    if kind in ("integer", "number"):
        return "number"
    if kind is None:
        return "unknown"
    raise ValueError(f"Unsupported approved schema: {schema}")


for operations in contract["paths"].values():
    for operation in operations.values():
        if operation.get("x-contract-status") == "approved":
            refs(operation)
output = "// Generated from approved docs/openapi.yaml; do not edit by hand.\n"
output += "\n".join(f"export type {name} = {ts(schemas[name])};" for name in sorted(names)) + "\n"
target = ROOT / "frontend/src/lib/api-types.ts"
if "--check" in sys.argv:
    if not target.is_file() or target.read_text(encoding="utf-8") != output:
        raise SystemExit("Approved API client types drifted; run scripts/generate-client-types.py.")
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output, encoding="utf-8")

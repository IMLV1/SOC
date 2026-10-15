"""Manifest allowlist and reproducible UTF-8 byte-budget chunking (not token estimates)."""

import hashlib
import json
from pathlib import Path
from typing import Any


def digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def chunks(body: str, budget: int = 1200, overlap: int = 160) -> list[dict[str, Any]]:
    if not 0 <= overlap < budget or budget < 4:
        raise ValueError("Invalid byte budget")
    result: list[dict[str, Any]] = []
    start = 0
    raw = body.encode("utf-8")
    while start < len(raw):
        end = min(len(raw), start + budget)
        while end < len(raw) and raw[end] & 0xC0 == 0x80:
            end -= 1
        excerpt = raw[start:end].decode("utf-8")
        headings = [
            line for line in raw[:start].decode("utf-8").splitlines() if line.startswith("#")
        ]
        result.append(
            dict(
                ordinal=len(result),
                body=excerpt,
                start_byte=start,
                end_byte=end,
                heading=headings[-1] if headings else "",
                content_hash=digest(excerpt),
            )
        )
        if end == len(raw):
            break
        start = max(start + 1, end - overlap)
        while start < len(raw) and raw[start] & 0xC0 == 0x80:
            start += 1
    return result


def load_manifest(path: Path) -> list[dict[str, Any]]:
    root = path.parent.resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if set(manifest) != {"documents"} or not manifest["documents"]:
        raise ValueError("Manifest documents required")
    if len(manifest["documents"]) > 20:
        raise ValueError("Manifest exceeds offline admission limit")
    documents = []
    total_bytes = 0
    seen = set()
    for entry in manifest["documents"]:
        if set(entry) != {
            "path",
            "stable_key",
            "revision",
            "title",
            "language",
            "reviewer",
            "license",
            "sha256",
        }:
            raise ValueError("Invalid manifest metadata")
        target = (root / entry["path"]).resolve()
        if not target.is_relative_to(root / "approved") or target.suffix != ".md":
            raise ValueError("Only approved Markdown allowed")
        if target.stat().st_size > 120_000:
            raise ValueError("Document exceeds offline byte budget")
        body = target.read_text(encoding="utf-8")
        total_bytes += len(body.encode("utf-8"))
        if total_bytes > 1_000_000:
            raise ValueError("Corpus exceeds offline ingestion budget")
        if not all(isinstance(v, str) and v.strip() for v in entry.values()):
            raise ValueError("Missing approval metadata")
        identity = (entry["stable_key"], entry["revision"])
        if identity in seen or digest(body) != entry["sha256"]:
            raise ValueError("Duplicate or changed manifest content")
        seen.add(identity)
        documents.append({**entry, "body": body})
    return documents

"""Operator-reviewed, non-secret investigation release pinned to each training run."""

import hashlib
import json
import os
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.dify_provider import CONTRACT_VERSION
from app.auth.models import Strict
from app.knowledge.dify_client import DifyConfig


class InvestigationRelease(Strict):
    status: str
    reviewer: str = Field(min_length=1, max_length=200)
    workflow_id: UUID
    base_url: str
    model_id: str = Field(min_length=1, max_length=100)
    contract_version: str
    max_output_tokens: int
    call_bound_usd: Decimal = Field(gt=0, le=Decimal("0.25"), decimal_places=6)
    cost_bound_verified: bool


def release_snapshot(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    values = os.environ if env is None else env
    try:
        path = Path(values["DIFY_ANALYSIS_RELEASE_FILE"])
        if path.is_symlink() or path.stat().st_size > 16000:
            raise ValueError("Invalid review file")
        review = InvestigationRelease.model_validate_json(path.read_text(encoding="utf8"))
        if (
            review.status != "approved_for_investigation"
            or not review.cost_bound_verified
            or review.contract_version != CONTRACT_VERSION
            or review.max_output_tokens != 2048
        ):
            raise ValueError("Unapproved release")
        config = DifyConfig.from_env(
            {
                "DIFY_API_BASE_URL": review.base_url,
                "DIFY_APP_KEY_FILE": values["DIFY_ANALYSIS_APP_KEY_FILE"],
            }
        )
        snapshot = review.model_dump(mode="json")
        snapshot["base_url"] = config.base_url
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        return snapshot | {"release_hash": digest}
    except (KeyError, OSError, ValueError, RuntimeError):
        raise ValueError("DIFY_INVESTIGATION_RELEASE_UNAVAILABLE") from None


def current_release(snapshot: Any) -> bool:
    try:
        return isinstance(snapshot, dict) and snapshot == release_snapshot()
    except ValueError:
        return False


def model_pin(snapshot: dict[str, Any]) -> str:
    return "dify-investigation:" + str(snapshot["release_hash"])


def transport_config(snapshot: dict[str, Any]) -> DifyConfig:
    if not current_release(snapshot):
        raise ValueError("DIFY_INVESTIGATION_RELEASE_WITHDRAWN")
    config = DifyConfig.from_env(
        {
            "DIFY_API_BASE_URL": snapshot["base_url"],
            "DIFY_APP_KEY_FILE": os.environ.get("DIFY_ANALYSIS_APP_KEY_FILE", ""),
        }
    )
    key = config.read_api_key()
    tutor_path = os.environ.get("DIFY_APP_KEY_FILE")
    if tutor_path and Path(tutor_path).is_file():
        if key == Path(tutor_path).read_text(encoding="utf8").strip():
            raise ValueError("DIFY_INVESTIGATION_REQUIRES_SEPARATE_APP_KEY")
    return config


async def analysis_withdrawn(session: AsyncSession, run_id: UUID, mode: str) -> bool:
    if mode != "real":
        return False
    pinned = await session.scalar(
        text("SELECT config_snapshot->'investigation' FROM app.run_versions WHERE run_id=:run"),
        {"run": run_id},
    )
    if not current_release(pinned):
        return True
    from app.analysis.investigation_budget import drifted

    return await drifted(session, pinned["release_hash"])

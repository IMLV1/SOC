from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt, field_validator

from app.auth.models import AuthMeta, Strict
from app.input_validation import InputModel


class ScenarioView(Strict):
    id: UUID
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)
    difficulty: Literal["beginner", "intermediate", "advanced"]
    duration_ms: int = Field(gt=0)
    learning_objectives: list[str] = Field(min_length=1, max_length=10)


class CatalogMeta(AuthMeta):
    next_cursor: str | None = None


class ScenarioCatalog(Strict):
    data: list[ScenarioView]
    meta: CatalogMeta


class TrainingSelection(InputModel):
    """Admission input for the future training service, never exam creation."""

    scenario_ids: list[UUID] = Field(min_length=1, max_length=5)
    seed: StrictInt | None = Field(default=None, ge=0, le=2147483647)

    @field_validator("scenario_ids")
    @classmethod
    def unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate selection")
        return value

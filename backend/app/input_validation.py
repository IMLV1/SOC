"""Validation shared by client-supplied JSON, never provider/response payloads."""

from typing import Annotated

from pydantic import AfterValidator, model_validator

from app.http_models import StrictModel


def nonblank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Text is required")
    return value


NonBlankText = Annotated[str, AfterValidator(nonblank)]


def reject_null_characters(value: object, depth: int = 0) -> None:
    # PostgreSQL text/jsonb cannot store U+0000. Reject it before any transaction.
    if depth > 64:
        raise ValueError("Input nesting is too deep")
    if isinstance(value, str):
        if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("Invalid text")
    if isinstance(value, dict):
        for key, item in value.items():
            reject_null_characters(key, depth + 1)
            reject_null_characters(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            reject_null_characters(item, depth + 1)


class InputModel(StrictModel):
    @model_validator(mode="before")
    @classmethod
    def valid_text(cls, value: object) -> object:
        reject_null_characters(value)
        return value

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginInput(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def email_format(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Invalid email")
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Invalid email")
        return value


class RegisterInput(LoginInput):
    display_name: str = Field(min_length=1, max_length=60)

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Invalid name")
        value = value.strip()
        if not value:
            raise ValueError("Empty name")
        return value


class UserView(Strict):
    id: UUID
    display_name: str
    email: str
    role: Literal["analyst", "instructor"]
    status: Literal["active", "disabled"]


class AuthMeta(Strict):
    request_id: str


class PageMeta(AuthMeta):
    next_cursor: str | None = None


class UserEnvelope(Strict):
    data: UserView
    meta: AuthMeta


class CsrfData(Strict):
    csrf_token: str


class CsrfEnvelope(Strict):
    data: CsrfData
    meta: AuthMeta


class SessionData(CsrfData):
    user: UserView
    expires_at: datetime


class SessionEnvelope(Strict):
    data: SessionData
    meta: AuthMeta


class QuotaData(Strict):
    daily_runs: int
    daily_ai_requests: int
    run_count: int
    ai_request_count: int
    reserved_tokens: int
    consumed_tokens: int
    reset_at: datetime


class QuotaEnvelope(Strict):
    data: QuotaData
    meta: AuthMeta

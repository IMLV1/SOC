from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(StrictModel):
    request_id: str


class ErrorDetail(StrictModel):
    code: str
    message: str


class ErrorEnvelope(StrictModel):
    error: ErrorDetail
    meta: Meta


class LiveData(StrictModel):
    status: Literal["alive"] = "alive"


class LiveEnvelope(StrictModel):
    data: LiveData
    meta: Meta


class ReadyData(StrictModel):
    status: Literal["ready"] = "ready"


class ReadyEnvelope(StrictModel):
    data: ReadyData
    meta: Meta

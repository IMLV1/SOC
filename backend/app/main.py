"""Process health only. Domain routes require approved contracts before implementation."""

from collections.abc import Awaitable, Callable
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException


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


app = FastAPI(title="SOC API", version="0.1.0", docs_url="/docs", redoc_url=None)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Generate locally; never reflect an untrusted header or any request payload.
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    return response


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    body = ErrorEnvelope(
        error=ErrorDetail(code=code, message=message),
        meta=Meta(request_id=request.state.request_id),
    )
    return JSONResponse(status_code=status, content=body.model_dump())


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    return error_response(request, exc.status_code, code, "Request could not be processed.")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not reflect raw input, exception context, secrets or future exam data.
    return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed.")


@app.get("/health/live", response_model=LiveEnvelope, operation_id="health_live", tags=["health"])
async def live(request: Request) -> LiveEnvelope:
    return LiveEnvelope(data=LiveData(), meta=Meta(request_id=request.state.request_id))


@app.get(
    "/health/ready",
    response_model=ErrorEnvelope,
    status_code=503,
    response_description="Database/migration foundation is not implemented in step 01.",
    operation_id="health_ready",
    tags=["health"],
)
async def ready(request: Request) -> ErrorEnvelope:
    # Step 02 must replace this with real DB + migration compatibility checks.
    # A live process is not proof that database-backed features are ready.
    return ErrorEnvelope(
        error=ErrorDetail(code="SERVICE_UNAVAILABLE", message="Database foundation is not ready."),
        meta=Meta(request_id=request.state.request_id),
    )

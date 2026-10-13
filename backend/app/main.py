from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.auth.routes import router as auth_router
from app.auth.service import AuthError
from app.db.config import database_url
from app.db.health import check_database
from app.db.session import Database
from app.demo import router as demo_router
from app.http_models import (
    ErrorDetail,
    ErrorEnvelope,
    LiveData,
    LiveEnvelope,
    Meta,
    ReadyData,
    ReadyEnvelope,
)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    database = None
    try:
        database = Database(database_url("api_runtime"))
    except (ValueError, OSError):
        pass
    application.state.database = database
    try:
        yield
    finally:
        if database is not None:
            await database.close()


app = FastAPI(title="SOC API", version="0.1.0", docs_url="/docs", redoc_url=None, lifespan=lifespan)
app.include_router(auth_router)
app.include_router(demo_router)


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


@app.exception_handler(AuthError)
async def auth_error(request: Request, exc: AuthError) -> JSONResponse:
    response = error_response(request, exc.status, exc.code, "Request could not be processed.")
    if exc.status == 429:
        response.headers["Retry-After"] = "60"
    return response


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    return error_response(request, 503, "SERVICE_UNAVAILABLE", "Service temporarily unavailable.")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    return error_response(request, exc.status_code, code, "Request could not be processed.")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not reflect raw input, exception context, secrets or future exam data.
    if any(error["type"] == "json_invalid" for error in exc.errors()):
        return error_response(request, 400, "BAD_REQUEST", "Request could not be processed.")
    return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed.")


@app.get("/health/live", response_model=LiveEnvelope, operation_id="health_live", tags=["health"])
async def live(request: Request) -> LiveEnvelope:
    return LiveEnvelope(data=LiveData(), meta=Meta(request_id=request.state.request_id))


@app.get(
    "/health/ready",
    response_model=ReadyEnvelope,
    responses={
        503: {"model": ErrorEnvelope, "description": "Database or migration state unavailable."}
    },
    operation_id="health_ready",
    tags=["health"],
)
async def ready(request: Request) -> ReadyEnvelope | JSONResponse:
    database = request.app.state.database
    if database is None or not await check_database(database, "api_runtime"):
        return error_response(
            request, 503, "SERVICE_UNAVAILABLE", "Database foundation is not ready."
        )
    return ReadyEnvelope(data=ReadyData(), meta=Meta(request_id=request.state.request_id))

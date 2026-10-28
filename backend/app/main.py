import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.analysis.routes import router as analysis_router
from app.auth.google_routes import router as google_router
from app.auth.routes import router as auth_router
from app.auth.service import AuthError
from app.db.config import database_url
from app.db.health import check_database
from app.db.session import Database
from app.demo import router as demo_router
from app.evaluation.routes import admin_router as instructor_evaluation_router
from app.evaluation.routes import router as evaluation_router
from app.exams.routes import router as exam_router
from app.http_models import (
    ErrorDetail,
    ErrorEnvelope,
    LiveData,
    LiveEnvelope,
    Meta,
    ReadyData,
    ReadyEnvelope,
)
from app.investigation.routes import admin_router as admin_ticket_router
from app.investigation.routes import router as ticket_router
from app.knowledge.routes import router as rag_router
from app.learning.practice_routes import router as practice_router
from app.learning.routes import router as learning_router
from app.runs.routes import router as run_router
from app.scenarios.routes import router as scenario_router
from app.tutor.routes import router as tutor_router


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
app.include_router(google_router)
app.include_router(demo_router)
app.include_router(scenario_router)
app.include_router(run_router)
app.include_router(ticket_router)
app.include_router(admin_ticket_router)
app.include_router(analysis_router)
app.include_router(rag_router)
app.include_router(learning_router)
app.include_router(practice_router)
app.include_router(tutor_router)
app.include_router(exam_router)
app.include_router(evaluation_router)
app.include_router(instructor_evaluation_router)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Generate locally; never reflect an untrusted header or any request payload.
    request.state.request_id = str(uuid4())
    from app.auth import supabase_provider, supabase_service

    if (
        supabase_provider.enabled()
        and request.url.path.startswith("/api/v1/")
        and request.url.path != "/api/v1/auth/logout"
    ):
        try:
            await supabase_service.prepare(request)
        except AuthError as exc:
            if exc.status != 401:
                unavailable = await auth_error(request, exc)
                unavailable.headers["X-Request-ID"] = request.state.request_id
                unavailable.headers["Cache-Control"] = "no-store"
                return unavailable
    if (
        os.getenv("SOC_PREVIEW_MODE") == "auth_only"
        and request.method in {"POST", "PATCH", "PUT", "DELETE"}
        and request.url.path.startswith("/api/v1/")
        and not request.url.path.startswith(("/api/v1/auth/", "/api/v1/demo/"))
    ):
        response: Response = error_response(
            request, 503, "PREVIEW_UNAVAILABLE", "Runner is unavailable on this preview."
        )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response
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

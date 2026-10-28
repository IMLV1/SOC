"""Public, benign example snapshot; separate from learner runs and any exam bank."""

from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.auth.models import AuthMeta, Strict
from app.auth.service import AuthError
from app.auth.service import database as request_database
from app.http_models import ErrorEnvelope


class DemoEvent(Strict):
    id: UUID
    event_time: str
    method: str
    path: str
    status_code: int
    description: str


class DemoMeta(AuthMeta):
    next_cursor: str | None = None


class DemoEvents(Strict):
    data: list[DemoEvent]
    meta: DemoMeta


class DemoDetail(Strict):
    data: DemoEvent
    meta: AuthMeta


class DemoSummary(Strict):
    is_demo: bool = True
    status: str = "published_example"
    event_count: int
    description: str


class DemoOverview(Strict):
    data: DemoSummary
    meta: AuthMeta


async def published_events(request: Request) -> list[DemoEvent]:
    async with request_database(request).sessions() as session:
        rows = (
            (
                await session.execute(
                    text("SELECT content_json FROM app.demo_events ORDER BY ordinal")
                )
            )
            .scalars()
            .all()
        )
    return [DemoEvent.model_validate(row) for row in rows]


router = APIRouter(
    prefix="/api/v1/demo",
    tags=["Demo"],
    responses={404: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope}},
)


@router.get("/overview", response_model=DemoOverview, operation_id="demo_overview")
async def overview(request: Request) -> DemoOverview:
    return DemoOverview(
        data=DemoSummary(
            event_count=len(await published_events(request)),
            description="ข้อมูลตัวอย่างแบบอ่านอย่างเดียว แยกจากรอบฝึกและข้อสอบ",
        ),
        meta=AuthMeta(request_id=request.state.request_id),
    )


@router.get("/events", response_model=DemoEvents, operation_id="demo_events")
async def events(request: Request) -> DemoEvents:
    return DemoEvents(
        data=await published_events(request), meta=DemoMeta(request_id=request.state.request_id)
    )


@router.get("/events/{event_id}", response_model=DemoDetail, operation_id="demo_event")
async def event(event_id: UUID, request: Request) -> DemoDetail:
    for item in await published_events(request):
        if item.id == event_id:
            return DemoDetail(data=item, meta=AuthMeta(request_id=request.state.request_id))
    raise AuthError(404, "NOT_FOUND")

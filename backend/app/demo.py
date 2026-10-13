"""Public, benign example snapshot; separate from learner runs and any exam bank."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.auth.models import AuthMeta, Strict
from app.auth.service import AuthError
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


EVENTS = [
    DemoEvent(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        event_time="2026-01-01T09:00:00Z",
        method="GET",
        path="/help",
        status_code=200,
        description="ตัวอย่างการอ่านหน้าคู่มือสำเร็จ ไม่ใช่ข้อมูลผู้ใช้จริง",
    ),
    DemoEvent(
        id=UUID("00000000-0000-4000-8000-000000000002"),
        event_time="2026-01-01T09:01:00Z",
        method="GET",
        path="/missing-page",
        status_code=404,
        description="ตัวอย่างการขอหน้าที่ไม่มีอยู่ ใช้ฝึกอ่าน request และ response",
    ),
]
router = APIRouter(
    prefix="/api/v1/demo",
    tags=["Demo"],
    responses={404: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope}},
)


@router.get("/overview", response_model=DemoOverview, operation_id="demo_overview")
async def overview(request: Request) -> DemoOverview:
    return DemoOverview(
        data=DemoSummary(
            event_count=len(EVENTS), description="ข้อมูลตัวอย่างแบบอ่านอย่างเดียว แยกจากรอบฝึกและข้อสอบ"
        ),
        meta=AuthMeta(request_id=request.state.request_id),
    )


@router.get("/events", response_model=DemoEvents, operation_id="demo_events")
async def events(request: Request) -> DemoEvents:
    return DemoEvents(data=EVENTS, meta=DemoMeta(request_id=request.state.request_id))


@router.get("/events/{event_id}", response_model=DemoDetail, operation_id="demo_event")
async def event(event_id: UUID, request: Request) -> DemoDetail:
    for item in EVENTS:
        if item.id == event_id:
            return DemoDetail(data=item, meta=AuthMeta(request_id=request.state.request_id))
    raise AuthError(404, "NOT_FOUND")

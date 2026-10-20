from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthError, database
from app.http_models import ErrorEnvelope
from app.scenarios.models import CatalogMeta, ScenarioCatalog, ScenarioView, TrainingSelection

PUBLIC_COLUMNS = "id,version,public_title AS title,difficulty,duration_ms,learning_objectives"
router = APIRouter(prefix="/api/v1", tags=["Scenarios"])


@router.get(
    "/scenarios",
    response_model=ScenarioCatalog,
    operation_id="scenario_catalog",
    responses={
        400: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        503: {"model": ErrorEnvelope},
    },
)
async def catalog(
    request: Request, cursor: str | None = None, limit: int = Query(default=50, ge=1, le=100)
) -> ScenarioCatalog:
    try:
        after = UUID(cursor) if cursor is not None else UUID(int=0)
    except ValueError:
        raise AuthError(400, "BAD_REQUEST") from None
    async with database(request).sessions() as session:
        rows = await session.execute(
            text(
                f"SELECT {PUBLIC_COLUMNS} FROM app.scenarios "
                "WHERE enabled AND purpose='training' AND id > :after ORDER BY id LIMIT :count"
            ),
            {"after": after, "count": limit + 1},
        )
        items = [ScenarioView.model_validate(dict(row)) for row in rows.mappings()]
        return ScenarioCatalog(
            data=items[:limit],
            meta=CatalogMeta(
                request_id=request.state.request_id,
                next_cursor=str(items[limit - 1].id) if len(items) > limit else None,
            ),
        )


async def select_training(
    session: AsyncSession, selection: TrainingSelection
) -> list[ScenarioView]:
    """Caller must hold user/idempotency guards; never query a private exam bank.

    Only the training-only table can admit IDs; unknown, disabled and exam IDs
    fail alike. Step 06 owns run/quota/idempotency transaction enforcement.
    """
    rows = await session.execute(
        text(
            f"SELECT {PUBLIC_COLUMNS} FROM app.scenarios "
            "WHERE enabled AND purpose='training' AND id = ANY(:ids) ORDER BY id"
        ),
        {"ids": selection.scenario_ids},
    )
    selected = [ScenarioView.model_validate(dict(row)) for row in rows.mappings()]
    if len(selected) != len(selection.scenario_ids):
        raise AuthError(422, "INVALID_SCENARIO_SELECTION")
    return selected

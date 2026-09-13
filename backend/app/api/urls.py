from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repository import ClickRepository, ShortCodeExistsError, UrlRepository
from app.db.session import get_session
from app.middleware.rate_limit import enforce_rate_limit
from app.schemas import CreateUrlRequest, CreateUrlResponse, StatsResponse

router = APIRouter(prefix="/api/urls", tags=["urls"])


@router.post(
    "",
    response_model=CreateUrlResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_url(
    payload: CreateUrlRequest,
    session: AsyncSession = Depends(get_session),
) -> CreateUrlResponse:
    repo = UrlRepository(session)
    try:
        url = await repo.create(payload.long_url, payload.custom_code)
    except ShortCodeExistsError:
        raise HTTPException(status_code=409, detail="code_taken") from None
    return CreateUrlResponse(
        short_code=url.short_code,
        short_url=f"{settings.api_host}/{url.short_code}",
        long_url=url.long_url,
        created_at=url.created_at,
    )


@router.get("/{short_code}/stats", response_model=StatsResponse)
async def get_stats(
    short_code: str,
    session: AsyncSession = Depends(get_session),
) -> StatsResponse:
    """Aggregated click analytics for a single short code."""
    url_repo = UrlRepository(session)
    click_repo = ClickRepository(session)

    url = await url_repo.get_by_code(short_code)
    if url is None:
        raise HTTPException(status_code=404, detail="not_found")

    total = await click_repo.count_by_url(url.id)
    by_day = await click_repo.clicks_by_day(url.id, days=30)
    referrers = await click_repo.top_referrers(url.id, limit=5)
    browsers = await click_repo.top_browsers(url.id, limit=5)

    return StatsResponse(
        short_code=url.short_code,
        long_url=url.long_url,
        total_clicks=total,
        created_at=url.created_at,
        clicks_by_day=by_day,
        top_referrers=referrers,
        top_browsers=browsers,
    )
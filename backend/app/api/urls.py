from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repository import ShortCodeExistsError, UrlRepository
from app.db.session import get_session
from app.middleware.rate_limit import enforce_rate_limit
from app.schemas import CreateUrlRequest, CreateUrlResponse

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
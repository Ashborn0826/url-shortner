from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import UrlRepository
from app.db.session import get_session

router = APIRouter(tags=["redirect"])


@router.get("/{short_code}")
async def redirect_to_long_url(
    short_code: str,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    repo = UrlRepository(session)
    url = await repo.get_by_code(short_code)
    if url is None:
        raise HTTPException(status_code=404, detail="not_found")
    return RedirectResponse(url=url.long_url, status_code=302)
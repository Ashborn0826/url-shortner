from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import get_redis
from app.cache.url_cache import get_cached_url, set_cached_url
from app.db.repository import UrlRepository
from app.db.session import get_session

router = APIRouter(tags=["redirect"])


@router.get("/{short_code}")
async def redirect_to_long_url(
    short_code: str,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    # Cache-aside: try cache first.
    cached = await get_cached_url(redis, short_code)
    if cached is not None:
        return RedirectResponse(url=cached["long_url"], status_code=302)

    # Cache miss: fall through to Postgres.
    repo = UrlRepository(session)
    url = await repo.get_by_code(short_code)
    if url is None:
        # No negative caching: a flood of unknown codes still hits Postgres.
        raise HTTPException(status_code=404, detail="not_found")

    payload = {
        "short_code": url.short_code,
        "long_url": url.long_url,
        "created_at": url.created_at.isoformat(),
    }
    await set_cached_url(redis, short_code, payload)
    return RedirectResponse(url=url.long_url, status_code=302)
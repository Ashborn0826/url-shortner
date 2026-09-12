from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.queue import enqueue_click
from app.cache.redis_client import get_redis
from app.cache.url_cache import get_cached_url, set_cached_url
from app.config import settings
from app.db.repository import UrlRepository
from app.db.session import get_session

router = APIRouter(tags=["redirect"])


@router.get("/{short_code}")
async def redirect_to_long_url(
    request: Request,
    short_code: str,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    # Cache-aside: try cache first.
    cached = await get_cached_url(redis, short_code)
    if cached is not None:
        long_url: str = cached["long_url"]
    else:
        # Cache miss: fall through to Postgres.
        repo = UrlRepository(session)
        url = await repo.get_by_code(short_code)
        if url is None:
            # No negative caching: a flood of unknown codes still hits Postgres.
            raise HTTPException(status_code=404, detail="not_found")
        long_url = url.long_url
        payload = {
            "short_code": url.short_code,
            "long_url": url.long_url,
            "created_at": url.created_at.isoformat(),
        }
        await set_cached_url(redis, short_code, payload)

    # Enqueue click event (fire-and-forget). If the queue is unavailable,
    # we still return 302 to the user; the failure is logged but does not
    # break the redirect (analytics loss is acceptable; broken redirects
    # are not).
    event = {
        "short_code": short_code,
        "ts": datetime.now(timezone.utc).isoformat(),
        "referrer": request.headers.get("referer"),
        "user_agent": request.headers.get("user-agent"),
    }
    try:
        await enqueue_click(redis, event)
    except Exception:
        # swallow + log; the redirect still succeeds
        import logging

        logging.getLogger(__name__).exception("failed to enqueue click event")

    return RedirectResponse(url=long_url, status_code=302)
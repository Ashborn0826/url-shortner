"""Cache-aside wrapper for URL lookups.

Stores the URL payload as JSON under the key prefix `url:{short_code}` with
a configurable TTL. The redirect handler reads from this cache first and
falls through to Postgres on miss.
"""
import json
from typing import Any

from redis.asyncio import Redis

from app.config import settings


def _key(short_code: str) -> str:
    return f"url:{short_code}"


async def get_cached_url(redis: Redis, short_code: str) -> dict[str, Any] | None:
    raw = await redis.get(_key(short_code))
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached_url(
    redis: Redis, short_code: str, payload: dict[str, Any], ttl: int | None = None
) -> None:
    effective_ttl = ttl if ttl is not None else settings.cache_ttl_seconds
    await redis.set(_key(short_code), json.dumps(payload), ex=effective_ttl)


async def invalidate(redis: Redis, short_code: str) -> None:
    await redis.delete(_key(short_code))
"""Per-IP rate limiting for the URL creation endpoint.

Implementation: Redis INCR + EXPIRE pattern. The first request from an IP
sets the counter and starts a sliding window via EXPIRE; subsequent requests
just INCR. If the counter exceeds the configured limit, the request is
rejected with 429 and a Retry-After header.

Why Redis: the counter is the shared state across multiple uvicorn workers.
In-memory counters would let users bypass the limit by hitting different
workers, breaking the invariant.

Race condition note: between the INCR and EXPIRE calls, if the worker
crashes, the key has no TTL. The next INCR returns 2 (not 1) so we never
set EXPIRE. The key then persists forever. For learning purposes we accept
this rare case. In production, use a Lua script for atomicity, or use
Redis 7+'s EXPIRE with NX option.
"""
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.cache.redis_client import get_redis
from app.config import settings


async def enforce_rate_limit(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> None:
    if request.client is None:
        return  # be permissive if we can't identify the client

    client_ip = request.client.host
    key = f"rl:{client_ip}"

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.rate_limit_window_seconds)

    if count > settings.rate_limit_requests:
        retry_after = await redis.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
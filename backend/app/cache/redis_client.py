from redis.asyncio import Redis

from app.config import settings


async def get_redis() -> Redis:
    """Return an async Redis client.

    In production this connects to the configured Redis URL. In tests we
    override this dependency with a `fakeredis` instance via the FastAPI
    `dependency_overrides` mechanism.
    """
    return Redis.from_url(settings.redis_url, decode_responses=True)
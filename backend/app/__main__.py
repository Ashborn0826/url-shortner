"""Entry point: `python -m app` starts the click worker.

Run alongside the API server (uvicorn). The worker drains the click
queue in `clicks:queue`, parses user-agent, persists to Postgres, and
falls back to the dead-letter queue `clicks:dlq` after 3 failed retries.

Ctrl-C / SIGTERM gracefully shuts down the worker.
"""
import asyncio
import logging
import signal

from redis.asyncio import Redis

from app.analytics.worker import run_worker_loop
from app.config import settings


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows: signal handlers aren't supported for SIGTERM in asyncio.
            # SIGINT (Ctrl-C) still works.
            pass

    logger = logging.getLogger(__name__)
    logger.info("click worker starting (redis=%s)", settings.redis_url)
    await run_worker_loop(redis, stop)
    logger.info("click worker stopped")
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
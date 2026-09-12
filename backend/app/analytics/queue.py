"""Click event queue (Redis list) + DLQ.

We use a plain Redis list instead of arq's queue because:

1. fakeredis (used in tests) doesn't speak arq's protocol, and arq wants
   real Redis connections on a port. The semantic difference is just
   serialization format — a Redis list with JSON values is functionally
   equivalent for our use case.
2. Retry + DLQ logic lives in `process_one` (analytics/worker.py) where
   it's easier to read and unit-test than in arq's retry_defer config.
3. The list semantics are exactly what we need: LPUSH on producer side,
   BRPOP on worker side, RPUSH for DLQ.

If we ever add scheduled or periodic jobs (arq cron, delayed jobs), we
can revisit and bring arq back. For a fire-and-forget click pipeline,
this is the minimum complexity that works.
"""
import json
from typing import Any

from redis.asyncio import Redis

QUEUE_KEY = "clicks:queue"
DLQ_KEY = "clicks:dlq"


async def enqueue_click(redis: Redis, event: dict[str, Any]) -> None:
    """Enqueue a click event (LPUSH).

    Fire-and-forget from the caller's perspective: the redirect handler
    awaits this, but if Redis is unavailable the handler catches the
    exception and still returns 302 to the user.
    """
    await redis.lpush(QUEUE_KEY, json.dumps(event))


async def dequeue_click(redis: Redis, timeout: float = 1.0) -> dict[str, Any] | None:
    """Pop one event from the queue, blocking up to `timeout` seconds.

    Returns None if no event is available within the timeout.
    """
    result = await redis.brpop(QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, value = result
    return json.loads(value)


async def push_to_dlq(redis: Redis, event: dict[str, Any], error: str) -> None:
    """Push a permanently-failed event to the DLQ with error context."""
    payload = {"event": event, "error": error}
    await redis.rpush(DLQ_KEY, json.dumps(payload))


async def drain_dlq(redis: Redis) -> list[dict[str, Any]]:
    """Pop all events from the DLQ. Used for manual inspection / replay."""
    events: list[dict[str, Any]] = []
    while True:
        raw = await redis.lpop(DLQ_KEY)
        if raw is None:
            break
        events.append(json.loads(raw))
    return events
"""Click worker.

Two entry points:

- `process_one(redis, event)` — handle one event with retry + DLQ. Used
  by both the in-process worker loop and unit tests that don't need a
  subprocess.

- `run_worker_loop(redis, stop_event)` — long-running BRPOP loop. Start
  with `asyncio.create_task(run_worker_loop(redis, stop))` in production
  (or in a separate process for full isolation).

Retry policy: 3 attempts with exponential backoff 1s/4s/16s (total
max wall-clock ~21s per event). After exhausting retries the event
goes to the DLQ (`clicks:dlq`) and `process_one` returns False.

We accept duplicate clicks if the worker crashes after writing the row
but before returning — see `notes/phase-3-explanation.md` for the
idempotency discussion. This is the standard "best-effort delivery"
trade-off for analytics that don't promise exactly-once.
"""
import asyncio
import logging
from typing import Any

from redis.asyncio import Redis

from app.analytics.persist import persist_click
from app.analytics.queue import dequeue_click, push_to_dlq

logger = logging.getLogger(__name__)

# Retry delays in seconds. Index = attempt number; 3 entries = 3 retries.
RETRY_DELAYS = [1, 4, 16]


async def process_one(redis: Redis, event: dict[str, Any]) -> bool:
    """Process one click event with retry + DLQ.

    Returns True if persisted, False if pushed to DLQ after exhausting retries.
    """
    last_error: Exception | None = None
    for attempt in range(len(RETRY_DELAYS) + 1):  # 1 initial + 3 retries
        try:
            await persist_click(event)
            return True
        except Exception as e:
            last_error = e
            if attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                logger.warning(
                    "click persist attempt %d failed: %s, retrying in %ds",
                    attempt + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "click persist permanently failed after %d attempts: %s",
                    len(RETRY_DELAYS) + 1,
                    e,
                )
                if last_error is not None:
                    await push_to_dlq(redis, event, str(last_error))
                else:
                    await push_to_dlq(redis, event, "unknown error")
                return False
    return False  # unreachable


async def run_worker_loop(redis: Redis, stop_event: asyncio.Event) -> None:
    """Long-running worker loop. BRPOPs and processes until stop_event is set."""
    while not stop_event.is_set():
        event = await dequeue_click(redis, timeout=0.5)
        if event is None:
            continue
        await process_one(redis, event)
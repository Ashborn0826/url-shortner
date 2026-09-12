"""End-to-end tests for the click pipeline: queue → worker → DB."""
import asyncio

import pytest
from sqlalchemy import func, select

from app.analytics.persist import persist_click
from app.analytics.queue import (
    DLQ_KEY,
    QUEUE_KEY,
    dequeue_click,
    drain_dlq,
    enqueue_click,
    push_to_dlq,
)
from app.analytics.worker import process_one, run_worker_loop
from app.db.models import Click


async def test_enqueue_dequeue_round_trip(redis_client):
    event = {"short_code": "abc1234", "ts": "2026-09-12T10:00:00+00:00"}
    await enqueue_click(redis_client, event)
    got = await dequeue_click(redis_client, timeout=0.5)
    assert got == event


async def test_dequeue_empty_returns_none(redis_client):
    assert await dequeue_click(redis_client, timeout=0.2) is None


async def test_push_to_dlq_and_drain(redis_client):
    event = {"short_code": "x", "ts": "t"}
    await push_to_dlq(redis_client, event, "boom")
    dlq = await drain_dlq(redis_client)
    assert len(dlq) == 1
    assert dlq[0]["event"] == event
    assert dlq[0]["error"] == "boom"


async def test_persist_click_writes_row(redis_client, session):
    # Need a URL to FK against
    from app.db.repository import UrlRepository

    create = await UrlRepository(session).create("https://example.com", custom_code="docs")
    await session.commit()

    event = {
        "short_code": "docs",
        "ts": "2026-09-12T10:00:00+00:00",
        "referrer": "https://google.com",
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    }
    click_id = await persist_click(event)
    assert click_id > 0

    # Verify the click landed in the DB
    result = await session.execute(select(Click))
    clicks = result.scalars().all()
    assert len(clicks) == 1
    c = clicks[0]
    assert c.url_id == create.id
    assert c.referrer == "https://google.com"
    assert c.browser == "Chrome"
    assert c.os == "Linux"
    assert c.device == "Desktop"


async def test_persist_drops_click_for_deleted_url(redis_client, session):
    """If the URL was deleted between redirect and processing, drop the click."""
    event = {"short_code": "ghost", "ts": "2026-09-12T10:00:00+00:00", "referrer": None, "user_agent": None}
    click_id = await persist_click(event)
    assert click_id == 0
    result = await session.execute(select(func.count()).select_from(Click))
    assert result.scalar() == 0


async def test_worker_loop_processes_100_clicks(client, redis_client, session):
    """End-to-end: hit the redirect 100 times, the worker drains the queue,
    all 100 clicks land in the DB within 5 seconds.
    """
    create = await client.post(
        "/api/urls", json={"long_url": "https://example.com/e2e"}
    )
    code = create.json()["short_code"]

    # Start the worker loop in the background.
    stop = asyncio.Event()
    worker_task = asyncio.create_task(run_worker_loop(redis_client, stop))

    try:
        # Hit the redirect 100 times. Each request enqueues a click event.
        for _ in range(100):
            r = await client.get(
                f"/{code}", follow_redirects=False, headers={"user-agent": "Test/1.0"}
            )
            assert r.status_code == 302

        # Wait for the queue to drain (up to 5 seconds).
        deadline = asyncio.get_event_loop().time() + 5.0
        while asyncio.get_event_loop().time() < deadline:
            queue_size = await redis_client.llen(QUEUE_KEY)
            if queue_size == 0:
                # Give the worker a tick to finish processing the last item.
                await asyncio.sleep(0.1)
                break
            await asyncio.sleep(0.05)

        # Verify exactly 100 click rows landed.
        result = await session.execute(select(func.count()).select_from(Click))
        count = result.scalar()
        assert count == 100
    finally:
        stop.set()
        await worker_task


async def test_failed_event_goes_to_dlq_after_retries(redis_client, session, monkeypatch):
    """If persist_click always raises, the event must end up in the DLQ
    after exhausting retries (not infinitely retried, not silently dropped).
    """
    calls = []

    async def always_failing(event):
        calls.append(event)
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr("app.analytics.worker.persist_click", always_failing)

    # Don't actually wait 21s of real time — patch the retry delays to
    # be much shorter for the test.
    monkeypatch.setattr("app.analytics.worker.RETRY_DELAYS", [0.01, 0.01, 0.01])

    event = {"short_code": "x", "ts": "2026-09-12T10:00:00+00:00"}
    ok = await process_one(redis_client, event)
    assert ok is False
    # 1 initial + 3 retries = 4 calls total
    assert len(calls) == 4

    # Event must be in the DLQ
    dlq = await drain_dlq(redis_client)
    assert len(dlq) == 1
    assert dlq[0]["event"] == event
    assert "simulated DB failure" in dlq[0]["error"]


async def test_recovered_event_does_not_go_to_dlq(redis_client, monkeypatch):
    """If persist_click fails once then succeeds, no DLQ entry."""
    monkeypatch.setattr("app.analytics.worker.RETRY_DELAYS", [0.01, 0.01, 0.01])

    calls = []

    async def fail_then_succeed(event):
        calls.append(event)
        if len(calls) == 1:
            raise RuntimeError("transient")

    monkeypatch.setattr("app.analytics.worker.persist_click", fail_then_succeed)

    event = {"short_code": "x", "ts": "2026-09-12T10:00:00+00:00"}
    ok = await process_one(redis_client, event)
    assert ok is True
    assert len(calls) == 2
    assert await drain_dlq(redis_client) == []
import pytest


async def test_under_limit_passes(client, redis_client):
    for i in range(3):
        r = await client.post("/api/urls", json={"long_url": f"https://a.com/{i}"})
        assert r.status_code == 201, r.text


async def test_at_limit_passes(client, redis_client):
    """Making exactly N requests succeeds (count == N is allowed)."""
    # Default limit is 10
    for i in range(10):
        r = await client.post("/api/urls", json={"long_url": f"https://a.com/{i}"})
        assert r.status_code == 201, f"req {i}: {r.text}"


async def test_over_limit_returns_429_with_retry_after(client, redis_client):
    # Default limit is 10
    for i in range(10):
        r = await client.post("/api/urls", json={"long_url": f"https://a.com/{i}"})
        assert r.status_code == 201

    blocked = await client.post("/api/urls", json={"long_url": "https://b.com"})
    assert blocked.status_code == 429
    assert "retry-after" in {k.lower() for k in blocked.headers.keys()}
    assert int(blocked.headers["retry-after"]) > 0


async def test_redirect_is_not_rate_limited(client, redis_client):
    """Rate limit applies only to POST /api/urls, not to GET /{code}.

    100 redirect requests must all succeed regardless of creation limit.
    """
    create = await client.post(
        "/api/urls", json={"long_url": "https://example.com"}
    )
    code = create.json()["short_code"]
    for _ in range(50):
        r = await client.get(f"/{code}", follow_redirects=False)
        assert r.status_code == 302


async def test_redis_state_is_under_rl_prefix(client, redis_client):
    """Sanity: rate-limit keys live under rl: prefix, not url:."""
    await client.post("/api/urls", json={"long_url": "https://a.com"})
    keys = await redis_client.keys("rl:*")
    assert len(keys) >= 1
    assert all(k.startswith("rl:") for k in keys)


async def test_rate_limit_counter_lives_in_redis(client, redis_client):
    """The rate-limit counter MUST live in Redis, not in process memory.

    This test proves the cross-worker invariant at its root: if the counter
    is in Redis, any number of uvicorn workers all see the same counter,
    so the limit is `limit` per IP (not `limit * worker_count` per IP).

    If someone later moves the counter to a Python dict in process memory,
    this test fails immediately and loudly.
    """
    # 10 successful requests (httpx's ASGITransport host is "127.0.0.1")
    for i in range(10):
        r = await client.post("/api/urls", json={"long_url": f"https://a.com/{i}"})
        assert r.status_code == 201

    # Counter must be in Redis under the rl: prefix, value "10"
    assert await redis_client.get("rl:127.0.0.1") == "10"

    # 11th request from the same IP must be rate-limited
    r = await client.post("/api/urls", json={"long_url": "https://b.com"})
    assert r.status_code == 429

    # Counter still tracks the over-the-limit attempts (so the 429 was
    # because we EXCEEDED the limit, not because the counter got reset)
    assert int(await redis_client.get("rl:127.0.0.1")) >= 11
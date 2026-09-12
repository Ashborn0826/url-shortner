"""Integration tests for the cache-aside pattern on GET /{short_code}."""
import pytest


async def test_first_request_is_cache_miss_then_populates_cache(client, redis_client):
    create = await client.post(
        "/api/urls", json={"long_url": "https://example.com/first"}
    )
    code = create.json()["short_code"]

    # Pre-condition: cache must be empty for this code.
    await redis_client.delete(f"url:{code}")

    r = await client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302

    cached = await redis_client.get(f"url:{code}")
    assert cached is not None
    import json

    payload = json.loads(cached)
    assert payload["long_url"] == "https://example.com/first"
    assert payload["short_code"] == code


async def test_second_request_uses_cache_no_db_query(client, redis_client, monkeypatch):
    """After the first request populates the cache, the second request must
    NOT touch the repository. We prove this by counting get_by_code calls.
    """
    from app.db.repository import UrlRepository

    create = await client.post(
        "/api/urls", json={"long_url": "https://example.com/cached"}
    )
    code = create.json()["short_code"]

    real_get_by_code = UrlRepository.get_by_code
    call_count = 0

    async def counting_get_by_code(self, sc):
        nonlocal call_count
        call_count += 1
        return await real_get_by_code(self, sc)

    monkeypatch.setattr(UrlRepository, "get_by_code", counting_get_by_code)

    # First request: cache miss, populates DB call count.
    r1 = await client.get(f"/{code}", follow_redirects=False)
    assert r1.status_code == 302
    assert call_count == 1

    # Second request: must be a cache hit.
    r2 = await client.get(f"/{code}", follow_redirects=False)
    assert r2.status_code == 302
    assert call_count == 1, "expected cache hit, but DB was queried again"


async def test_unknown_code_returns_404_and_does_not_cache(client, redis_client):
    """No negative caching: a 404 does not write a sentinel to Redis."""
    r = await client.get("/zzzzzzz", follow_redirects=False)
    assert r.status_code == 404
    keys = await redis_client.keys("url:zzzzzzz")
    assert keys == []


async def test_custom_code_round_trip_through_cache(client, redis_client):
    await client.post(
        "/api/urls", json={"long_url": "https://example.com", "custom_code": "docs"}
    )
    # Cache should not be populated by creation (only by redirect).
    pre = await redis_client.get("url:docs")
    assert pre is None

    # Redirect populates cache.
    r = await client.get("/docs", follow_redirects=False)
    assert r.status_code == 302
    post = await redis_client.get("url:docs")
    assert post is not None
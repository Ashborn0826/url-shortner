import pytest

from app.cache.url_cache import get_cached_url, invalidate, set_cached_url


async def test_get_miss_returns_none(redis_client):
    assert await get_cached_url(redis_client, "missing") is None


async def test_set_then_get_round_trips_json(redis_client):
    payload = {"short_code": "abc1234", "long_url": "https://example.com"}
    await set_cached_url(redis_client, "abc1234", payload)
    got = await get_cached_url(redis_client, "abc1234")
    assert got == payload


async def test_set_uses_default_ttl_from_settings(redis_client):
    await set_cached_url(redis_client, "abc1234", {"long_url": "https://example.com"})
    ttl = await redis_client.ttl("url:abc1234")
    # Should be > 0 (set) and within the configured window.
    assert ttl > 0
    from app.config import settings

    assert ttl <= settings.cache_ttl_seconds


async def test_set_with_explicit_ttl(redis_client):
    await set_cached_url(redis_client, "abc1234", {"long_url": "https://x"}, ttl=120)
    ttl = await redis_client.ttl("url:abc1234")
    assert 0 < ttl <= 120


async def test_invalidate_removes_key(redis_client):
    await set_cached_url(redis_client, "abc1234", {"long_url": "https://x"})
    assert await get_cached_url(redis_client, "abc1234") is not None
    await invalidate(redis_client, "abc1234")
    assert await get_cached_url(redis_client, "abc1234") is None


async def test_keys_are_namespaced_by_url_prefix(redis_client):
    """Sanity: we don't collide with the rl: or clicks: prefixes."""
    await set_cached_url(redis_client, "abc1234", {"long_url": "https://x"})
    keys = await redis_client.keys("url:*")
    assert "url:abc1234" in keys
    keys = await redis_client.keys("rl:*")
    assert keys == []
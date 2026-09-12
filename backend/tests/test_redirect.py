import pytest


async def test_known_code_returns_302_with_location(client):
    create = await client.post(
        "/api/urls", json={"long_url": "https://example.com/path?x=1"}
    )
    assert create.status_code == 201
    code = create.json()["short_code"]

    response = await client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/path?x=1"


async def test_custom_code_redirects(client):
    await client.post(
        "/api/urls", json={"long_url": "https://example.com", "custom_code": "docs"}
    )
    response = await client.get("/docs", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com"


async def test_unknown_code_returns_404(client):
    response = await client.get("/zzzzzzz", follow_redirects=False)
    assert response.status_code == 404


async def test_health_endpoint_is_not_treated_as_short_code(client):
    """Regression: /health must NOT be matched by GET /{short_code}."""
    response = await client.get("/health", follow_redirects=False)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
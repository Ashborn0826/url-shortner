import pytest


async def test_create_returns_201_with_short_code(client):
    response = await client.post(
        "/api/urls",
        json={"long_url": "https://example.com/some/long/path"},
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["short_code"]) == 7
    assert body["long_url"] == "https://example.com/some/long/path"
    assert body["short_url"].endswith("/" + body["short_code"])


async def test_create_with_custom_code_returns_that_code(client):
    response = await client.post(
        "/api/urls",
        json={"long_url": "https://example.com", "custom_code": "docs"},
    )
    assert response.status_code == 201
    assert response.json()["short_code"] == "docs"


async def test_duplicate_custom_code_returns_409(client):
    first = await client.post(
        "/api/urls", json={"long_url": "https://a.example", "custom_code": "docs"}
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/urls", json={"long_url": "https://b.example", "custom_code": "docs"}
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "code_taken"


async def test_invalid_url_returns_422(client):
    response = await client.post("/api/urls", json={"long_url": "not-a-url"})
    assert response.status_code == 422


async def test_invalid_custom_code_too_short_returns_422(client):
    response = await client.post(
        "/api/urls", json={"long_url": "https://a.example", "custom_code": "ab"}
    )
    assert response.status_code == 422


async def test_invalid_custom_code_bad_chars_returns_422(client):
    response = await client.post(
        "/api/urls", json={"long_url": "https://a.example", "custom_code": "hi there"}
    )
    assert response.status_code == 422


async def test_custom_code_max_length_32_accepted(client):
    long_code = "a" * 32
    response = await client.post(
        "/api/urls", json={"long_url": "https://a.example", "custom_code": long_code}
    )
    assert response.status_code == 201
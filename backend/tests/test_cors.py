"""CORS middleware tests."""
import pytest


async def test_cors_preflight_options_returns_correct_headers(client):
    response = await client.options(
        "/api/urls",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    # Starlette's CORSMiddleware returns 200 for preflight (or 204 in newer versions)
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "POST" in response.headers.get("access-control-allow-methods", "")


async def test_cors_simple_get_includes_allow_origin_header(client):
    response = await client.get(
        "/api/urls/abc1234/stats",
        headers={"Origin": "http://localhost:5173"},
    )
    assert "access-control-allow-origin" in {k.lower() for k in response.headers.keys()}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_cors_does_not_allow_other_origins(client):
    response = await client.get(
        "/api/urls/abc1234/stats",
        headers={"Origin": "http://evil.example.com"},
    )
    # CORS spec: non-allowed origins get no Access-Control-Allow-Origin header
    allow_origin = response.headers.get("access-control-allow-origin", "")
    assert allow_origin != "http://evil.example.com"
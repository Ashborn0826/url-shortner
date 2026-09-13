"""Stats endpoint tests.

Covers the 4 aggregates (total_clicks, clicks_by_day, top_referrers,
top_browsers) plus the 404 path and the empty-data case.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.db.repository import ClickRepository, UrlRepository


async def _make_url(session, code: str = "docs"):
    url = await UrlRepository(session).create("https://example.com", custom_code=code)
    await session.commit()
    return url


async def _seed_clicks(session, url_id: int, rows: list[dict]) -> None:
    repo = ClickRepository(session)
    for row in rows:
        await repo.create(url_id=url_id, **row)


async def test_stats_unknown_code_returns_404(client):
    r = await client.get("/api/urls/nope/stats")
    assert r.status_code == 404
    assert r.json()["detail"] == "not_found"


async def test_stats_no_clicks_returns_empty_aggregates(client, session):
    await _make_url(session, "docs")
    r = await client.get("/api/urls/docs/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["short_code"] == "docs"
    assert data["long_url"] == "https://example.com"
    assert data["total_clicks"] == 0
    assert data["clicks_by_day"] == []
    assert data["top_referrers"] == []
    assert data["top_browsers"] == []


async def test_stats_total_clicks_counts_all(client, session):
    url = await _make_url(session, "docs")
    now = datetime.now(timezone.utc)
    await _seed_clicks(
        session,
        url.id,
        [
            {"clicked_at": now, "referrer": "https://a.com", "user_agent": "ua1", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": "https://b.com", "user_agent": "ua2", "browser": "Firefox", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": None, "user_agent": "ua3", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
        ],
    )
    r = await client.get("/api/urls/docs/stats")
    data = r.json()
    assert data["total_clicks"] == 3


async def test_stats_clicks_by_day_groups_correctly(client, session):
    url = await _make_url(session, "docs")
    now = datetime.now(timezone.utc)
    # 2 clicks today, 1 click yesterday, 1 click 5 days ago
    await _seed_clicks(
        session,
        url.id,
        [
            {"clicked_at": now, "referrer": None, "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": None, "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now - timedelta(days=1), "referrer": None, "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now - timedelta(days=5), "referrer": None, "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
        ],
    )
    r = await client.get("/api/urls/docs/stats")
    by_day = {d["day"]: d["count"] for d in r.json()["clicks_by_day"]}
    today = now.date().isoformat()
    yesterday = (now - timedelta(days=1)).date().isoformat()
    five_days_ago = (now - timedelta(days=5)).date().isoformat()
    assert by_day[today] == 2
    assert by_day[yesterday] == 1
    assert by_day[five_days_ago] == 1


async def test_stats_top_referrers_orders_by_count_and_buckets_null(client, session):
    url = await _make_url(session, "docs")
    now = datetime.now(timezone.utc)
    await _seed_clicks(
        session,
        url.id,
        [
            {"clicked_at": now, "referrer": "https://google.com", "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": "https://google.com", "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": "https://google.com", "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": "https://twitter.com", "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": None, "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
        ],
    )
    r = await client.get("/api/urls/docs/stats")
    referrers = r.json()["top_referrers"]
    # google 3, twitter 1, (direct) 1 — order by count desc
    assert referrers[0] == {"referrer": "https://google.com", "count": 3}
    # Last two are tied at 1; we don't pin order between them
    tail = {r["referrer"]: r["count"] for r in referrers[1:]}
    assert tail == {"https://twitter.com": 1, "(direct)": 1}


async def test_stats_top_referrers_caps_at_5(client, session):
    url = await _make_url(session, "docs")
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(7):
        rows.append({
            "clicked_at": now,
            "referrer": f"https://ref{i}.com",
            "user_agent": "ua",
            "browser": "Chrome",
            "os": "Linux",
            "device": "Desktop",
        })
    await _seed_clicks(session, url.id, rows)
    r = await client.get("/api/urls/docs/stats")
    assert len(r.json()["top_referrers"]) == 5


async def test_stats_top_browsers_orders_by_count(client, session):
    url = await _make_url(session, "docs")
    now = datetime.now(timezone.utc)
    await _seed_clicks(
        session,
        url.id,
        [
            {"clicked_at": now, "referrer": None, "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": None, "user_agent": "ua", "browser": "Chrome", "os": "Linux", "device": "Desktop"},
            {"clicked_at": now, "referrer": None, "user_agent": "ua", "browser": "Firefox", "os": "Linux", "device": "Desktop"},
        ],
    )
    r = await client.get("/api/urls/docs/stats")
    browsers = r.json()["top_browsers"]
    assert browsers[0] == {"browser": "Chrome", "count": 2}
    assert browsers[1] == {"browser": "Firefox", "count": 1}


async def test_stats_response_includes_created_at_and_url_metadata(client, session):
    url = await _make_url(session, "docs")
    r = await client.get("/api/urls/docs/stats")
    data = r.json()
    assert data["short_code"] == "docs"
    assert data["long_url"] == "https://example.com"
    assert "created_at" in data and data["created_at"]
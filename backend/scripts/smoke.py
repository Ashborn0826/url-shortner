"""End-to-end smoke test against a running stack.

Prerequisites:
  1. docker compose up -d (Postgres + Redis from infra/docker-compose.yml)
  2. cd backend && alembic upgrade head
  3. uvicorn app.main:app --port 8000   (in another shell)
  4. python -m app.analytics.worker    (in another shell, or use a worker entry-point)

Then:
  python backend/scripts/smoke.py

Exits 0 on success, non-zero on any check failure.
"""
import sys
import time

import httpx

API = "http://localhost:8000"
TIMEOUT = 10.0


def check_health() -> None:
    r = httpx.get(f"{API}/health", timeout=TIMEOUT)
    assert r.status_code == 200, f"/health: {r.status_code} {r.text!r}"
    assert r.json() == {"status": "ok"}


def create_url() -> str:
    r = httpx.post(
        f"{API}/api/urls",
        json={"long_url": "https://example.com/smoke", "custom_code": "smoke"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 201, f"create: {r.status_code} {r.text!r}"
    body = r.json()
    assert body["short_code"] == "smoke"
    assert body["short_url"].endswith("/smoke")
    assert body["long_url"] == "https://example.com/smoke"
    return body["short_code"]


def redirect(code: str) -> None:
    r = httpx.get(f"{API}/{code}", follow_redirects=False, timeout=TIMEOUT)
    assert r.status_code == 302, f"redirect: {r.status_code}"
    assert r.headers["location"] == "https://example.com/smoke"


def stats_after_wait(code: str) -> dict:
    # Wait for the click worker to drain the queue. Generous default.
    deadline = time.time() + 5.0
    last_total = -1
    while time.time() < deadline:
        r = httpx.get(f"{API}/api/urls/{code}/stats", timeout=TIMEOUT)
        if r.status_code == 200:
            last_total = r.json().get("total_clicks", 0)
            if last_total >= 1:
                return r.json()
        time.sleep(0.2)
    raise AssertionError(
        f"total_clicks never reached >=1 within 5s (last seen: {last_total})"
    )


def stats_404() -> None:
    r = httpx.get(f"{API}/api/urls/does-not-exist/stats", timeout=TIMEOUT)
    assert r.status_code == 404, f"stats 404: {r.status_code}"


def main() -> int:
    print("→ /health")
    check_health()
    print("  OK")

    print("→ POST /api/urls")
    code = create_url()
    print(f"  OK (code={code})")

    print(f"→ GET /{code} (redirect)")
    redirect(code)
    print("  OK (302 -> https://example.com/smoke)")

    print(f"→ GET /api/urls/{code}/stats (after worker drains)")
    stats = stats_after_wait(code)
    print(f"  OK (total_clicks={stats['total_clicks']})")

    print("→ GET /api/urls/does-not-exist/stats (404)")
    stats_404()
    print("  OK")

    print("\nSMOKE OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"\nSMOKE FAIL: {e}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"\nSMOKE FAIL (HTTP): {e}", file=sys.stderr)
        sys.exit(1)
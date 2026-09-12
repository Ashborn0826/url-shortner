## Why

We're building a URL shortener as Project 1 of a full-stack learning series. The goal is to teach cache-aside reads, async analytics, and rate-limiting not as abstract patterns, but as actual code in a working system. Each requirement maps to a specific system-design concept that will reappear in Project 2.

## What Changes

- New REST API for creating short URLs from long URLs (auto-generated base62 code or user-chosen custom code).
- New redirect endpoint that resolves a short code and returns 302 to the original URL.
- Redis cache-aside layer in front of Postgres for hot URLs, with explicit cache-fill + cache-miss paths.
- Per-IP rate limiting on URL creation, backed by Redis so it works across multiple API workers.
- Async click analytics pipeline: the redirect response returns immediately, the click event is enqueued and processed by a background worker that parses the user-agent and persists aggregated stats.
- React + Vite SPA with a short-URL creation form and an analytics dashboard for each short code.
- Postgres schema with a partial index optimized for the cache-miss lookup path.

## Capabilities

### New Capabilities

- `url-shortening`: Core URL service. Accepts a long URL, generates (or accepts) a short code, persists it, and serves the redirect. Owns the cache-aside pattern between Postgres and Redis.
- `rate-limiting`: Per-IP rate limit on the URL creation endpoint. Counter state in Redis so the limit holds across multiple FastAPI workers.
- `click-analytics`: Async click recording and enrichment (user-agent parse, referrer capture, timestamp). Provides aggregated stats for the dashboard.

### Modified Capabilities

None — greenfield project.

## Impact

- New backend service (Python + FastAPI) exposing REST endpoints.
- New background worker (Celery or `arq` over Redis) consuming the click queue.
- Postgres schema: `urls` and `clicks` tables; partial index on `short_code` for the redirect lookup.
- Redis used for three distinct concerns, namespaced by key prefix so they don't collide: URL cache, rate-limit counter, click queue.
- New frontend SPA (React + Vite) with two views: creation form and stats dashboard.
- New Python deps: `fastapi`, `sqlalchemy`, `alembic`, `asyncpg`, `redis-py`, `celery` or `arq`, `pydantic`, `pytest`, `httpx`.
- Local infrastructure: Postgres + Redis. Will use a `docker-compose.yml` so `docker compose up` brings the full stack online.
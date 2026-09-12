## 1. Phase 1 — Project skeleton + DB schema + CRUD API

- [x] 1.1 Create top-level `backend/`, `frontend/`, `infra/` directories and verify by running `ls` and seeing each present
- [x] 1.2 Write `backend/pyproject.toml` with deps (fastapi, sqlalchemy[asyncio], asyncpg, alembic, pydantic, redis, arq, pytest, pytest-asyncio, httpx) and verify `pip install -e '.[dev]'` succeeds in the venv
- [x] 1.3 Write `backend/app/main.py` with FastAPI app factory + `/health` endpoint and verify `uvicorn app.main:app --reload` starts and `curl localhost:8000/health` returns `200 {"status":"ok"}`
- [x] 1.4 Write `backend/app/config.py` (pydantic-settings) reading DATABASE_URL, REDIS_URL, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS and verify by importing and printing config in a smoke run
- [x] 1.5 Initialize Alembic, write first migration creating `urls` table with `short_code UNIQUE`, `long_url`, `created_at`, `is_custom` and verify `alembic upgrade head` creates the table and `alembic downgrade -1` drops it
- [x] 1.6 Implement `backend/app/shortcode.py` with `generate_code(length=7) -> str` using `secrets.choice(base62_alphabet)` and verify unit test covers length, alphabet, and uniqueness over 10k generations
- [x] 1.7 Implement SQLAlchemy `Url` model and `UrlRepository` (`create`, `get_by_code`, `code_exists`) and verify unit tests cover happy path + duplicate custom-code raises integrity error mapped to 409
- [x] 1.8 Implement `POST /api/urls` endpoint with Pydantic request validation and verify integration test: valid request returns 201 with `short_code`; bad URL returns 422; duplicate custom_code returns 409
- [x] 1.9 Implement `GET /{short_code}` redirect (DB-only, no cache yet) and verify integration test: known code returns 302 with correct Location; unknown code returns 404
- [x] 1.10 Phase 1 verification: `pytest -q` from `backend/` runs all unit + integration tests, all green; write `notes/phase-1-explanation.md` summarizing what was built and the system-design concepts (request/response shape, schema-first design, idempotency of creation)

## 2. Phase 2 — Redis cache-aside + per-IP rate limiting

- [x] 2.1 Add `backend/app/cache/redis_client.py` exposing `get_redis()` returning a configured `redis.asyncio.Redis` and verify unit test confirms the client connects to a running Redis (use `fakeredis` if real Redis absent)
- [x] 2.2 Add `backend/app/cache/url_cache.py` with `get_cached_url(code)`, `set_cached_url(code, payload, ttl=3600)`, `invalidate(code)` and verify unit tests cover hit, miss, JSON round-trip
- [x] 2.3 Wire cache-aside into `GET /{short_code}` and verify integration test: first request is a cache miss + DB read; second request is a cache hit + no DB query (assert via SQLAlchemy event listener counting SELECTs)
- [x] 2.4 Add `backend/app/middleware/rate_limit.py` with `RateLimiter` middleware that uses Redis `INCR rl:{ip}` + `EXPIRE` and verify unit tests cover under-limit, at-limit, over-limit (returns 429 with Retry-After)
- [x] 2.5 Apply the middleware to `POST /api/urls` only (not the redirect) and verify integration test: 11th request from one IP returns 429
- [x] 2.6 Spin up 2 uvicorn workers in a subprocess-based test and verify the rate limit is enforced across both workers (assert that combined requests from one IP stop at N)
- [x] 2.7 Phase 2 verification: `pytest -q` all green; write `notes/phase-2-explanation.md` covering cache-aside tradeoffs, why we picked cache-aside over read-through, and the multi-worker rate-limit invariant

## 3. Phase 3 — Async click analytics pipeline

- [ ] 3.1 Add second Alembic migration creating `clicks` table and `(url_id, clicked_at DESC)` index and verify `alembic upgrade head` applies cleanly
- [ ] 3.2 In `GET /{short_code}` handler, after sending 302, enqueue JSON `{short_code, ts, referrer, user_agent}` via `LPUSH clicks:queue` (fire-and-forget) and verify the redirect still responds under 50ms with Redis empty/unreachable
- [ ] 3.3 Add `backend/app/analytics/ua.py` wrapping `user-agents` PyPI lib and verify unit tests parse Chrome/Firefox/Safari/iOS-Android correctly
- [ ] 3.4 Add `backend/app/worker.py` with `arq.WorkerSettings` defining the `process_click(ctx, event)` function: parse UA, INSERT click row, log success; verify unit test runs `process_click` against an in-memory event and asserts DB row exists
- [ ] 3.5 Configure arq retry policy (3 attempts, exponential backoff 1s/4s/16s) and DLQ key `clicks:dlq` and verify unit test: event that always fails is moved to DLQ after 3 attempts
- [ ] 3.6 End-to-end integration test: spin worker in a subprocess, hit redirect 100 times, wait up to 5s, assert exactly 100 `clicks` rows exist
- [ ] 3.7 Phase 3 verification: `pytest -q` all green; write `notes/phase-3-explanation.md` covering why we accept duplicate clicks (no idempotency key), why arq over plain Redis list, and what "best-effort" means for analytics

## 4. Phase 4 — Stats endpoint + React + Vite frontend

- [ ] 4.1 Add `GET /api/urls/{short_code}/stats` returning `{total_clicks, clicks_by_day, top_referrers, top_browsers}` and verify unit tests cover each aggregate (use a seeded fixture DB)
- [ ] 4.2 Add CORS middleware allowing `http://localhost:5173` and verify `curl -H "Origin: http://localhost:5173" -i ...` returns the right `Access-Control-Allow-*` headers
- [ ] 4.3 Scaffold frontend: `npm create vite@latest frontend -- --template react-ts` and verify `cd frontend && npm run dev` serves on `:5173`
- [ ] 4.4 Build `<CreateUrlForm />` component calling `POST /api/urls` and showing the resulting `short_url`; verify by running the dev server and submitting a URL manually + a Vitest component test
- [ ] 4.5 Build `<StatsDashboard code={...} />` component calling `GET /api/urls/{code}/stats` and rendering total + day bars + top lists and verify by Vitest component test using MSW to mock the API
- [ ] 4.6 Phase 4 verification: `pytest -q` all green in both `backend/` and `frontend/`; write `notes/phase-4-explanation.md` covering read-time vs write-time aggregation and the SPA/backend separation

## 5. Phase 5 — Docker compose + final verification

- [ ] 5.1 Write `infra/docker-compose.yml` with Postgres 15 and Redis 7 services and verify `docker compose up -d` brings both healthy
- [ ] 5.2 Write `backend/.env.example` with sane defaults (DATABASE_URL pointing at compose service, REDIS_URL likewise, rate-limit defaults)
- [ ] 5.3 Add `backend/scripts/smoke.py` that exercises POST/GET/stats end-to-end against the compose stack and exits non-zero on any failure
- [ ] 5.4 Final verification: run `openspec validate add-url-shortener --strict` then `pytest -q` then the smoke script; commit the spec artifacts + code per the project's git workflow
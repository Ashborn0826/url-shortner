# URL Shortener

A full-stack URL shortener with cache-aside reads, per-IP rate limiting, async click analytics, and a React dashboard. Built as a learning project to demonstrate system-design concepts (cache-aside, async pipelines, idempotency, retry/DLQ, rate limiting) using the OpenSpec spec-driven workflow.

## Features

- **REST API** for creating short URLs (`POST /api/urls`) and redirecting (`GET /{short_code}`)
- **Custom short codes** — pick your own vanity URL (e.g. `docs`) if available
- **Cache-aside** on the redirect path — hot URLs never touch Postgres
- **Per-IP rate limiting** on creation, held across multiple FastAPI workers
- **Async click analytics** — redirect returns immediately; click is enqueued, parsed, and persisted by a background worker
- **Retry + dead-letter queue** for click processing (3× exponential backoff, then DLQ for manual inspection)
- **Stats endpoint** — total clicks, 30-day bar chart, top referrers, top browsers
- **React + Vite frontend** — short-URL form + stats dashboard, served on `:5173`

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic |
| Frontend | React 19, TypeScript, Vite, Vitest, @testing-library/react |
| Storage | Postgres 15 (production), SQLite (tests) |
| Cache + queue + rate limit | Redis 7 |
| Worker | asyncio + raw Redis list (LPUSH/BRPOP) with retry + DLQ |
| Tests | pytest + pytest-asyncio (backend), Vitest + jsdom (frontend), fakeredis (backend) |

## Quick start (with Docker)

Prerequisites: Docker, Docker Compose, Node 18+, Python 3.11+.

```bash
# 1. Start Postgres + Redis
docker compose -f infra/docker-compose.yml up -d

# 2. Backend: install + migrate + run API + run worker (in 3 shells)
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1                  # Windows
# source .venv/bin/activate                 # Linux/macOS
pip install -e ".[dev]"
cp .env.example .env                       # tweak if needed
alembic upgrade head
uvicorn app.main:app --reload --port 8000  # API
python -m app                              # click worker (separate shell)

# 3. Frontend
cd ../frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The API is at `http://localhost:8000` and Swagger UI at `http://localhost:8000/_internal/docs`.

## Quick start (without Docker — tests only)

The backend pytest suite uses SQLite + fakeredis, no external services needed:

```bash
cd backend
.venv\Scripts\python.exe -m pytest          # 61 tests, ~5s
```

Frontend tests use Vitest + jsdom, no API needed (fetch is mocked):

```bash
cd frontend
npm test                                   # 7 tests, ~2s
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check. Returns `{"status": "ok"}` |
| `POST` | `/api/urls` | Create a short URL. Body: `{long_url, custom_code?}`. Returns `201 {short_code, short_url, long_url, created_at}`. `409` if custom code taken, `422` on validation failure, `429` if rate-limited. |
| `GET` | `/{short_code}` | Redirect to the original long URL (`302`). `404` if unknown. |
| `GET` | `/api/urls/{short_code}/stats` | Aggregated click stats: `{total_clicks, clicks_by_day, top_referrers, top_browsers, ...}`. `404` if unknown. |

### `POST /api/urls` examples

```bash
# Auto-generated short code
curl -X POST http://localhost:8000/api/urls \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://example.com/some/long/path"}'
# {"short_code":"abc1234","short_url":"http://localhost:8000/abc1234",...}

# Custom short code
curl -X POST http://localhost:8000/api/urls \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://example.com", "custom_code": "docs"}'
# {"short_code":"docs", ...}
```

## Architecture

```
+------------------+        REST          +----------------------+
| Browser (React   |  <------------------> | FastAPI (uvicorn)    |
| + Vite, :5173)   |                       | - POST /api/urls     |
|  - create form   |                       | - GET  /{code}       |
|  - stats panel   |                       | - GET  /stats        |
+--------+---------+                       +-------+-------------+
         |                                          |
         | CORS                                     |
         |                                          |
   +-----+----------------+--------------------+----+--------+
   |                      |                    |             |
   v                      v                    v             v
+-------+          +-------------+      +----------------+   +----------+
| Stats|          |  Cache-     |      |  Rate limit    |   |  Click   |
| GET  |          |  aside      |      |  INCR + EXPIRE |   |  LPUSH   |
|      |          |  Redis-first|      |  rl:{ip}       |   |  queue   |
+-------+          +-------------+      +----------------+   +----+-----+
                                                                    |
                                                                    v
                                                          +-----------------+
                                                          | Worker (asyncio) |
                                                          | BRPOP + parse UA |
                                                          | + INSERT click   |
                                                          +--------+--------+
                                                                   |
                                                                   v
                                                          +-----------------+
                                                          | Postgres         |
                                                          | urls + clicks    |
                                                          +-----------------+
```

Three Redis keyspaces stay isolated:

| Prefix    | Purpose                           | Type   |
|-----------|-----------------------------------|--------|
| `url:`    | Cache-aside for URL lookups       | string (JSON) |
| `rl:`     | Rate-limit counter per IP         | counter       |
| `clicks:` | Click queue + dead-letter queue   | list          |

## Project structure

```
01-url-shortener/
├── backend/
│   ├── app/
│   │   ├── api/             REST endpoints (urls.py, redirect.py)
│   │   ├── analytics/       ua.py, queue.py, persist.py, worker.py
│   │   ├── cache/           redis_client.py + url_cache.py (cache-aside)
│   │   ├── db/              models.py, session.py, repository.py
│   │   ├── middleware/      rate_limit.py (Redis INCR + EXPIRE dep)
│   │   ├── alembic/         migrations
│   │   ├── __main__.py      `python -m app` starts the click worker
│   │   ├── config.py        pydantic-settings (reads .env)
│   │   ├── main.py          FastAPI app factory + CORS
│   │   ├── schemas.py       Pydantic request/response models
│   │   └── shortcode.py     base62 generator (secrets.choice)
│   ├── tests/               61 pytest tests
│   ├── scripts/smoke.py     End-to-end smoke (requires docker stack)
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/      CreateUrlForm, StatsDashboard + tests
│   │   ├── test/setup.ts    Vitest + @testing-library/jest-dom
│   │   ├── App.tsx          Toggle between create form and stats
│   │   └── main.tsx         React 19 root
│   ├── package.json         (with overrides to pin vite for vitest compat)
│   └── vite.config.ts
├── infra/
│   └── docker-compose.yml   Postgres 15 + Redis 7
├── openspec/
│   ├── specs/               Main specs (url-shortening, rate-limiting, click-analytics)
│   ├── changes/archive/     2026-09-13-add-url-shortener/ (proposal + design + tasks)
│   └── config.yaml
├── notes/                   (gitignored — teaching content)
│   ├── phase-{1..5}-explanation.md
│   └── bugs.md
├── .gitignore
└── README.md
```

## Tests

```bash
# Backend — 61 tests, ~5s
cd backend
pytest

# Frontend — 7 tests, ~2s
cd frontend
npm test

# End-to-end smoke (requires Docker stack running)
python backend/scripts/smoke.py
```

## Configuration

All backend config via env vars (see `backend/.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://urlshort:urlshort@localhost:5432/urlshort` | SQLAlchemy async URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL (cache + queue + rate limit) |
| `RATE_LIMIT_REQUESTS` | `10` | Max POST `/api/urls` per IP per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window |
| `CACHE_TTL_SECONDS` | `3600` | Cache-aside TTL on `url:{code}` |
| `SHORT_CODE_LENGTH` | `7` | Length of auto-generated base62 codes |
| `API_HOST` | `http://localhost:8000` | Used to build `short_url` in responses |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allow-list |
| `DEBUG` | `false` | Enable SQLAlchemy echo (noisy; dev only) |

## OpenSpec workflow

This project was built spec-first using [OpenSpec](https://github.com/Fission-AI/OpenSpec):

- **`openspec/specs/`** — the live contract. Three capability specs: `url-shortening`, `rate-limiting`, `click-analytics`. Every pytest maps to at least one scenario in one of these.
- **`openspec/changes/archive/2026-09-13-add-url-shortener/`** — historical change with `proposal.md`, `design.md`, `tasks.md`. The full record of WHY/WHAT/HOW.
- **`openspec/config.yaml`** — schema config (`spec-driven`).

Future changes that touch these capabilities will be written as **deltas** against the live specs, then archived the same way.

## What's NOT in this README (production concerns)

This is a learning codebase. Production concerns NOT addressed:

- **TLS termination** — run behind Caddy / nginx / a cloud LB
- **Managed databases** — swap docker-compose for RDS / Cloud SQL + ElastiCache / MemoryStore
- **Authentication** — the dashboard is anonymous per spec; user accounts would be a separate change
- **Log shipping / metrics / tracing** — Prometheus + OTel exporter would be the next step
- **Horizontal worker scaling** — the worker is single-process; production would run N workers, sharded via the Redis queue
- **URL editing / deletion / expiration** — out of scope for v1 (URLs are immutable)
- **Negative caching on 404s** — small DoS surface; acceptable for our scale; documented in `design.md`

Each of these is a separate change with its own OpenSpec change proposal.

## Lessons learned (the bugs that taught us)

While building this, four real bugs surfaced (full write-ups in `notes/bugs.md`):

1. **`pool_size`/`max_overflow` rejected by SQLite** — `StaticPool` doesn't take pool args; one factory has to handle multiple dialects.
2. **Catch-all `IntegrityError` → "duplicate"** — would have masked every other constraint violation. Fix: inspect the underlying error code before mapping.
3. **`BIGINT PRIMARY KEY` doesn't auto-fill on SQLite** — SQLite only ROWID-aliases the literal type name `INTEGER`. Fix: `BigInteger().with_variant(Integer(), "sqlite")`.
4. **FastAPI `/docs` shadows `/{short_code}` redirects** — framework defaults at root collide with our root-level route. Fix: move Swagger UI to `/_internal/*`.

The general lesson: **the catch-all is the most dangerous pattern**, because it hides the other bugs.

## License

MIT (educational use).
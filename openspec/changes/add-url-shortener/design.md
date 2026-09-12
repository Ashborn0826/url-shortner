# Design — add-url-shortener

See `proposal.md` for motivation. This document covers **how** we build it.

## Context

Greenfield project. We control the stack. The architecture has three concerns that map cleanly onto three infrastructure pieces:

1. **Synchronous request path** (URL resolve) — must be sub-50ms p99. Drives the cache-aside pattern.
2. **Write-path backpressure** (click floods on a viral URL) — must not slow down the redirect. Drives the async queue.
3. **Abuse protection** (URL creation spam) — must hold across multiple API workers. Drives Redis-backed counters.

Stack is fixed by the user's selections: Python 3.11+, FastAPI, Postgres 15, Redis 7, React + Vite. Migrations via Alembic. Queue layer chosen in Decisions below.

## Goals / Non-Goals

**Goals**
- Hot-URL redirect path never touches Postgres on a cache hit.
- Click recording never blocks the redirect response.
- Rate limit holds across multiple FastAPI workers.
- Each phase of `tasks.md` produces a small, testable vertical slice.

**Non-Goals**
- Multi-tenant user accounts (analytics is anonymous in v1).
- URL editing / deletion after creation.
- Custom analytics beyond referrer + parsed user-agent (no IP, no GeoIP).
- Distributed tracing, metrics export, alerting — left for a later change.
- Production deployment story (Docker Compose for local dev only).

## Architecture Overview

```
+------------------+        REST          +----------------------+
| Browser          |  <----------------->  | FastAPI (uvicorn)    |
|  - create form   |                       |  - POST /api/urls    |
|  - stats panel   |                       |  - GET  /{code}      |
+------------------+                       |  - GET  /stats       |
                                           +----+-----------------+
                                                |
       +-----------------+----------------+-----+--------+--------------+
       |                 |                |              |              |
       v                 v                v              v              v
+-----------+    +------------------+   +-----------+   +----------+   +--------+
| Postgres  |    | Redis            |   | arq       |   | Redis    |   | Postgr.|
|  urls     |    |  url:{code}  (cache)|  | worker    |   | clicks:q |   | clicks |
|  clicks   |    |  rl:{ip}     (counter)|  | drains    |   | clicks:dlq  | (writes|
|  idx      |    |  clicks:q    (queue) |  | queue,    |   |          |   | from   |
|           |    |  clicks:dlq  (dead   |  | enriches, |   |          |   | worker)|
|           |    |              letter)|  | writes    |   |          |   |        |
+-----------+    +------------------+   +-----------+   +----------+   +--------+
    ^                                                                       
    |                                                                       
    +---------------- cache-miss path ------------------------------------+
```

Three named Redis key spaces so the three concerns never collide:

| Prefix       | Purpose                              | Type   |
|--------------|--------------------------------------|--------|
| `url:`       | Cache-aside for URL lookups          | string (JSON) |
| `rl:`        | Rate-limit counter per IP            | string (counter) |
| `clicks:`    | Click queue + dead-letter queue      | list   |

## Database Schema

Two tables, one materialized view for the daily aggregate. UUIDs are overkill here — base62 is the natural ID — so we use `BIGSERIAL` PKs and a unique index on `short_code`.

```sql
CREATE TABLE urls (
    id           BIGSERIAL    PRIMARY KEY,
    short_code   VARCHAR(32)  UNIQUE NOT NULL,
    long_url     TEXT         NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    is_custom    BOOLEAN      NOT NULL DEFAULT false
);

CREATE INDEX urls_short_code_idx ON urls (short_code);   -- already covered by UNIQUE

CREATE TABLE clicks (
    id           BIGSERIAL    PRIMARY KEY,
    url_id       BIGINT       NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    clicked_at   TIMESTAMPTZ  NOT NULL,
    referrer     TEXT,
    user_agent   TEXT,
    browser      VARCHAR(64),
    os           VARCHAR(64),
    device       VARCHAR(32)
);

CREATE INDEX clicks_url_id_clicked_at_idx ON clicks (url_id, clicked_at DESC);
```

Schema notes:
- `is_custom` is a small denormalization that lets the dashboard distinguish vanity URLs without joining extra tables. Cheap to add, hard to backfill later.
- `url_id ON DELETE CASCADE` lets an admin `DELETE FROM urls WHERE id=...` purge a URL and its click history in one shot. (We don't expose this in the API in v1.)
- `(url_id, clicked_at DESC)` composite index serves both the dashboard's "recent clicks for this code" and the `clicks_by_day` aggregation efficiently.
- We deliberately do **not** store raw IP. Privacy + spec scope.

Migrations are Alembic. `alembic upgrade head` brings a fresh DB to current schema; `alembic downgrade -1` rolls back one revision.

## API Contracts

All endpoints under the FastAPI app. CORS allows `http://localhost:5173` (Vite default) in dev.

### `POST /api/urls` — create a short URL

```
Request:
{
  "long_url": "https://example.com/some/long/path",
  "custom_code": "docs"          // optional, 3-32 chars, [A-Za-z0-9_-]
}

Responses:
201 Created
{
  "short_code": "abc1234",
  "short_url":  "http://localhost:8000/abc1234",
  "long_url":   "https://example.com/some/long/path",
  "created_at": "2026-09-12T10:00:00Z"
}

409 Conflict    { "error": "code_taken" }
422 Unprocessable  validation error (bad URL, bad custom_code)
429 Too Many Requests  + Retry-After header (rate limited)
```

### `GET /{short_code}` — redirect

```
Responses:
302 Found
  Location: <original long URL>

404 Not Found     { "error": "not_found" }
```

This is the **hot path**. Must be sub-50ms p99 on a cache hit.

### `GET /api/urls/{short_code}/stats` — dashboard data

```
200 OK
{
  "short_code":   "abc1234",
  "long_url":     "https://example.com/...",
  "total_clicks": 1234,
  "created_at":   "2026-09-12T10:00:00Z",
  "clicks_by_day": [
    { "day": "2026-09-10", "count": 50 },
    { "day": "2026-09-11", "count": 90 },
    { "day": "2026-09-12", "count": 30 }
  ],
  "top_referrers": [
    { "referrer": "google.com", "count": 70 }
  ],
  "top_browsers": [
    { "browser": "Chrome", "count": 80 },
    { "browser": "Firefox", "count": 40 }
  ]
}

404 Not Found
```

`clicks_by_day` is the last 30 days. `top_referrers` and `top_browsers` are top 5 each. `null`/empty referrer buckets into `"(direct)"`.

## Caching Strategy (cache-aside)

```
                +-----------+
GET /{code} --->| FastAPI   |
                | resolver  |
                +-----+-----+
                      |
        url:{code} GET|
                      |
                +-----v-----+        HIT (deserialize JSON, return long_url)
                |  Redis    |-------------------------+
                +-----+-----+                         |
                      | MISS                          |
                      v                                |
              +-------+-------+                        |
              |  SELECT       |                        |
              |  short_code,  |                        |
              |  long_url     |                        |
              |  FROM urls    |                        |
              |  WHERE code=? |                        |
              +-------+-------+                        |
                      |                                |
              found? +---------- NOT FOUND -> 404       |
                      |                                |
                      v                                |
              SETEX url:{code} 3600 <json>             |
                      |                                |
                      +--------------------------------+
                                  302 redirect
```

Key facts:
- **TTL = 1 hour**. Long enough that a viral URL is served from cache, short enough that ops can purge by restarting.
- **No negative caching**. An unknown code returns 404 without writing to Redis. Trade-off: a malicious flood of random codes still hits Postgres. Mitigation: rate limit applies to creation, not redirect; if needed, add a per-IP rate limit on redirect in a later change.
- **JSON value** stores `{short_code, long_url, created_at}` so the redirect path doesn't need any DB metadata.
- **Cache invalidation**: not needed in v1 because URLs are immutable. If we ever add edit, the API does a `DEL url:{code}` after the write commits.

## Queueing Strategy (async click pipeline)

```
              +-----------+        enqueue (LPUSH)        +----------------+
GET /{code}  | FastAPI   |------------------------------->| Redis list     |
   redirect  | resolver  |                                | clicks:queue   |
   returns   +-----+-----+                                +-------+--------+
   immediately                                              |
                                                            | BRPOP (worker)
                                                            v
                                                    +---------------+
                                                    | arq worker    |
                                                    |  - parse UA   |
                                                    |  - write row  |
                                                    |  - incr daily |
                                                    +-------+-------+
                                                            |
                                                  success?   |   perm. fail after 3 retries
                                                            v
                                                    +---------------+
                                                    | arq DLQ       |
                                                    | clicks:dlq    |
                                                    +---------------+
```

Choices:
- **arq** (over plain Redis list, Celery, or RQ). arq is async-native — runs in the same event-loop model as FastAPI — and has retry + DLQ built in. Celery is heavyweight and process-based; RQ lacks first-class async support.
- **Click event payload** is small JSON: `{short_code, ts, referrer, user_agent}`. We resolve `short_code -> url_id` once on the worker (single `SELECT id FROM urls WHERE short_code = ?`) rather than passing the FK across the queue boundary — keeps the event payload small and lets the cache be the source of truth for resolution.
- **Retry policy**: 3 attempts, exponential backoff `1s, 4s, 16s`. After 3 failures, arq moves the job to DLQ.
- **DLQ** is just `clicks:queue:dlq` Redis list. A separate admin task can drain it once the underlying bug is fixed. We do not auto-replay.

### Idempotency note (and why we accept duplicates)

Click events do not carry a client-supplied idempotency key — there is no client. The hazard: a worker can write the click row successfully, then crash before arq acks the job; on restart, the job runs again, producing a duplicate row.

**Decision**: accept best-effort delivery. A 1-2% duplicate rate on a viral URL is fine for analytics. The spec does not promise exactly-once.

If we ever need exactly-once, the standard fix is: API server generates a `request_id = uuid4()` per click event and inserts with `INSERT ... ON CONFLICT (request_id) DO NOTHING`. We document this in `notes/phase-3-explanation.md` as the future improvement, but don't build it now — it's a teaching point, not a v1 requirement.

## Decisions (key trade-offs)

### D1. Cache-aside vs read-through vs write-through
- **Cache-aside** (chosen): app code reads cache, falls through to DB on miss, writes back. Explicit miss path; we can decide policy per-key.
- Read-through: cache library fetches from DB on miss automatically. Less code, but the miss policy is hidden in the library — worse for teaching.
- Write-through: every write also writes cache. Coherent, but penalizes the write path. We don't write often so the cost is low, but we don't gain much either.
- **Why cache-aside**: makes the miss path visible in our own code, which is the whole teaching point. Same pattern Facebook described for memcached at scale.

### D2. arq vs plain Redis list vs Celery
- **arq** (chosen). Async-native, retry+DLQ out of the box, one extra process.
- Plain Redis list (LPUSH/BRPOP): zero dependencies but no retry, no DLQ, no concurrency controls. We'd rebuild them poorly.
- Celery: production-grade but process-based, more config, harder mental model for FastAPI users.
- **Why arq**: best fit for FastAPI's async model, smallest teaching surface for the queue concepts we care about.

### D3. Read-time aggregation vs write-time counters
- **Read-time** (chosen): dashboard query runs `SELECT ... GROUP BY day/referrer/browser` over `clicks` table.
- Write-time: each click increments Redis counters (`clicks:{url_id}:{day}`, etc.). Faster reads, harder to evolve the dashboard (every new dimension requires new counters).
- **Why read-time**: clicks per URL are bounded (a viral URL is millions, not billions) and Postgres with the `(url_id, clicked_at DESC)` index handles this fine. Easier to add "top_countries" or "clicks_by_hour" later without a backfill.

### D4. No negative caching
- See Caching Strategy above. We accept the trade-off (small DoS surface on 404 floods) in exchange for not having to design cache invalidation for a sentinel value.

### D5. Per-IP rate limit, not per-user
- v1 is anonymous — there are no users. Per-IP is the only option.
- Implementation: Redis `INCR rl:{ip}` with `EXPIRE` on first hit. The standard pattern; safe because `EXPIRE` is idempotent.

### D6. uvicorn workers (4) behind one port
- Dev: 1 worker.
- "Production-like" learning: 4 workers. Rate limit still works because Redis is shared. The 4-worker setup is the minimum where the rate-limit-across-workers spec scenario becomes non-trivial.

### D7. Short-code length = 7
- 62^7 = 3.5 trillion combinations. At 1000 URLs/sec, that's ~111 years to 50% collision.
- 6 chars (56B) is too small to be safe against birthday-collision at scale.
- **Why 7**: standard for production shorteners (bit.ly uses 7), one more char costs nothing in cache size.

### D8. Custom-code length 3-32, charset `[A-Za-z0-9_-]`
- 3 chars minimum prevents squatting (`a`, `b`, `c`) which would crowd the namespace.
- 32 chars accommodates `learn-system-design-week-3-resources` style codes.
- Charset matches URL path segment grammar; allows hyphens and underscores without percent-encoding.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Click queue grows unbounded if worker is down | Cap with `LPUSH` against `LLEN` check, alert if `LLEN clicks:queue > 100k`. Out of scope for v1 but documented. |
| Cache stampede on a newly-viral URL | Single-flight: only one DB query per cache miss. After TTL expiry, concurrent misses all hit DB once. Acceptable for v1; in production, add request coalescing or pre-warming. |
| Rate limit false positives behind a NAT'd corporate IP | Documented in API docs; can be tuned via env vars. |
| UA parser mistakes | Use a maintained library (`user-agents` PyPI package wrapping `user_agent.parse`). Pin version. |
| Postgres connection pool exhaustion under load | Use SQLAlchemy async pool with sane defaults (`pool_size=10`, `max_overflow=20`). |
| Worker dies mid-write, click row written but ack lost | Accepted best-effort duplicates. See "Idempotency note" above. |

## Migration Plan

Greenfield, so no migration of existing data. Steps:

1. `docker compose up -d` brings up Postgres + Redis.
2. `alembic upgrade head` applies the initial schema.
3. `uvicorn app.main:app --reload` starts the API.
4. `arq app.worker.WorkerSettings` starts the click worker.
5. `npm run dev` (in the frontend dir) starts the Vite dev server.

That's it. No blue/green, no feature flags — v1 has one feature.

## Open Questions

None. All decisions taken above.
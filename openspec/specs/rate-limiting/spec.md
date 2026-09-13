# rate-limiting Specification

## Purpose
Protects the URL creation endpoint from abuse by limiting how many requests a single client IP can make per rolling time window. Counter state lives in Redis so the limit holds across multiple FastAPI workers.

## Requirements

### Requirement: Per-IP rate limit on URL creation
The system SHALL enforce a per-IP rate limit on `POST /api/urls`. When a client exceeds the limit, the system SHALL respond `429 Too Many Requests`.

#### Scenario: Under the limit
- **WHEN** client IP has made fewer than `N` requests in the last `W` seconds
- **THEN** request proceeds normally

#### Scenario: Over the limit
- **WHEN** client IP has made `N` or more requests in the last `W` seconds
- **THEN** system responds `429` with a `Retry-After` header

#### Scenario: Limit holds across workers
- **WHEN** two API workers process requests from the same client IP concurrently
- **THEN** the combined count is used to decide 429, not per-worker counts

### Requirement: Configurable limits
The system SHALL read the limit value and window size from environment variables at startup, with documented defaults.

#### Scenario: Defaults applied
- **WHEN** env vars are unset
- **THEN** system uses default `N=10` requests per `W=60` seconds

#### Scenario: Custom values from env
- **WHEN** env vars `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` are set
- **THEN** system uses those values at startup

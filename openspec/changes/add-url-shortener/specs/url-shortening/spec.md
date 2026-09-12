## Purpose

The core URL service: accepts a long URL, produces a short code, persists the mapping, and resolves short codes back to the original URL on redirect. Owns the cache-aside pattern between Postgres and Redis so hot URLs never touch the database.

## ADDED Requirements

### Requirement: Create short URL from long URL
The system SHALL accept a long URL via `POST /api/urls` and return a short code. The default short code SHALL be a base62 string of length 7 generated to be unique with collision retries.

#### Scenario: Auto-generated short code
- **WHEN** client POSTs `{"long_url": "https://example.com/some/long/path"}`
- **THEN** system responds `201` with `{"short_code": "<7-char base62>", "short_url": "http://<host>/<short_code>", "long_url": "https://example.com/some/long/path"}`
- **AND** the short code is unique in the system

#### Scenario: Custom short code
- **WHEN** client POSTs `{"long_url": "https://example.com", "custom_code": "docs"}`
- **THEN** system responds `201` with `short_code == "docs"`
- **AND** `custom_code` MUST be 3-32 characters, `[A-Za-z0-9_-]` only

#### Scenario: Custom code collision
- **WHEN** client POSTs a `custom_code` that already exists
- **THEN** system responds `409` with body indicating the code is taken

#### Scenario: Invalid URL
- **WHEN** client POSTs a `long_url` that is not a valid http(s) URL
- **THEN** system responds `422` with validation error

### Requirement: Resolve short code to long URL
The system SHALL resolve a short code on `GET /{short_code}` and respond with `302 Found` whose `Location` header is the original long URL.

#### Scenario: Known short code
- **WHEN** client requests `GET /abc1234`
- **THEN** system responds `302` with `Location: <original long URL>`

#### Scenario: Unknown short code
- **WHEN** client requests `GET /zzzzzzz` and no such code exists
- **THEN** system responds `404`

### Requirement: Cache-aside resolution
The system SHALL use a Redis cache-aside pattern when resolving short codes: read Redis first, fall through to Postgres on cache miss, and repopulate the cache with a TTL.

#### Scenario: Cache hit
- **WHEN** short code exists in Redis
- **THEN** system returns 302 without querying Postgres

#### Scenario: Cache miss
- **WHEN** short code is not in Redis
- **THEN** system reads from Postgres, writes the result to Redis with a TTL, and returns 302

#### Scenario: Cache miss on unknown code
- **WHEN** short code is not in Redis and not in Postgres
- **THEN** system returns 404 and does NOT write a negative-cache entry
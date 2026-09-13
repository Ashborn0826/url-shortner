# click-analytics Specification

## Purpose
Records every click on a short URL asynchronously so the redirect response stays fast. A background worker enriches each click (user-agent parsed into browser/OS/device), persists it, and exposes aggregated stats for the dashboard.

## Requirements

### Requirement: Record click asynchronously
The system SHALL enqueue a click event for every successful redirect without persisting the click inline on the request path.

#### Scenario: Redirect stays fast
- **WHEN** a short code resolves to a long URL and the user is redirected
- **THEN** the redirect response is sent before any click row is written to Postgres
- **AND** a click event containing `{short_code, timestamp, referrer, user_agent}` is enqueued

#### Scenario: Failed enqueue does not break redirect
- **WHEN** the click queue is unavailable
- **THEN** system still returns 302 to the user
- **AND** the failed enqueue is logged

### Requirement: Background enrichment and persistence
The system SHALL process click events on a background worker. The worker SHALL parse the user-agent into browser/OS/device and persist a row per click, plus increment aggregated counters.

#### Scenario: Worker dequeues a click
- **WHEN** worker picks up a click event
- **THEN** it parses user-agent, writes a `clicks` row, and increments the per-short-code daily counter

#### Scenario: Worker retries on transient failure
- **WHEN** Postgres write fails with a transient error
- **THEN** worker retries with exponential backoff up to N attempts
- **AND** on permanent failure, the event is moved to a dead-letter list in Redis

### Requirement: Aggregated stats for dashboard
The system SHALL expose `GET /api/urls/{short_code}/stats` returning aggregated analytics for that code.

#### Scenario: Stats response shape
- **WHEN** client requests `GET /api/urls/abc1234/stats`
- **THEN** system responds `200` with `{total_clicks, clicks_by_day: [...], top_referrers: [...], top_browsers: [...]}`

#### Scenario: Unknown code
- **WHEN** client requests stats for a non-existent code
- **THEN** system responds `404`

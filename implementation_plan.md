# Implementation Plan — Phase 0: Accumulate Before the App

**Stack:** Python core + JS frontend (frontend deferred; Phase 0 is ingestion-only).
**Goal (PRD §17):** *Start the clock on the moat.* Stand up the day-0 wait-time poller and the history tables **before the app exists**, so perishable observations (§7.6) begin accumulating immediately.

## Scope of Phase 0
- Day-0 **wait-time poller** against Queue-Times (free, attribution-required — PRD §8.2).
- **History tables** committed from day 1 (PRD §7.6): `wait_time_history` (live) + schema **stubs** for offers / flight prices / room prices / DVC availability.
- **Ports & Adapters** shape (PRD §2.3): a driven `WaitTimesSource` port + `WaitTimeRepository` port; Queue-Times and Postgres are adapters.
- **Scheduler/worker** container (PRD §13) running the poller on an interval. n8n is the eventual home; a self-contained APScheduler worker keeps Phase 0 testable.
- **Docker Compose:** Postgres (durable store, schema auto-loaded), Redis (present for later phases), Open-Meteo self-host service (profile-gated), poller worker.

## Design tenets honored
- **Tenant-free natural keys / append-only history** (§7.3, §7.5): `wait_time_history` is append-only, unique on `(source, park_id, ride_id, observed_at)` → idempotent re-polls, no user/tenant in the key.
- **Error isolation + retry** (§13, §18): one flaky park degrades to a *gap*, not a total-run failure; per-park try/except with exponential backoff.
- **Fail loud, never silent-bucket** (§18): unknown park name / unparseable timestamp raises, never silently coerced.

## Files
```
[NEW] pyproject.toml                     # package + deps (httpx, psycopg3, apscheduler)
[NEW] Dockerfile                         # worker image
[NEW] docker-compose.yml                 # postgres + redis + open-meteo + poller
[NEW] .env.example                       # config surface
[NEW] db/schema.sql                      # wait_time_history + stub history tables
[NEW] src/moat/__init__.py
[NEW] src/moat/config.py                 # env-driven Config
[NEW] src/moat/models.py                 # WaitObservation dataclass
[NEW] src/moat/ports/__init__.py
[NEW] src/moat/ports/wait_times.py       # WaitTimesSource + WaitTimeRepository protocols
[NEW] src/moat/adapters/__init__.py
[NEW] src/moat/adapters/queue_times.py   # Queue-Times adapter (fail-loud parsing)
[NEW] src/moat/db.py                      # PgWaitTimeRepository (append + ON CONFLICT DO NOTHING)
[NEW] src/moat/ingest/__init__.py
[NEW] src/moat/ingest/wait_poller.py     # poll_once: error isolation + retry
[NEW] src/moat/scheduler.py              # APScheduler entrypoint (moat-poll)
[NEW] tests/test_queue_times.py          # parse + fail-loud (httpx MockTransport, no network)
[NEW] tests/test_wait_poller.py          # error isolation + retry (fakes, no DB)
```

## Verification
`pip install -e .[dev] && pytest` — tests use `httpx.MockTransport` and in-memory fakes, so they pass with **no live network and no Postgres**.

## Explicitly NOT in Phase 0
Domain core, Field Registry, MCDA, chat, paywall, tenancy, real Open-Meteo reanalysis sync (image ships; data sync is an infra step documented, not coded here). These are Phases 1–5.

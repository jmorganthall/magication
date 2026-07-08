# magication

Vacation Research & Planning Platform. See [`PRD.md`](./PRD.md) for the full architecture.

## Phase 0 — Accumulate before the app

The moat starts before the app exists (PRD §17). A wait-time poller banks perishable
observations into append-only history tables so the proprietary dataset accrues from day 0.

- **Poller:** `src/moat/` — Queue-Times adapter → per-park error-isolated poll → Postgres history.
- **Schema:** `db/schema.sql` — `wait_time_history` (live) + stub tables for offers / flight prices /
  room prices / DVC availability (§7.6).
- **Layout:** ports & adapters (`ports/` interfaces, `adapters/` + `db.py` implementations).

### Run

```bash
docker compose up            # postgres + redis + poller (schema auto-loads)
```

### Develop / test

```bash
pip install -e .[dev]
pytest                       # no network, no DB required (MockTransport + fakes)
```

Configuration surface: see [`.env.example`](./.env.example).

### Attribution

Wait-time data via [Queue-Times.com](https://queue-times.com) (attribution required by their terms).

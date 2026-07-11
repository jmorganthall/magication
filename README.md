# magication

**A structured, repeatable engine for planning Disney / Universal (and beyond) vacations.**

Planning a theme-park trip today means pulling together weather, crowd levels, school and
custody calendars, offers, DVC availability, flight prices, ticket and parking costs, Lightning
Lane options, and nearby events — by hand, from scratch, every time. `magication` turns that ad
hoc process into a **deterministic decision model** with a **conversational layer that can
manipulate it** ("but what if we changed to January?" / "what would Lightning Lane Premier cost?").
It works *backward* from a defensible ranked recommendation instead of forward from a blank page.

> **Status:** pre-alpha · **Phase 0 (Accumulate)** in progress · see the [roadmap](#roadmap).
> The full architecture lives in **[`PRD.md`](./PRD.md)** — this README is the short version.

---

## What it is

A trip-decision engine that ranks **candidates** — every `(destination × week × accommodation)` —
on a small, auditable set of objectives (cost, crowd, weather, events, offers) and explains *why*
each one ranks where it does. You give it fuzzy constraints ("sometime in spring, kids can't miss
the gymnastics meet, budget around $6k"); it gives you a ranked, legible set of trips, each with a
cost breakdown and a bookable next step.

## What it will be

One architecture, two audiences (**not** two codebases):

- **Personal tier (now):** the owner's own trip planning.
- **Product tier (later):** a sellable multi-tenant SaaS — Disney/Universal travel agents above all.

The difference is which **adapters** plug into the data ports, not a fork of the app.

## How it works

Five ideas carry the whole design (details in the PRD sections linked):

| Principle | In one line | PRD |
|---|---|---|
| **Deterministic core, AI at the edges** | Scoring is auditable arithmetic; an LLM never computes it. AI is scoped to 3 zones only: intake parsing, unstructured matching, narrative. | §2, §11 |
| **Ports & Adapters (Hexagonal)** | A pure domain core knows nothing about weather APIs, Postgres, or the UI — every external thing is an adapter behind a port. | §2, §3 |
| **Classify each datum once** | Tag a datum's *volatility* × *shared-ness* once and its cache, its store, and its paywall side all fall out. | §4, §7 |
| **The Field Registry is the keystone** | One registry of every fillable field powers NL resolution, validation, the recompute graph, paywall gating, and metering. | §6 |
| **Chat emits operations; it never edits state** | The LLM proposes constrained operations against the registry; a deterministic engine validates, applies, and recomputes. Simulate is the default. | §10 |

Scoring is **Multi-Criteria Decision Analysis** (weighted sum / TOPSIS + Pareto filtering) — the
"what jumps out" quadrant is really a Pareto frontier over cost/crowd/weather. Monetization follows
a **maturity ladder** (L0 season-browse → L3 book-and-monitor) with the paywall exactly where
per-user marginal cost jumps from ~zero to real (L1→L2).

## Roadmap

Phases are boundaries — each independently shippable (PRD §17).

| Phase | Focus | State |
|---|---|---|
| **0 — Accumulate** | Day-0 wait-time poller + history tables + Open-Meteo self-host. *Start the moat before the app exists.* | ✅ shipped |
| **1 — Deterministic spine** | Domain core, Field Registry, MCDA scoring, recompute cascade, completeness validator, Trip document + operation log. | 🟡 in progress |
| **2 — Data adapters + caching** | Weather, crowd (wait proxy), tickets; cache/meter/route decorators; cache-key discipline + lead-time TTL. | ⚪ planned |
| **3 — Conversational layer** | Chat-as-operation-emitter, simulate/commit/branch, edit-or-direct rule, form + chat as dual drivers. | ⚪ planned |
| **4 — L2 paywall + metered adapters** | DVC (personal tier), flights, live rates/offers; metered-action warnings; rate-card CSVs. | ⚪ planned |
| **5 — Multi-tenancy + B2B** | Pool/silo tiers, SSO, agency roles, per-tenant billing, client-shareable proposals. | ⚪ planned |

### Phase 0 — what's built now

A wait-time poller banks **perishable observations** into **append-only history tables** so the
proprietary dataset accrues from day 0 (PRD §7.6, §8.2). This is the moat: usage → data → better
models → better product.

- **Poller** (`src/moat/`) — Queue-Times adapter → per-park **error-isolated** poll (one flaky park
  degrades to a gap, not a total-run failure) → Postgres history.
- **Schema** (`db/schema.sql`) — `wait_time_history` (live) + stub tables for offers / flight prices
  / room prices / DVC availability, shipped now so no capturable data is lost.
- **Shape** — ports & adapters: `ports/` interfaces, `adapters/` + `db.py` implementations.

## Repository layout

```
PRD.md                     # the full product requirements document (source of truth)
implementation_plan.md     # active phase plan
db/schema.sql              # history tables (Phase 0) — append-only, tenant-free keys
db/migrations/             # forced-RLS tenancy floor (Phase 1)
inputs/rate_card.csv       # editable rate constants (a rate change is a data edit)
src/moat/                  # Phase 0 — the accumulation layer (ingestion)
  ports/wait_times.py      # WaitTimesSource + WaitTimeRepository (the hexagonal boundary)
  adapters/queue_times.py  # Queue-Times adapter (fail-loud parsing)
  ingest/wait_poller.py    # poll_once — error isolation + backoff retry
  scheduler.py             # APScheduler worker entrypoint (`moat-poll`)
src/core/                  # Phase 1 — the pure deterministic domain core
  registry.py, fields.yaml # the Field Registry (keystone): aliases, validation, the DAG
  trip.py, operations.py   # Trip document + operation model/log (chat emits ops, never edits)
  cascade.py               # recompute cascade + completeness validator (fail-loud, §6.3)
  mcda.py, solve.py        # MCDA scoring (weighted-sum/TOPSIS/Pareto) + solve engine
  decision.py              # the structured decision object (never prose)
tests/                     # Phase 0 + core suites (no network, no DB)
Dockerfile, docker-compose.yml, .env.example   # the deployment template
```

## Quickstart

### Run the stack (Docker)

```bash
cp .env.example .env      # optional — sane defaults work out of the box
docker compose up         # postgres + redis + poller (schema auto-loads on first boot)
```

Add the self-hosted weather service when you need it:

```bash
docker compose --profile weather up
```

The stack ([`docker-compose.yml`](./docker-compose.yml)) — every value defaults, so `up` works
with no `.env`, and everything is overridable:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-moat}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-moat}
      POSTGRES_DB: ${POSTGRES_DB:-moat}
    ports: ["${POSTGRES_PORT:-5432}:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro   # loads once
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-moat} -d ${POSTGRES_DB:-moat}"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:                       # ephemeral TTL cache (PRD §7.2)
    image: redis:7
    command: ["redis-server", "--save", "", "--appendonly", "no"]
    ports: ["${REDIS_PORT:-6379}:6379"]

  poller:                      # the day-0 wait-time poller (`moat-poll`)
    build: .
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-moat}:${POSTGRES_PASSWORD:-moat}@postgres:5432/${POSTGRES_DB:-moat}
      POLL_INTERVAL_SECONDS: ${POLL_INTERVAL_SECONDS:-300}
    depends_on:
      postgres:
        condition: service_healthy   # waits for the healthcheck, not just container start
    restart: unless-stopped

volumes:
  pgdata:
```

The full file adds a profile-gated Open-Meteo service, a bridge network, and Redis healthchecks —
see [`docs/DOCKER.md`](./docs/DOCKER.md) for the complete template reference (services, env vars, ops).

### Develop & test

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest                    # 34 tests, no network and no DB required (MockTransport + fakes)
```

## Configuration

All configuration is environment-driven — see [`.env.example`](./.env.example). App-level knobs:
`DATABASE_URL`, `QUEUE_TIMES_PARK_IDS`, `POLL_INTERVAL_SECONDS`, `HTTP_TIMEOUT_SECONDS`, `MAX_RETRIES`.

## Releasing

`magication-moat` publishes to PyPI on every push to `main` via GitHub Actions (setuptools-scm
versioning + OIDC trusted publishing). One-time PyPI setup is documented in [`RELEASING.md`](./RELEASING.md).

## Data sources & attribution

Wait-time data is served via [Queue-Times.com](https://queue-times.com) (attribution required by
their terms). Weather uses [Open-Meteo](https://open-meteo.com) (CC BY 4.0). Source-by-source terms
and the personal-vs-product-tier fault line are catalogued in PRD §8.

## License

TBD — not yet licensed for redistribution.

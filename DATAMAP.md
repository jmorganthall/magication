# DATAMAP — First-Class Objects

**Status:** living document · keep in sync with the code (see [Maintenance contract](#maintenance-contract)).
**Purpose:** the single canonical catalog of every first-class object in the system — what it is,
who owns its values, where it lives, and the invariants it MUST satisfy. If a noun is passed
between modules, persisted, or reasoned about by the engine or the AI, it belongs here.

This complements two other artifacts:
- **[`PRD.md`](./PRD.md)** — *why* the architecture is shaped this way (sections referenced as §N).
- **[`src/core/fields.yaml`](./src/core/fields.yaml)** — the machine-readable registry of *fillable fields*
  (a subset of the objects here: the leaf values a human or adapter provides). DATAMAP is the wider
  map of aggregates, records, ports, and enums that those fields live inside.

## Legend

- **Kind** — `value-object` · `aggregate` · `entity` (persisted, has identity) · `record` (append-only
  history row) · `reference-data` · `port` (interface) · `adapter` · `enum/ladder` · `service`.
- **Authority** — who is allowed to write the value: `user` · `engine` (deterministic derivation) ·
  `adapter` (fetched) · `system` (infra). Maps to the provenance firewall (§6.1).
- **Volatility × Shared-ness** — the §7 taxonomy tag that decides store + cache + paywall side.
- **Status** — ✅ implemented (phase) · ⚪ planned (phase).

> **The firewall, once (§6.1):** every value's authority is fixed. `user` values are the ONLY ones an
> operation (form or chat) may set. `engine` values come only from the recompute cascade. `adapter`
> values come only from a port. Nothing crosses these lines — most of the invariants below restate it.

---

## A. Core domain objects (`src/core/`) — ✅ Phase 1

### Field (`FieldSpec`)
- **Kind:** value-object · **Home:** `registry.py`, declared in `fields.yaml`
- **What:** one human-fillable field as a first-class registered entity — the keystone (§6).
- **Attributes:** `path` (canonical address) · `type` (enum|int_range|number|currency|date…) ·
  `provenance` · `domain` · `aliases` · `description` · `depends_on` · `maturity_level` · `cost_to_obtain`.
- **Invariants:**
  - `path` is globally unique; every alias (and the path itself) resolves to exactly one field — an
    alias collision is a **load-time error**, never last-write-wins.
  - `USER_INPUT` fields MUST NOT declare `depends_on`; `DERIVED`/`FETCHED` MUST.
  - every `depends_on` target must be a registered path; the resulting graph must be **acyclic**.

### FieldRegistry
- **Kind:** service (immutable catalog) · **Home:** `registry.py`
- **What:** the one registry that powers NL resolution, validation, the recompute DAG, paywall gating,
  and metering (§6.2). Five systems, one artifact.
- **Invariants:** loaded once and treated as immutable at runtime; alias resolution is
  case-insensitive; exposes a single topological order used by the cascade.

### Trip (the Trip document)
- **Kind:** aggregate · **Authority:** mixed (per-field) · **Home:** `trip.py` (in-memory);
  persisted as the `trip` entity (§C)
- **What:** the **one source of truth** for a trip. Form and chat are two driving adapters over it (§10.6).
- **Attributes:** map of `path → Value`.
- **Invariants:**
  - `USER_INPUT` paths are set only via operations; `DERIVED`/`FETCHED` only via the cascade/adapters.
  - `branch()` is **copy-on-write** — a simulation never mutates the baseline (§10.4).
  - hydrated from live state each turn — the chat agent never reasons off a stale snapshot (§10.6).

### Value
- **Kind:** value-object (frozen) · **Home:** `trip.py`
- **What:** one cell of a Trip: `value` + `provenance` + `origin`.
- **Attributes:** `origin ∈ {user, ai-proposed, engine, fetched}`.
- **Invariants:** an AI-originated edit is tagged `ai-proposed` and **never masquerades** as a user
  assertion; the user can always see "AI changed this" and revert (§10.6).

### Operation
- **Kind:** value-object (command) · **Home:** `operations.py`
- **What:** the only way state changes — chat/UI emit operations, they never edit state (§10).
- **Attributes:** `kind ∈ {read, simulate_set, commit_set}` · `path` · `value` · `actor ∈ {user, ai}`.
- **Invariants:** a SET may target **only `USER_INPUT`** (firewall — `ForbiddenOperation` otherwise);
  `simulate` is the default; applying runs the recompute cascade and returns a diff.

### OperationLog
- **Kind:** aggregate (append-only) · **Home:** `operations.py`; persisted as `trip_operation` (§C)
- **What:** trip state = **a fold over its operation log** (§10.5) — free undo, audit, replay.
- **Invariants:** only `COMMIT_SET` operations are recorded; `fold()` reconstructs a Trip from empty;
  `undo()` drops the last committed op.

### Candidate
- **Kind:** value-object · **Home:** `candidate.py`
- **What:** a `(destination × week × accommodation)` the solve engine ranks (§4.1).
- **Attributes:** `id` · `destination` · `week` (ISO date) · `accommodation`.

### CandidateFacts
- **Kind:** value-object · **Authority:** adapter · **Volatility × Shared:** slow/fast **shared**
  (per §7) · **Home:** `candidate.py`
- **What:** the per-candidate facts the feature vector is built from.
- **Attributes:** `base_cost` · `crowd_index` (lower better) · `weather_score` (higher better).
- **Status:** ✅ in-memory (Phase 1) → ⚪ real weather/crowd adapters behind `FactsProvider` (Phase 2).

### Rule (formula / fetcher)
- **Kind:** value-object · **Home:** `formulas.py`
- **What:** a computed field's contract: the `inputs` it reads + the pure `fn` that folds them.
- **Invariants:** `set(rule.inputs) == set(field.depends_on)` — enforced by the **completeness
  validator** (§6.3); a mismatch fails loud. `fn` is pure: same inputs → same output, always.

### RateCard
- **Kind:** reference-data · **Authority:** user (data edit) · **Home:** `inputs/rate_card.csv`
- **What:** editable rate constants (ticket base/overhead, LL per-tier price) — a rate change is a
  **data edit, not a code deploy** (§18).
- **Invariants:** a missing key fails loud (never a silent default that corrupts cost math).

### MCDA objects — Criterion, DecisionObject, ScoredCandidate, Dimension
- **Kind:** value-objects · **Home:** `mcda.py`, `decision.py`
- **Criterion:** `key` · `weight` · `maximize`.
- **DecisionObject:** `method` · `weights` · `ranked[]` · `pareto_front[]`. The engine's primary output
  is this **structured object, never prose** (§4.5) — UI and agent proposal are two renderers over it.
- **ScoredCandidate:** `candidate` · `total_cost` · `crowd_index` · `weather_score` · `score` · `rank`
  · `on_pareto_front` · `dimensions[]`.
- **Dimension:** `key` · `raw` · `normalized` · `weight` — score decomposed so the ranking is legible.
- **Invariants:** no AI anywhere in scoring; re-ranking on new weights uses cached facts, **no
  re-fetch** (CQRS, §4.6).

---

## B. Enums & ladders — ✅ Phase 1

### Provenance — `USER_INPUT | DERIVED | FETCHED`
The firewall (§6.1). Fixes each field's authority; see the callout above.

### Maturity ladder — `L0 | L1 | L2 | L3`
The cost gradient (§9). L0 season-browse (≈free) → L1 shape-the-window (account) → **L2 real rates
(PAYWALL)** → L3 book & monitor (subscription). The paywall sits at **L1→L2**, where marginal
cost per user jumps from ~zero to real. A field's `maturity_level` + `cost_to_obtain` drive gating.

### CostToObtain — `free_shared | cached | metered`
Per-field metering class (§6). `metered` fields are the ones that cost real money per user.

### IsolationTier — `pool | silo`
Per-tenant isolation (§12.3). `pool` = shared DB + RLS (default, scales to the free funnel);
`silo` = dedicated schema/db for an enterprise client. Promotion is a provisioning action, not a
code change (persistence is behind a port).

---

## C. Tenancy & identity — ✅ SQL floor (Phase 1), ⚪ app wiring (Phase 5)

Home: [`db/migrations/0002_tenancy_rls.sql`](./db/migrations/0002_tenancy_rls.sql). All four tables are
under **forced, fail-closed RLS** (§12.2): no `app.tenant_id` context ⇒ **zero rows, never all rows**.

### Tenant
- **Kind:** entity · **Attributes:** `id` · `name` · `isolation` (pool|silo).
- **Invariants:** the **isolation AND billing boundary**; a B2C signup mints a tenant-of-one; every
  user belongs to exactly one tenant.

### User (`app_user`)
- **Kind:** entity · **Attributes:** `id` · `tenant_id` · `email` · `role`.
- **Invariants:** unique `(tenant_id, email)`; belongs to exactly one tenant.

### Trip (persisted)
- **Kind:** entity · **Attributes:** `id` · `tenant_id` · `maturity` · `state` (JSONB) · timestamps.
- **Relationship:** the persisted form of the in-memory **Trip document** (§A). Storage grows with
  maturity (§9): L0 persists nothing per-user; L1 creates the row; L2 hardens it with fetched-rate
  snapshots.

### TripOperation (`trip_operation`)
- **Kind:** record (append-only) · **Attributes:** `id` · `tenant_id` · `trip_id` · `seq` · `kind` ·
  `path` · `value` (JSONB) · `actor` · `created_at`.
- **Invariants:** unique `(trip_id, seq)`; the persisted **OperationLog** — trip state folds from it.

---

## D. Perishable data & history — ✅ `wait_time_history` (Phase 0); others are shipped stubs

Home: [`db/schema.sql`](./db/schema.sql). These capture **perishable observations** — unrecoverable if
not banked as they happen, and the moat (§7.6). **Cache-key discipline (§7.3): keys are the intrinsic
natural key of the shared dimension and EXCLUDE tenant/user.**

### WaitObservation → `wait_time_history` — ✅ Phase 0
- **Kind:** record · **Authority:** adapter · **Volatility × Shared:** fast **shared** (Redis serve +
  Postgres history) · **Home:** `src/moat/models.py` (in-flight) + table.
- **Attributes:** `park_id` · `park_name` · `ride_id` · `ride_name` · `is_open` · `wait_minutes` (NULL
  when closed) · `source` · `observed_at` · `ingested_at`.
- **Invariants:** append-only; idempotent via unique `(source, park_id, ride_id, observed_at)`; no
  tenant in the key.

### Stub history records — ⚪ (schema shipped, adapters later)
Same append-only, tenant-free, perishable discipline. Shipped now so no capturable data is lost.
- **OfferRecord → `offer_history`** — offer/promo snapshots (adapter Phase 4).
- **FlightPriceRecord → `flight_price_history`** — origin/dest/dates → price (adapter Phase 4).
- **RoomPriceRecord → `room_price_history`** — resort/room/date → price (adapter Phase 4).
- **DVCAvailabilityRecord → `dvc_availability_history`** — "X available for date D at occupancy O, as
  seen on T" (§8.4). `room_type` is SKU-derived and MUST **fail loud** on an unknown SKU, never silent
  `UNK` (§18). Adapter Phase 4 (personal tier).

---

## E. Ports & adapters (the boundary objects)

Every external dependency is an adapter behind a port (§2.3, §3). The driven-adapter edge hosts three
cross-cutting decorators — **cache · meter · route** — declared per adapter as policy (§3).

### Implemented — Phase 0 / Phase 1
- **`WaitTimesSource`** (port) → **`QueueTimesSource`** (adapter) — `src/moat/`. Fail-loud parsing.
- **`WaitTimeRepository`** (port) → **`PgWaitTimeRepository`** (adapter) — append-only persistence.
- **`FactsProvider`** (port) → **`InMemoryFactsProvider`** — `src/core/candidate.py` (Phase 1 stand-in).

### Planned ports — each a first-class boundary
| Port | Feeds | Redistribution / tier | Phase |
|---|---|---|---|
| Weather | climatology (expectation+variance) | Open-Meteo CC BY — **both tiers** | 2 |
| Crowd | wait proxy now; predictive model later | attribution feeds — own-by-accumulation | 2 |
| Tickets | ticket price + affiliate revenue | Undercover Tourist AWIN — **both** | 2 |
| DVC | availability + rental cost | unofficial endpoint — **personal only** (§8.4 OPEN) | 4 |
| Flights | L2 fetched price | Amadeus/Duffel/Kiwi — **OPEN** (§8.5) | 4 |
| Events | headline-event matching (embeddings ok) | Ticketmaster/SeatGeek/Bandsintown | 4 |
| Offers | promos (scrape) | ToS exposure for product tier | 4 |
| LLM | intake parse / matching / narrative | OpenRouter keys + BYOK, one port | 3 |
| Persistence | Postgres/Redis behind a port | pool→silo is a provisioning knob | 1/5 |

---

## Maintenance contract

This file drifts silently the moment code changes without it — which is the failure mode it exists to
prevent. Therefore:

1. **Adding/changing a first-class object** (a new aggregate, record, port, enum, or a changed
   invariant) is **not done until DATAMAP is updated in the same change.**
2. A new **fillable field** goes in `fields.yaml`; if it introduces a new *kind* of object (not just a
   leaf), catalog it here too.
3. Keep **invariants** concrete and testable — they are the contract, not decoration. Where an
   invariant is enforced in code (registry load checks, the completeness validator, RLS policies),
   say so, so a reader can find the guardrail.
4. When an object's **Status** changes (planned → implemented), update it and its Home path.

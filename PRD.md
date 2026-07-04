# Vacation Research & Planning Platform — Product Requirements Document
**Working title:** TBD (codename placeholder — decide before repo init)
**Version:** 0.1 (Draft for build)
**Status:** Foundational architecture locked; two data-source items openly unresolved (see §15)
**Audience:** Project owner + AI coding agents executing a greenfield build
**Storage:** This is a living document. Version it in the repo root alongside other instruction artifacts.
**Decision legend:**
`[LOCKED]` = decided, do not re-open without explicit sign-off · `[OPEN]` = unresolved, carried deliberately · `[V1]` = in scope for first build · `[LATER]` = deferred by design

---

## 1. Context & Vision
Today, planning a Disney / Universal (and potentially other) vacation means pulling a large amount of heterogeneous data together by hand — weather, crowd levels, family and school calendars, Disney offers, DVC availability, flight pricing, food and parking costs, Lightning Lane options, park events, nearby concerts/headline events, and off-property alternatives — then holding it all in human "context" and deciding what jumps out. It is ad hoc, repeated from scratch each time, and does not scale.

This platform makes that process structured, repeatable, and cheap. It blends a **structured, deterministic decision model** with a **conversational layer that can manipulate that model** ("but what if we changed to January?" / "what would Lightning Lane Premier cost?"). The system works backward from a defensible ranked recommendation rather than forward from an arbitrary starting point.

**Two audiences, one architecture:**
- **Personal tier (now):** the owner's own trip planning.
- **Product tier (later):** a sellable multi-tenant SaaS for others — Disney/Universal travel agents above all.

These are **not** two products. They are one architecture with different adapters plugged into the encumbered data ports (see §2, §8). This is the central structural decision that keeps the effort from forking into two codebases.

---

## 2. Guiding Principles (Design Tenets)
Everything downstream derives from these. They are the non-negotiables.

1. **Backward-chaining design method.** `[LOCKED]` We design from the required output (a ranked set of candidate trips, each with a defensible reason, a cost breakdown, and a bookable next step) and trace backward to the data required to produce it. This is Event Storming: name the domain events first, work back to commands and data. It is the mechanism that surfaces impossible corners (the "Penrose triangle" problem) *before* code, where they show up as **data-availability and licensing constraints**, not compute problems.
2. **Deterministic core, AI at the edges.** `[LOCKED]` The scoring/ranking math is low-dimensional, auditable arithmetic. An LLM never computes it — same inputs must always yield the same ranking, and we must be able to show *why*. AI is scoped to exactly three zones (§11): (a) parsing fuzzy intake into structured constraints, (b) matching genuinely unstructured long-tail data, (c) writing the "why this week" narrative. Nothing else.
3. **Ports & Adapters (Hexagonal), not MVC.** `[LOCKED]` The hard part is orchestrating a dozen heterogeneous external sources and computing a defensible decision — not rendering. A pure domain core knows nothing about weather APIs, Postgres, OpenRouter, or the UI. Every external dependency is an adapter behind a port. MVC describes only the presentation adapter and is too small to organize the system.
4. **Classify each datum once; cache policy, storage, and paywall all fall out.** `[LOCKED]` Every piece of data has two properties that matter — **volatility** (how often the value changes) and **shared-ness** (whose value it is). Tag those once and the data's cache mechanism, its storage location, and which side of the paywall it sits on are all determined. Caching and the monetization funnel are the same taxonomy viewed from two ends.
5. **The Field Registry is the keystone.** `[LOCKED]` Every human-fillable field is a first-class registered entity carrying metadata. One registry simultaneously powers natural-language resolution, schema validation, the recompute dependency graph, paywall gating, and cost metering (§6).
6. **Chat emits operations; it never edits state.** `[LOCKED]` The conversational layer proposes constrained operations against the registry's vocabulary. A deterministic engine validates and applies them and runs the recompute cascade. Simulate is the default. The LLM may only propose changes to `USER_INPUT` fields — never write `DERIVED` or `FETCHED` values (§10).
7. **The collection layer is an asset, not just a cost saving.** `[LOCKED]` Serving users cheaply *is simultaneously* building a proprietary dataset (crowd/wait history, offer/price history, DVC availability history) that nobody else has. This is a flywheel: usage → data accumulation → better models and lower cost → better product → more usage.

---

## 3. Architecture Overview
```
                       ┌─────────────────── DRIVING ADAPTERS ───────────────────┐
                       │   Web/Mobile UI (form)        Conversational layer      │
                       │        (driver A)                 (driver B)            │
                       └───────────────┬─────────────────────┬──────────────────┘
                                       │   one source of truth: the Trip document
                       ┌───────────────▼─────────────────────▼──────────────────┐
                       │                     DOMAIN CORE (pure)                  │
                       │  • Field Registry        • MCDA scoring / Pareto filter │
                       │  • Solve engine          • Recompute cascade (DAG)      │
                       │  • Operation model       • Decision object (structured) │
                       └───────────────┬─────────────────────────────────────────┘
                                       │ PORTS (interfaces)
        ┌──────────────────────────────┼───────────────────────────────────────────┐
        │  cache · meter · route  ◄── three cross-cutting decorators on this edge    │
        └──────────────────────────────┼───────────────────────────────────────────┘
                       ┌───────────────▼─────────────────────────────────────────┐
                       │                    DRIVEN ADAPTERS                       │
                       │  Weather · Crowd/Waits · Tickets · DVC · Flights ·       │
                       │  Events · Offers · LLM (OpenRouter/BYOK) · Persistence   │
                       └──────────────────────────────────────────────────────────┘
```
**The driven-adapter boundary hosts three cross-cutting decorators**, declared per-adapter as policy (not scattered through business logic):
- **cache** — reduces metered cost (§7)
- **meter** — tracks per-tenant spend, and BYOK users' own spend (§7, §11)
- **route** — picks whose key pays (BYOK vs our OpenRouter keys) (§11)

Cache reduces the metered cost; the meter tracks what's left; the router picks who pays for it. One place to reason about all of it.

---

## 4. The Domain Core
### 4.1 The candidate model
A **candidate** = (destination × week × accommodation). The solve engine ranks candidates.

### 4.2 The feature vector (per candidate)
Deterministic, computed by the core from adapter-supplied facts:
- decomposed cost (accommodation + tickets + food estimate + parking + flights + add-ons)
- crowd index (v1: deterministic wait-time proxy — §8)
- weather expectation (a **distribution**, not a number — climatology + variance)
- event bonus (nearby headline events / park events)
- offer applicability

### 4.3 Scoring — MCDA `[LOCKED]`
The cost × crowd × weather framing is formalized as **Multi-Criteria Decision Analysis**. The "quadrant" is a **Pareto frontier**; "what jumps out" is the non-dominated set; the price-vs-weather intake questions are **weight elicitation**. Use real machinery — weighted sum / TOPSIS for ranking, Pareto filtering for the frontier — not invented quadrant math. Note: with three objectives the 2×2 quadrant is a *projection*; the underlying model is a 3-objective Pareto set.

**No AI in scoring.** The score decomposition is surfaced by dimension so the recommendation is legible ("this week wins on crowd and price, loses slightly on weather").

### 4.4 The solve engine — one engine, not five `[LOCKED]` `[V1]`
Build the **flexible-window optimizer as THE core engine**. All other "modes" are degenerate cases or filters on it:
- **Hard dates** → a search space of one.
- **Duration-only** ("5 days", "4 park days") → the same engine over a wider window.
- **Budget-anchored / event-anchored** → filters on that search, not separate modes.

### 4.5 The decision object `[LOCKED]`
The domain core emits a **structured decision object, never prose.** The consumer UI and the agent-facing client-shareable proposal are two rendering adapters over the *same* object. This is why the core must never emit formatted text as its primary output.

### 4.6 CQRS read model `[LOCKED]`
The scored candidate set is a **read model**. Sliding the price-vs-weather weights must re-rank **instantly off cached scores without re-fetching**. Exploring the tradeoff space interactively is the core value prop, so the command/query split is present from the start.

---

## 5. Intake / Processing / Output Flow
Runtime order is forward; content is only what the backward trace proved necessary. **Discipline `[LOCKED]`: every intake question must trace to a downstream computation.** If a question does not feed the objective function, the search space, or a hard constraint — cut it.

- **Intake** — solve mode; party composition (adults, kids + ages → ticket pricing/eligibility; custody/availability calendars as first-class constraints); hard constraints (school, work blackouts, custody, budget ceiling, must-include events); soft weights (the MCDA objective); scope (which resort / Universal / both; on- vs off-property; DVC ownership).
- **Processing** — resolve solve mode → search space; fan out through data-source adapters → normalize into per-candidate vectors; deterministic MCDA scoring + Pareto classification (**no AI**). Result is the CQRS read model.
- **Output** — the tradeoff view (Pareto projection); ranked candidates with score decomposed by dimension; per-candidate detail (cost breakdown, weather-as-expectation, crowd forecast, events, offers); on selection → itinerary skeleton (park-day allocation by crowd/hours) + bookable checklist with price-watch. Same object → client-shareable proposal for the B2B/agent case.

---

## 6. The Field Registry (Keystone)
Every fillable field is registered with metadata:
```yaml
- path: trip.addons.lightning_lane.tier      # canonical address
  type: enum                                  # enum | date | currency | int_range | ...
  domain: [none, multi_pass, single_pass, premier]
  provenance: USER_INPUT                       # USER_INPUT | DERIVED | FETCHED
  aliases: ["Lightning Lane Premier", "LL Premier", "the premium skip-the-line thing"]
  description: "Which paid Lightning Lane product the party intends to buy."
  # embedded (vector) for NL resolution — routing/matching only, never scoring
  depends_on: null                             # inputs, for DERIVED/FETCHED (forms the recompute DAG)
  maturity_level: L2                            # L0 | L1 | L2 | L3
  cost_to_obtain: metered                       # free_shared | cached | metered
```

### 6.1 Provenance classes (the firewall) `[LOCKED]`
- `USER_INPUT` — constraints, preferences, the weights. **The only class the LLM may propose operations against.**
- `DERIVED` — engine-computed via deterministic formulas. **Never LLM-writable.**
- `FETCHED` — from an adapter. **Never LLM-writable.**

This enforces the deterministic-math-gate firewall: the LLM proposes *inputs*; the engine owns everything downstream.

### 6.2 What the one registry powers
NL resolution (aliases + embeddings) · schema validation (type/domain) · the recompute DAG (`depends_on` edges) · paywall gating (`maturity_level`) · cost metering (`cost_to_obtain`). Five systems, one artifact, registered once.

### 6.3 The completeness validator `[LOCKED]`
A validator **fails loudly** if any `DERIVED`/`FETCHED` field has an input that is not wired to dirty it in the cascade. An unmapped edge (e.g. `month → LL_estimate` forgotten) leaves a stale value that *looks valid* — this is the "silent missing-predecessor" failure in interactive form, and the validator is the cure.

---

## 7. The Data Layer
### 7.1 The taxonomy (classify once)
| Class | Volatility | Shared-ness | Store | Example |
|---|---|---|---|---|
| Durable reference | ~never / yearly | global (shared) | Postgres (WORM) | historical weather climatology |
| Slow shared | refines w/ lead time | global (shared) | Postgres + computed TTL | crowd prediction by week |
| Fast shared | minutes–hours | global (shared) | Redis (TTL) | live wait times |
| Per-user volatile | minutes–hours | per-tenant | Redis (TTL) + snapshot | live flight quote, DVC availability |
| Per-user durable | stable | per-tenant | Postgres (tenant rows) | trip constraints, weights |

### 7.2 Two stores, two mechanisms `[LOCKED]`
- **Durable reference store (Postgres):** low-volatility, high-share data is *not a cache* — it is ingested once and owned, write-once-read-many, TTL "a year" or "never." Putting it in an evictable cache is a category error (re-pays API cost on eviction).
- **Ephemeral TTL cache (Redis):** high-volatility data, TTL seconds-to-hours.

### 7.3 THE cache key discipline — the load-bearing decision `[LOCKED]`
Cache keys must be the **intrinsic natural key of the shared dimension and must EXCLUDE tenant/user.**
```
weather:climatology:{park}:{month}:{day}
availability:dvc:{resort}:{date}:{occupancy}:{roomtype}
```
No `tenant_id` in the key → every tenant asking about early December hits one row; the underlying API is called **once, ever.** The instant someone adds session/user context "to be safe," every user pays full freight and the cache *looks* like it works while saving nothing. This is the amortization decision the entire cost thesis rests on. **Key on the data's own dimensions, never on who is asking.**

### 7.4 Lead-time TTL `[LOCKED]`
For shared-but-refining data (crowd, availability), **TTL is computed as a function of `target_date − now`, not a constant.** A date 200 days out refreshes weekly; the same date inside the booking window refreshes hourly/daily.

### 7.5 Two write patterns `[LOCKED]`
- **Static data:** cache-and-reuse.
- **Volatile-but-historically-valuable data:** cache-for-serving **and append a timestamped snapshot to a history log**, including on eviction/refresh (tee evicted Redis values into a Postgres append log).

### 7.6 History tables committed from day 1 `[LOCKED]` `[V1]`
These get the append-snapshot treatment because they are **perishable observations** — unrecoverable if not captured as they happen, and they are the moat:
- wait times
- offers/promos
- flight prices
- room/accommodation prices
- **DVC availability** (each availability call is "X was available for date D, as seen on T")

Everything else is serve-only until proven valuable. The schema ships with these history tables **in it**, not bolted on after a year of capturable data is lost.

---

## 8. Data Sources / Adapter Catalog
Each source is an adapter behind a port. The critical column is **commercial redistribution** — it decides personal-vs-product tier. The clean fault line: data is available; redistribution rights are where sources diverge.

### 8.1 Weather `[LOCKED]`
The need is **climatology** (an expectation + variance for a trip months out), not a forecast — forecasts don't exist past ~16 days regardless of vendor.

| Source | Role | Terms | Tier |
|---|---|---|---|
| **Open-Meteo** (primary) | ERA5 reanalysis, hourly from 1940, gap-free, global | CC BY 4.0 — commercial redistribution OK with attribution; AGPLv3 self-hostable | Both — **self-host on Unraid/Docker** for unlimited calls at zero marginal cost |
| Visual Crossing (alt) | 50+ yrs historical | commercial on paid plan | Both (managed SLA alternative to self-host) |
| NOAA / NCEI | US authoritative actuals + official normals | public domain | Both (corroborating; US-only, fine for these parks) |

**AccuWeather is rejected for this corner.** Its climate-normals product is behind separate Enterprise APIs (sales contact, **1-year minimum contract**), it explicitly offers no historical forecasts, and its cheap dev tiers are non-commercial. Wrong tool — it's a forecasting/current-conditions product. A **near-term forecast** (in-trip, day-of, inside 16 days) is a *different question* that lives behind the *same weather port* and is not needed for v1 candidate ranking.

### 8.2 Crowd `[LOCKED]`
**Two different quantities with opposite availability profiles:**
- **Observed wait times** (near-commoditized): **Queue-Times** (free real-time API, 80+ parks, data back to 2014, attribution required) and **themeparks.wiki** (free REST API). Both commercial-compatible via attribution.
- **Predicted crowd index** (proprietary secret sauce): what the optimizer actually consumes for *future* weeks. Nobody sells it as a redistributable API. **Thrill Data** has rich data but is **personal & academic license only — not resellable.**

**Decision:** crowd is an **own-it-by-accumulation** play.
- **Day 0:** stand up a poller against Queue-Times / themeparks.wiki and bank the data (history tables, §7.6). By the time the product needs a resellable crowd model, the training corpus exists, built entirely from attribution-licensed feeds. *This is a Penrose corner: nearly free to satisfy if seen on day 1, a hard blocker if not.*
- **v1 scoring:** the crowd axis is a **deterministic wait-time proxy** ("average historical wait for this week-of-year across N years"). Auditable, improves as the corpus grows, fits the math-gate philosophy. The predictive model layers in later `[LATER]`.
- **Thrill Data / Touring Plans:** personal-tier only.

### 8.3 Tickets / Cost `[LOCKED]`
**Undercover Tourist** — split verdict:
- **As a ticket-price source: excellent and sanctioned.** Disney-authorized Selected Ticket Seller; affiliate program distributes discounted ticket pricing as a **CSV product feed via the AWIN network** (30-day cookie, commission on sales). Wire into the ticket-price port — it is *both* a data source *and* a revenue channel (commission on every ticket users/agents buy through it).
- **As a crowd source: do not use.** Their crowd calendar is proprietary (20+ yrs of their own wait data + private hotel/ticket signals), exposed only as a consumer web page → scraping, same encumbered category as above.

### 8.4 DVC availability `[OPEN]` for product tier
- **Personal tier `[V1]`:** the existing ingestion (see §18 / appendix) hits the unofficial `keyholdervacations.com` backend that powers the DVC Rental Store site, with spoofed `origin`/`referer` headers and no auth. Fine for personal use; **behind the DVC port** so endpoint/auth/bot-detection changes touch only the adapter. Availability facts get history-snapshotted (§7.6) → proprietary DVC availability/cancellation-pattern dataset (second flywheel).
- **Product tier `[OPEN]`:** the unofficial endpoint almost certainly cannot survive commercial multi-tenant use (rate limits, ToS, detectability from server IPs at scale). **No clean commercial source identified yet.** Carried as unresolved — the PRD does not pretend otherwise. ToS mitigation acknowledged as a solve-over-time concern.

### 8.5 Flights `[OPEN]`
A `FETCHED` / L2 field regardless of source (does not touch architecture). Candidate APIs: Amadeus, Duffel, Kiwi — costly, terms-restrictive. **Commercial diligence not yet done.** Named here; resolved later.

### 8.6 Events, Lightning Lane, Offers
- **Events:** Ticketmaster / SeatGeek / Bandsintown — real APIs (also where embeddings genuinely earn a place: matching headline events to a week).
- **Lightning Lane cost:** dynamic and day-of; **not knowable in advance.** Store as an **estimate/range only**, or the cost breakdown quietly lies.
- **Offers/promos:** no API → scrape. Personal-tier; genuine ToS exposure for product tier (solve-over-time).

---

## 9. The Maturity Ladder & Monetization
Trip maturity is a traversal from the cheap/shared/static corner of the data space toward the expensive/personal/volatile corner. It is **literally the cost gradient**, and that is what places the paywall. Model it as an explicit state ladder (same headless state-machine discipline as the proposal pipeline).

| Level | What | Data profile | Marginal cost | Gate |
|---|---|---|---|---|
| **L0 — Season browse** | "Disney in June" | 100% globally-cached, low-volatility; AI narrative cached | **≈ zero** | none / no login |
| **L1 — Shape the window** | few questions → deterministic optimizer ranks weeks | still mostly cached, lightly personalized by weights | low | **account creation** (free, captures user) |
| **L2 — Real rates, real dates** | live DVC for their contract, current rates/offers, live flights, LL pricing | per-user, volatile, **metered** | **real $/user, cannot amortize** | **PAYWALL** |
| **L3 — Book & monitor** | price-watch, offer alerts, itinerary finalize, affiliate ticket purchase | ongoing per-user compute | recurring | **subscription** |

**The paywall sits at L1→L2 `[LOCKED]`** — precisely where marginal-cost-per-user jumps from ~zero to real, i.e. where data stops being shareable/cacheable and becomes per-user/metered. Gating is driven by each field's `maturity_level` + `cost_to_obtain` metadata (§6).

**Why the free tier is economically safe:** L0/L1 cost is bounded by the **cardinality of the shared data space** (parks × days-of-year × query-types — finite and small), **not by user count.** A million users asking "how's June" cost almost the same as one, once the cache is warm. L2 scales linearly with paying users — which is exactly why it must be paid.

**Honesty guardrail (that also sells the upgrade) `[LOCKED]`:** L0/L1 data is **directional and historical** ("June *typically* runs ~$X"), not a bookable quote. State this explicitly in the UI or L2's real rates appear to "violate" it. Framed right, that gap *is* the pitch: "here's what it usually costs; unlock live rates for your dates."

**Storage grows with maturity `[LOCKED]`:** L0 persists nothing per-user; L1 creates a Trip record (constraints + weights + pointers to shared data); L2 hardens it with snapshots of the actual fetched rates (kept against the trip even once stale — the user's decision history).

---

## 10. The Conversational Layer
**Spine `[LOCKED]`:** *The chat never edits state; it emits operations. The Field Registry defines which operations are legal; a deterministic engine applies them and runs the recompute cascade; simulate is the default; when a legal operation can't be formed, the AI directs instead of guessing.*

### 10.1 Operation flow (per chat turn)
```
utterance
  → resolve to registered field(s) + intent {read | simulate-set | commit-set}
  → LLM emits a CONSTRAINED operation  (a tool call against the registry vocabulary — NOT free JSON)
  → deterministic engine validates → applies to a copy-on-write BRANCH of the Trip document
  → runs the recompute cascade (DAG)
  → returns new state + a diff
```
The LLM proposes the *input* change; the engine owns everything downstream and computes `DERIVED` values via the deterministic formulas.

### 10.2 "Edit itself" vs "direct the user" — a deterministic rule, not fresh judgment `[LOCKED]`
- Target resolves to a `USER_INPUT` field, value present/derivable → **AI forms the operation** (simulate; commit on confirm). *"It edits the field itself."*
- Target is `FETCHED`, or a `USER_INPUT` with no known value, or resolution is ambiguous/gated → **AI directs** (asks, or points to the field / the paywall).

The field's provenance class already decided whether the AI may act. The model only decides what to *say*.

### 10.3 Worked examples
- **"What would Lightning Lane Premier cost?"** → resolves `lightning_lane.tier` (USER_INPUT) + `lightning_lane.estimated_cost` (DERIVED). Intent = simulate-set tier=premier + read cost. Engine forks a branch, sets tier, cascade recomputes cost deterministically (party × per-day price × park-days) pulling the FETCHED LL price (directional at L1, live at L2). AI computed it *through the engine and formula* — never invented a number — and previewed rather than mutating baseline.
- **"But what if we changed to January?"** → resolves `window.month`, intent ambiguous → **default simulate.** Cascade dirties month → crowd, weather, seasonality, ranked weeks, date-dependent costs. At L1 every recompute is shared/cached (≈ free). At L2 the engine sees the cascade touches FETCHED-per-user fields and **warns before spending** ("switching re-fetches live rates — metered, continue?"). Returns a preview diff.

### 10.4 Simulate / commit / branch `[LOCKED]`
Default to **simulate against a copy-on-write branch** — exploration never destroys the baseline. Commit promotes a branch; discard drops it; "and also October" branches fresh. This is the **command pattern over a versioned document**: operations are reversible, loggable, replayable.

### 10.5 The operation log — full replayable command history `[LOCKED]` `[V1]`
Current trip state = **a fold over its operation log.** Gives free undo, full audit ("why is this trip in this state"), and branch-replay as first-class. Same append-history discipline as the volatile data (§7). *Not* full ceremonial event-sourcing — the append log gives ~90% of it cheaply. **This is designed in from day 1 because it is far more painful to retrofit than to build in, and it makes "what if" genuinely cheap.**

### 10.6 Two more non-negotiables `[LOCKED]`
- Every AI-originated edit is **tagged `AI-proposed`** in provenance — never masquerades as a user assertion; the user can see "AI changed this" and revert.
- The **form UI and the chat are two driving adapters over one source of truth** (the Trip document). An edit from either reflects in the other; the chat agent hydrates context from live state each turn (no stale snapshot). This is the final reason "MVC was too small."

### 10.7 Residual hardness (organized, not eliminated) `[OPEN]` — engineering, not architecture
- **Dependency-graph completeness** — the §6.3 validator is the cure; treat as a first-class check.
- **Resolution ambiguity** — "change the dates" (which?), "make it cheaper" (how?) — surface multiple candidate operations and **disambiguate, gated on a confidence threshold; never guess.** Much of the product polish lives here.
- **Latency** — a shared/cached simulate is near-instant; an L2 simulate that re-fetches live data is slow → async/streamed with the metered-action warning up front. Different UX treatments so the cheap path stays snappy.

---

## 11. The AI Layer
### 11.1 The three zones (and only these) `[LOCKED]`
1. **Intake parsing** — fuzzy input ("sometime in spring, kids can't miss the gymnastics meet") → structured constraints.
2. **Unstructured matching** — headline event that week? does this off-property listing match their taste?
3. **Narrative generation** — the "why this week" write-up.

### 11.2 pgvector — three legitimate uses, all routing/matching, never scoring `[LOCKED]`
- semantic matching of unstructured intake/listings (zone 2)
- semantic caching key routing (§11.4)
- Field Registry alias resolution (§6)

**Never embed cost/crowd/weather** — that is a three-number deterministic decision, not an embedding problem.

### 11.3 Model access `[LOCKED]`
- **Our keys via OpenRouter** for the default path; **BYOK via OpenRouter** for users who bring their own.
- Two adapters behind **one LLM port** — not a code path threaded through the app. Metering + routing happen at that boundary (§3).
- **Model-tier routing** (cheap orchestrator, mid research, frontier critique) as appropriate.

### 11.4 Semantic caching `[LOCKED]`
"Tell me about Disney in June," when all inputs are globally-cached data, produces a globally-cacheable **output**. Cache the generated narrative, keyed on a **canonicalized** query + the version of the underlying data. A cheap normalization step collapses "what's June like at Disney" / "june disney trip" / "tell me about Disney in June" to one canonical intent+params. The biggest LLM saving is **not calling the model at all** for a repeat low-specificity question (GPTCache pattern).

---

## 12. Multi-Tenancy & Auth
**Model `[LOCKED]`: tenant-as-boundary hierarchy with forced row-level security as the floor and a per-tenant isolation tier above it.** Answers both "bulletproof independent users" and "corporate tenant" without branching the data model — a lone consumer and a 40-seat agency are the same shape, different cardinality.

### 12.1 The tenant abstraction
- Tenant = the isolation **and** billing boundary. Users belong to exactly one tenant.
- **B2C signup** mints a **tenant-of-one** automatically.
- **Corporate account** = **tenant-of-many** with roles (agency admin, agent) and optional **Entra SSO** (OIDC federation behind the auth port).

### 12.2 The floor: forced RLS, fail-closed `[LOCKED]`
Isolation is enforced **below the application layer** in Postgres:
- `FORCE ROW LEVEL SECURITY`
- a **non-superuser** application role
- a tenant context that **fails closed** — no tenant set means **no rows, never all rows.**

Multi-tenant leaks come almost always from application-layer filtering a buggy query forgets. Pushing enforcement below the app means an app bug **cannot** cross tenants. This is the floor for everyone.

### 12.3 The isolation tier (per-tenant attribute) `[LOCKED]`
- **`pool`** — shared DB + RLS. Default for all B2C and standard B2B; the only thing that scales to many small/free-tier tenants (the L0 funnel is high-volume and free by design).
- **`silo`** — dedicated schema or database for an enterprise client contractually demanding physical separation.

Because persistence is behind a port, **pool → silo promotion is a provisioning action, not a code change.** One knob decided later, per client (§15). Reference: AWS SaaS **pool/silo** model — adopted day 1, not invented.

**The taxonomy already did the hard part:** the expensive-to-isolate data (weather, crowd, seasonality) is *global shared* and sits **outside** the tenant boundary entirely (§7.3). Tenancy only wraps the per-user trip/preference tables — where row-level is plenty.

---

## 13. Deployment / Infrastructure
**Docker (assume for now).** Three long-lived containers + the app:
- **Postgres** — durable reference store + trip state + tenant data + history logs + operation log.
- **Redis** — ephemeral TTL cache.
- **Scheduler / worker** — background ingestion + refresh. **Natural n8n fit** given existing stack.

**Ingestion jobs (all the same category — scheduled ingestion into the store):**
- annual weather re-ingest (Open-Meteo, self-hosted)
- lead-time-tiered crowd/availability refresh
- offer polling
- **the day-0 wait-time poller** (Queue-Times / themeparks.wiki) — first inhabitant of the ingestion layer; runs *before the app exists*.

Per-night error isolation + retry on ingestion (see n8n error-handling patterns) so one flaky fetch degrades to a gap, not a total-run failure.

---

## 14. Reference Architectures (pulled in day 1)
Named handles so we do not reinvent, badly:
- **Event Storming** (Brandolini) — output-first backward design.
- **Multi-Criteria Decision Analysis (MCDA)** — weighted sum / TOPSIS / Pareto filtering.
- **Ports & Adapters (Hexagonal)** — the macro-structure.
- **CQRS / Read Model** — instant re-ranking; the durable reference store is a materialized view over external sources.
- **Cache-Aside / Lazy Loading** — populate-on-miss.
- **Materialized View** — the reference store.
- **Semantic Caching (GPTCache)** — the LLM layer.
- **Command pattern / event-sourcing-lite** — the operation log.
- **AWS SaaS pool/silo** — the tenancy tiers.

---

## 15. Open Questions (carried deliberately)
1. **DVC product-tier availability source `[OPEN]`.** No clean commercial source identified. Personal tier uses the unofficial endpoint; product tier is unresolved. Options to run down: negotiate a commercial data arrangement; find an authorized data partner; or scope the product tier without live DVC initially.
2. **Flight-pricing adapter commercial diligence `[OPEN]`.** Amadeus / Duffel / Kiwi — terms + cost not yet evaluated. Architecturally absorbed (L2 FETCHED field); needs a vendor decision.
3. **DVC range-endpoint payload `[OPEN]` — free-money check.** Does the range-date response already contain per-night availability breakdowns? If yes, the N per-night calls collapse to **one range call parsed in memory (N→1)** before caching even applies. If it only returns an aggregate roll-up, per-night calls are necessary and caching is the lever. **Resolve by inspecting a raw response payload.**
4. **Crowd predictive model specifics `[LATER]`.** v1 is the deterministic wait-proxy; the ML model is deferred until the accumulated corpus justifies it.
5. **Which tenants get `silo` `[LATER]`.** Per-client decision; nothing else re-opens.

---

## 16. Explicitly Out of Scope for v1
- Full crowd **ML** prediction model (v1 = wait-time proxy).
- Real-time flight **booking** (pricing/watch only if flights land in v1 at all).
- Deep non-Orlando expansion (architecture is general; content/adapters start Orlando-focused).
- Native mobile app (responsive web first).
- Product-tier DVC (personal-tier only until §15.1 resolves).
- BYOK beyond OpenRouter.

---

## 17. Build Sequencing (phase-as-boundary)
For the AI coding agents — phases are boundaries, each independently shippable. Deterministic code gates for all arithmetic; OpenRouter for all model calls.
- **Phase 0 — Accumulate before the app.** Day-0 wait-time poller + history tables (waits, and schema stubs for offers/prices/DVC availability). Self-host Open-Meteo. *Start the clock on the moat.*
- **Phase 1 — Deterministic spine.** Domain core + Field Registry + MCDA scoring + recompute cascade + completeness validator. Trip document + operation log. L0/L1 over cached shared data only — **no per-user fetches.** Postgres + Redis + forced RLS floor.
- **Phase 2 — Data adapters + caching.** Weather (climatology), crowd (wait proxy), tickets (Undercover Tourist AWIN feed). Cache/meter/route decorators on the port boundary. Cache-key discipline + lead-time TTL enforced and tested.
- **Phase 3 — Conversational layer.** Chat-as-operation-emitter, constrained operations, simulate/commit/branch, EITHER-edit-OR-direct rule, AI-proposed provenance tagging, disambiguation. Form + chat as dual drivers over the Trip document.
- **Phase 4 — L2 paywall + metered per-user adapters.** DVC (personal-tier adapter behind the port), flights (pending §15.2), live rates/offers. Metered-action warnings. Rate cards externalized to `/inputs/` CSVs.
- **Phase 5 — Multi-tenancy hardening + B2B.** Pool/silo tiers, Entra SSO, agency roles, per-tenant metering/billing, client-shareable proposal rendering of the decision object.

---

## 18. Appendix — Current DVC Ingestion Assessment
The existing PowerShell script is **not gospel**, but it validates the architecture and confirms the fragile corner exactly where predicted.

**What it is:** direct calls to `api.keyholdervacations.com/v2/dvc/availability/calendar` with `origin`/`referer` spoofed to `dvcrentalstore.com` and **no API key** — the private backend powering the DVC Rental Store site, called as if we were its frontend. Unofficial, unauthenticated, standing on spoofed headers.

**What carries forward (validates the design):**
- **Provenance model already implicit:** `availabilityLevel` / `pointCost` / `rentalCost.standard` = `FETCHED`; point rate / park days / people / occupancy = `USER_INPUT`; `estimatedCost = totalPoints × pointRate` and the ticket formula `$65 + ($392.36 / parkDays)` + hopper clamp = `DERIVED`. This is the Field Registry's three classes and the math gate, operating already. → becomes the explicit registry + cost engine.
- **Rate constants become editable rate-card CSVs under `/inputs/`** (`TicketBasePerDay`, `TicketFixedOverhead`, hopper bounds, point rate) — a rate change is a data edit, not a code deploy.
- **Availability facts are perishable → history-snapshot** them (§7.6) → proprietary DVC dataset (second flywheel).

**What must change for adapter-ization:**
- Behind the **DVC port**; personal-tier only; **not** lifted into the multi-tenant path as-is (server-IP + spoofed-header calls at scale are materially more detectable).
- **Caching kills the night-by-night waste.** The script loops one call per night, every run, zero reuse — but availability of `AKV-STU` on a date at an occupancy is identical for every user. Tenant-free keys + lead-time TTL → likely 1–2 orders of magnitude fewer calls, which on a fragile endpoint is *also* the survivability win. (Also check §15.3: the range endpoint may already return per-night data → N→1 before caching.)
- **Robustness fixes:** SKU room-type parse must **fail loud + log** on an unrecognized SKU, not silently bucket to `UNK` (silent bucket = corrupted cost math when SKU format changes). Per-night **error isolation + retry** (not `$ErrorActionPreference = "Stop"` aborting the whole run). Fix the hopper comment/constant drift ($85–$110 comment vs $100/$120 constants) before it becomes the authoritative rate card.

None of this bends the architecture — it lands cleanly as the DVC adapter behind the DVC port, feeding the deterministic cost engine, cached (lead-time TTL, tenant-free keys) and snapshotted to history.

---
*End of PRD v0.1 — Draft for build.*

# Implementation Plan — Phase 1: The Deterministic Spine

> Phase 0 (Accumulate) is shipped: poller + history tables + Docker. This plan covers Phase 1.

**Stack:** Python domain core (pure), no HTTP surface yet (driving adapters arrive in Phase 3).
**Goal (PRD §17):** the auditable heart — Field Registry, MCDA scoring, recompute cascade,
completeness validator, Trip document + operation log. L0/L1 logic over **synthetic/in-memory**
candidate facts only (real adapters are Phase 2). Add the forced-RLS floor SQL.

## Deliverable: one end-to-end vertical slice, fully tested
`Registry → Trip → Operation (simulate-set) → cascade recompute (DERIVED formula) → MCDA score →
Pareto front → DecisionObject`, plus the provenance firewall, completeness validator, and operation log.

## New package: `src/core/` (the pure domain, sibling to `moat/` ingestion)
```
[NEW] src/core/registry.py      # Provenance/Maturity/CostToObtain enums, FieldSpec, FieldRegistry
                                 #   - load YAML → specs; index by path + alias
                                 #   - validate a value against type/domain
                                 #   - build depends_on DAG + topological order
                                 #   - completeness validator: FAIL LOUD on unmapped edges (§6.3)
[NEW] src/core/fields.yaml       # compact but representative field set (USER_INPUT/DERIVED/FETCHED)
[NEW] src/core/trip.py           # Trip document: path → Value(provenance, origin tag); copy-on-write branch
[NEW] src/core/operations.py     # Operation {read|simulate_set|commit_set}; firewall: chat may only
                                 #   touch USER_INPUT; OperationLog (append fold → free undo/replay, §10.5)
[NEW] src/core/formulas.py       # deterministic DERIVED formulas (ticket + LL cost), rate card from /inputs
[NEW] src/core/cascade.py        # dirty-propagation over the DAG → recompute DERIVED (no AI)
[NEW] src/core/mcda.py           # weighted-sum + TOPSIS ranking + Pareto non-dominated set (§4.3)
[NEW] src/core/candidate.py      # Candidate (dest×week×accom) + FeatureVector; in-memory facts provider
[NEW] src/core/decision.py       # structured DecisionObject (never prose, §4.5)
[NEW] src/core/solve.py          # flexible-window solve engine (THE engine; hard-dates = search of one)
[NEW] inputs/rate_card.csv       # editable rate constants (ticket base/overhead, LL per-tier) — §18
[NEW] db/migrations/0002_tenancy_rls.sql  # tenant/trip tables + FORCE RLS + fail-closed policy (§12.2)
[NEW] tests/core/...             # registry, firewall, cascade, mcda, solve (no network, no DB)
```

## Design tenets honored
- **Deterministic math gate (§2.2):** no AI anywhere in this package; scoring is plain arithmetic.
- **Provenance firewall (§6.1):** operations may only set `USER_INPUT`; `DERIVED`/`FETCHED` are engine/adapter-owned.
- **Completeness validator (§6.3):** every `DERIVED` input must be a wired DAG edge or the validator fails loudly.
- **Command-pattern operation log (§10.5):** trip state = a fold over its append-only log.
- **CQRS (§4.6):** sliding weights re-ranks off cached feature vectors without recomputing facts.
- **RLS floor (§12.2):** enforced below the app; no tenant context ⇒ no rows, never all rows.

## Verification
`pytest` — new `tests/core/` suite exercises the full slice with synthetic facts (no network, no DB).

## NOT in Phase 1
Real data adapters + caching (Phase 2), chat/HTTP (Phase 3), paywall + metered fetches (Phase 4),
live multi-tenant wiring beyond the SQL floor (Phase 5).

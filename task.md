# Task Checklist — Phase 1 (Deterministic Spine)

- [x] `src/core/registry.py` + `fields.yaml` — Field Registry (aliases, validation, DAG)
- [x] `inputs/rate_card.csv` — editable rate constants
- [x] `src/core/trip.py` — Trip document, provenance-tagged values, copy-on-write branch
- [x] `src/core/formulas.py` — deterministic DERIVED formulas + FETCHED provider (rate-card stub)
- [x] `src/core/cascade.py` — recompute cascade + completeness validator (§6.3 fail-loud)
- [x] `src/core/operations.py` — Operation model, provenance firewall, OperationLog (fold/undo)
- [x] `src/core/mcda.py` — weighted sum, TOPSIS, Pareto front
- [x] `src/core/candidate.py`, `decision.py`, `solve.py` — solve engine + structured decision object
- [x] `db/migrations/0002_tenancy_rls.sql` — forced RLS floor, fail-closed
- [x] `tests/core/` — registry, validator, cascade, operations, mcda, solve
- [x] pyproject: pyyaml dep + package the registry YAML
- [x] Verify: `pytest` green (34 passed)
- [x] Commit + push

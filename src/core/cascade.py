"""The recompute cascade (PRD §4, §10.1) and completeness validator (§6.3).

When USER_INPUT changes, dirty every transitively-dependent DERIVED/FETCHED field
and recompute it in topological order. Deterministic — no AI ever runs here.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from core.formulas import FETCHERS, FORMULAS, Rule
from core.registry import FieldRegistry, Provenance
from core.trip import Trip


class CompletenessError(RuntimeError):
    """Raised when the DAG is not fully wired — the §6.3 fail-loud check."""


def check_completeness(
    registry: FieldRegistry,
    formulas: Mapping[str, Rule] = FORMULAS,
    fetchers: Mapping[str, Rule] = FETCHERS,
) -> None:
    """Every DERIVED/FETCHED field must have a rule whose inputs EXACTLY match its
    depends_on. A forgotten edge (e.g. month → LL_estimate) leaves a stale value
    that *looks valid*; this catches it loudly before it can lie."""
    problems: list[str] = []
    for spec in registry.specs():
        if spec.provenance is Provenance.DERIVED:
            rule = formulas.get(spec.path)
            kind = "formula"
        elif spec.provenance is Provenance.FETCHED:
            rule = fetchers.get(spec.path)
            kind = "fetcher"
        else:
            continue
        if rule is None:
            problems.append(f"{spec.provenance.value} {spec.path} has no {kind}")
            continue
        if set(rule.inputs) != set(spec.depends_on):
            problems.append(
                f"{spec.path}: {kind} inputs {sorted(rule.inputs)} "
                f"!= depends_on {sorted(spec.depends_on)}"
            )
    if problems:
        raise CompletenessError("; ".join(problems))


def _closure(registry: FieldRegistry, seeds: Iterable[str]) -> set[str]:
    """All fields transitively dependent on the seeds (excludes the seeds)."""
    affected: set[str] = set()
    stack = list(seeds)
    while stack:
        path = stack.pop()
        for dep in registry.dependents(path):
            if dep not in affected:
                affected.add(dep)
                stack.append(dep)
    return affected


def recompute(
    registry: FieldRegistry,
    trip: Trip,
    dirty: Iterable[str],
    formulas: Mapping[str, Rule] = FORMULAS,
    fetchers: Mapping[str, Rule] = FETCHERS,
) -> list[str]:
    """Recompute every field affected by `dirty`, in topological order.
    Fields whose inputs are not all present yet are skipped (partial trips don't
    crash), leaving them unset until their predecessors exist."""
    affected = _closure(registry, dirty)
    changed: list[str] = []
    for path in registry.topological_order():
        if path not in affected:
            continue
        spec = registry.get(path)
        if spec.provenance is Provenance.FETCHED:
            rule = fetchers[path]
        elif spec.provenance is Provenance.DERIVED:
            rule = formulas[path]
        else:
            continue  # USER_INPUT is never recomputed
        if not all(trip.has(dep) for dep in rule.inputs):
            continue
        inputs = {dep: trip.value(dep) for dep in rule.inputs}
        value = registry.validate_value(path, rule.fn(inputs))
        trip.set_computed(path, value, spec.provenance)
        changed.append(path)
    return changed

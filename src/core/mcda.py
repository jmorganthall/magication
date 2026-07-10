"""Multi-Criteria Decision Analysis (PRD §4.3).

Real machinery — min-max normalization, weighted sum, TOPSIS, and Pareto
filtering — not invented quadrant math. No AI: cost/crowd/weather is a
low-dimensional deterministic decision, never an embedding.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Criterion:
    key: str
    weight: float
    maximize: bool = False  # default: minimize (cost, crowd). weather maximizes.


Row = Mapping[str, float]


def normalize(values: Sequence[float], maximize: bool) -> list[float]:
    """Min-max to [0, 1] where higher is always better. Degenerate (all-equal)
    columns map to a neutral 1.0 so they don't skew the weighted sum."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    if maximize:
        return [(v - lo) / (hi - lo) for v in values]
    return [(hi - v) / (hi - lo) for v in values]


def _columns(rows: Sequence[Row], criteria: Sequence[Criterion]) -> dict[str, list[float]]:
    return {c.key: normalize([r[c.key] for r in rows], c.maximize) for c in criteria}


def weighted_sum(rows: Sequence[Row], criteria: Sequence[Criterion]) -> list[float]:
    if not rows:
        return []
    wsum = sum(c.weight for c in criteria) or 1.0
    cols = _columns(rows, criteria)
    return [
        sum(c.weight * cols[c.key][i] for c in criteria) / wsum
        for i in range(len(rows))
    ]


def topsis(rows: Sequence[Row], criteria: Sequence[Criterion]) -> list[float]:
    """Closeness to the ideal solution, in [0, 1]."""
    if not rows:
        return []
    n = len(rows)
    wsum = sum(c.weight for c in criteria) or 1.0
    cols = _columns(rows, criteria)  # already higher-is-better in [0, 1]
    wn = {c.key: [(c.weight / wsum) * cols[c.key][i] for i in range(n)] for c in criteria}
    ideal = {c.key: max(wn[c.key]) for c in criteria}
    anti = {c.key: min(wn[c.key]) for c in criteria}
    scores: list[float] = []
    for i in range(n):
        d_ideal = sum((wn[c.key][i] - ideal[c.key]) ** 2 for c in criteria) ** 0.5
        d_anti = sum((wn[c.key][i] - anti[c.key]) ** 2 for c in criteria) ** 0.5
        scores.append(0.0 if (d_ideal + d_anti) == 0 else d_anti / (d_ideal + d_anti))
    return scores


def pareto_front(rows: Sequence[Row], criteria: Sequence[Criterion]) -> list[int]:
    """Indices of the non-dominated set — 'what jumps out' (§4.3)."""
    def dominates(a: Row, b: Row) -> bool:
        no_worse = all(
            (a[c.key] >= b[c.key]) if c.maximize else (a[c.key] <= b[c.key])
            for c in criteria
        )
        strictly_better = any(
            (a[c.key] > b[c.key]) if c.maximize else (a[c.key] < b[c.key])
            for c in criteria
        )
        return no_worse and strictly_better

    front: list[int] = []
    for i, row in enumerate(rows):
        if not any(dominates(other, row) for j, other in enumerate(rows) if j != i):
            front.append(i)
    return front

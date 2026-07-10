"""The solve engine (PRD §4.4) — one engine, not five.

The flexible-window optimizer IS the core engine: hard dates are a search space
of one, duration-only widens the window, budget/event anchors are filters. It
ranks candidates via MCDA and emits a structured DecisionObject.

CQRS (§4.6): sliding the weights re-ranks off the same candidate facts — no
re-fetch — which is exactly what makes interactive tradeoff exploration cheap.
"""
from __future__ import annotations

from typing import Sequence

from core.candidate import Candidate, FactsProvider
from core.decision import DecisionObject, Dimension, ScoredCandidate
from core.mcda import Criterion, normalize, pareto_front, topsis, weighted_sum
from core.trip import Trip

_METHODS = {"weighted_sum": weighted_sum, "topsis": topsis}


class SolveEngine:
    def _addon_costs(self, trip: Trip) -> float:
        """Trip-level DERIVED costs shared across candidates (tickets + LL)."""
        total = 0.0
        for path in ("trip.tickets.estimated_cost", "trip.addons.lightning_lane.estimated_cost"):
            if trip.has(path):
                total += float(trip.value(path))
        return total

    def solve(
        self,
        trip: Trip,
        candidates: Sequence[Candidate],
        facts: FactsProvider,
        method: str = "weighted_sum",
    ) -> DecisionObject:
        if method not in _METHODS:
            raise ValueError(f"unknown MCDA method: {method!r}")

        addons = self._addon_costs(trip)
        rows: list[dict[str, float]] = []
        enriched: list[tuple[Candidate, float, float, float]] = []
        for cand in candidates:
            f = facts.facts(cand)
            total_cost = f.base_cost + addons
            rows.append({"cost": total_cost, "crowd": f.crowd_index, "weather": f.weather_score})
            enriched.append((cand, total_cost, f.crowd_index, f.weather_score))

        criteria = [
            Criterion("cost", float(trip.value("weights.cost")), maximize=False),
            Criterion("crowd", float(trip.value("weights.crowd")), maximize=False),
            Criterion("weather", float(trip.value("weights.weather")), maximize=True),
        ]

        scores = _METHODS[method](rows, criteria)
        front = set(pareto_front(rows, criteria))
        norm = {c.key: normalize([r[c.key] for r in rows], c.maximize) for c in criteria}

        order = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)
        ranked: list[ScoredCandidate] = []
        for rank, i in enumerate(order, start=1):
            cand, total_cost, crowd, weather = enriched[i]
            dims = tuple(
                Dimension(key=c.key, raw=rows[i][c.key], normalized=norm[c.key][i], weight=c.weight)
                for c in criteria
            )
            ranked.append(
                ScoredCandidate(
                    candidate=cand,
                    total_cost=total_cost,
                    crowd_index=crowd,
                    weather_score=weather,
                    score=scores[i],
                    rank=rank,
                    on_pareto_front=i in front,
                    dimensions=dims,
                )
            )

        return DecisionObject(
            method=method,
            weights={c.key: c.weight for c in criteria},
            ranked=tuple(ranked),
            pareto_front=tuple(enriched[i][0].id for i in sorted(front)),
        )

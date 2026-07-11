"""End-to-end spine: registry → trip → cascade → MCDA → DecisionObject."""
from __future__ import annotations

import pytest

from core.candidate import Candidate, CandidateFacts, InMemoryFactsProvider
from core.cascade import recompute
from core.registry import FieldRegistry
from core.solve import SolveEngine
from core.trip import Trip


@pytest.fixture(scope="module")
def registry() -> FieldRegistry:
    return FieldRegistry.from_yaml()


def _trip(registry, *, weights) -> Trip:
    trip = Trip()
    trip.set_input("trip.park_days", 4)
    trip.set_input("trip.party.adults", 2)
    trip.set_input("trip.party.children", 2)
    trip.set_input("trip.addons.lightning_lane.tier", "multi_pass")
    trip.set_input("weights.cost", weights[0])
    trip.set_input("weights.crowd", weights[1])
    trip.set_input("weights.weather", weights[2])
    recompute(registry, trip, {
        "trip.park_days", "trip.party.adults", "trip.party.children",
        "trip.addons.lightning_lane.tier",
    })
    return trip


CANDIDATES = [
    Candidate("A", "WDW", "2026-03-02", "AKV-STU"),
    Candidate("B", "WDW", "2026-03-09", "AKV-STU"),
    Candidate("C", "WDW", "2026-03-16", "AKV-STU"),
]
FACTS = InMemoryFactsProvider({
    "A": CandidateFacts(base_cost=2000, crowd_index=30, weather_score=0.8),
    "B": CandidateFacts(base_cost=2500, crowd_index=10, weather_score=0.6),
    "C": CandidateFacts(base_cost=1800, crowd_index=50, weather_score=0.9),
})


def test_decision_object_is_structured_and_ranked(registry):
    trip = _trip(registry, weights=(0.5, 0.3, 0.2))
    decision = SolveEngine().solve(trip, CANDIDATES, FACTS)

    # Structured, not prose.
    assert decision.method == "weighted_sum"
    assert [sc.candidate.id for sc in decision.ranked] == ["C", "A", "B"]
    assert decision.top.candidate.id == "C"
    assert decision.top.rank == 1

    # Total cost folds in the DERIVED add-ons: base + tickets(2609.44) + LL(560.0).
    assert decision.top.total_cost == 1800 + 2609.44 + 560.0

    # Score decomposed by dimension for legibility.
    dims = {d.key: d for d in decision.top.dimensions}
    assert set(dims) == {"cost", "crowd", "weather"}
    assert all(0.0 <= d.normalized <= 1.0 for d in decision.top.dimensions)


def test_all_three_on_pareto_front(registry):
    trip = _trip(registry, weights=(0.5, 0.3, 0.2))
    decision = SolveEngine().solve(trip, CANDIDATES, FACTS)
    assert set(decision.pareto_front) == {"A", "B", "C"}


def test_reweighting_reranks_without_refetch(registry):
    # Crowd-heavy weights flip the winner to B (best crowd) — CQRS re-rank (§4.6).
    trip = _trip(registry, weights=(0.1, 0.8, 0.1))
    decision = SolveEngine().solve(trip, CANDIDATES, FACTS)
    assert decision.top.candidate.id == "B"

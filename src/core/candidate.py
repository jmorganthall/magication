"""Candidates and their facts (PRD §4.1, §4.2).

A candidate = (destination × week × accommodation). Its facts (base cost, crowd,
weather) come from a FactsProvider port — synthetic/in-memory in Phase 1; real
adapters plug in behind the same port in Phase 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class Candidate:
    id: str
    destination: str
    week: str  # ISO date of the week start
    accommodation: str


@dataclass(frozen=True)
class CandidateFacts:
    base_cost: float      # accommodation + week-variable costs (lower is better)
    crowd_index: float    # deterministic wait-time proxy (lower is better)
    weather_score: float  # climatology expectation in [0, 1] (higher is better)


class FactsProvider(Protocol):
    def facts(self, candidate: Candidate) -> CandidateFacts:
        ...


class InMemoryFactsProvider:
    """Phase 1 stand-in — real weather/crowd adapters arrive in Phase 2."""

    def __init__(self, facts_by_id: Mapping[str, CandidateFacts]) -> None:
        self._facts = dict(facts_by_id)

    def facts(self, candidate: Candidate) -> CandidateFacts:
        if candidate.id not in self._facts:
            raise KeyError(f"no facts for candidate {candidate.id!r}")
        return self._facts[candidate.id]

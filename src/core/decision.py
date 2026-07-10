"""The structured decision object (PRD §4.5) — never prose.

The consumer UI and the agent-facing client-shareable proposal are two rendering
adapters over this same object, so the core must never emit formatted text.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.candidate import Candidate


@dataclass(frozen=True)
class Dimension:
    """One objective's contribution, surfaced so the ranking is legible (§4.3)."""

    key: str
    raw: float
    normalized: float  # [0, 1], higher = better
    weight: float


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    total_cost: float
    crowd_index: float
    weather_score: float
    score: float
    rank: int
    on_pareto_front: bool
    dimensions: tuple[Dimension, ...]


@dataclass(frozen=True)
class DecisionObject:
    method: str                      # "weighted_sum" | "topsis"
    weights: dict[str, float]
    ranked: tuple[ScoredCandidate, ...]
    pareto_front: tuple[str, ...]    # candidate ids on the non-dominated frontier

    @property
    def top(self) -> ScoredCandidate | None:
        return self.ranked[0] if self.ranked else None

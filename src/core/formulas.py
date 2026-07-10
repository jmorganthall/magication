"""Deterministic DERIVED formulas and FETCHED providers (PRD §4.2, §18).

Rate constants live in an editable CSV under /inputs (a rate change is a data
edit, not a code deploy — §18). No AI here: same inputs → same numbers, always.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True)
class Rule:
    """A computed field: the inputs it reads and the pure function that folds them.

    `inputs` is the contract the completeness validator checks against depends_on.
    """

    inputs: tuple[str, ...]
    fn: Callable[[Mapping[str, object]], object]


# ── rate card ────────────────────────────────────────────────────────────────
def _default_rate_card_path() -> Path:
    env = os.getenv("RATE_CARD_PATH")
    if env:
        return Path(env)
    # src/core/formulas.py → parents[2] == repo root → inputs/rate_card.csv
    return Path(__file__).resolve().parents[2] / "inputs" / "rate_card.csv"


_rate_cache: dict[str, dict[str, float]] = {}


def load_rate_card(path: str | Path | None = None) -> dict[str, float]:
    p = Path(path) if path else _default_rate_card_path()
    key = str(p)
    if key in _rate_cache:
        return _rate_cache[key]
    if not p.exists():
        raise FileNotFoundError(f"rate card not found: {p} (set RATE_CARD_PATH)")
    card: dict[str, float] = {}
    with p.open(newline="") as fh:
        for row in csv.DictReader(fh):
            card[row["key"]] = float(row["value"])
    _rate_cache[key] = card
    return card


# ── helpers ──────────────────────────────────────────────────────────────────
def _guests(inp: Mapping[str, object]) -> int:
    return int(inp["trip.party.adults"]) + int(inp["trip.party.children"])


# ── computed fields ──────────────────────────────────────────────────────────
def _tickets_estimated_cost(inp: Mapping[str, object]) -> float:
    card = load_rate_card()
    days = int(inp["trip.park_days"])
    per_person = card["ticket_base_per_day"] * days + card["ticket_fixed_overhead"]
    return round(per_person * _guests(inp), 2)


def _ll_price_per_day(inp: Mapping[str, object]) -> float:
    """FETCHED at L2; at L1 seeded directionally from the rate card by tier."""
    card = load_rate_card()
    tier = inp["trip.addons.lightning_lane.tier"]
    return card[f"ll_price_per_day_{tier}"]


def _ll_estimated_cost(inp: Mapping[str, object]) -> float:
    days = int(inp["trip.park_days"])
    price = float(inp["trip.addons.lightning_lane.price_per_day"])
    return round(price * days * _guests(inp), 2)


# DERIVED fields → their formulas.
FORMULAS: dict[str, Rule] = {
    "trip.tickets.estimated_cost": Rule(
        inputs=("trip.park_days", "trip.party.adults", "trip.party.children"),
        fn=_tickets_estimated_cost,
    ),
    "trip.addons.lightning_lane.estimated_cost": Rule(
        inputs=(
            "trip.addons.lightning_lane.price_per_day",
            "trip.park_days",
            "trip.party.adults",
            "trip.party.children",
        ),
        fn=_ll_estimated_cost,
    ),
}

# FETCHED fields → their providers (adapters in Phase 2; rate-card stub at L1).
FETCHERS: dict[str, Rule] = {
    "trip.addons.lightning_lane.price_per_day": Rule(
        inputs=("trip.addons.lightning_lane.tier",),
        fn=_ll_price_per_day,
    ),
}

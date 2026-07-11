"""Recompute cascade: dirty propagation recomputes DERIVED/FETCHED deterministically."""
from __future__ import annotations

import pytest

from core.cascade import recompute
from core.registry import FieldRegistry
from core.trip import Trip


@pytest.fixture(scope="module")
def registry() -> FieldRegistry:
    return FieldRegistry.from_yaml()


def _seed(trip: Trip) -> None:
    trip.set_input("trip.park_days", 4)
    trip.set_input("trip.party.adults", 2)
    trip.set_input("trip.party.children", 2)
    trip.set_input("trip.addons.lightning_lane.tier", "multi_pass")


def test_tickets_and_ll_cost_computed(registry):
    trip = Trip()
    _seed(trip)
    recompute(registry, trip, {
        "trip.park_days", "trip.party.adults", "trip.party.children",
        "trip.addons.lightning_lane.tier",
    })
    # per_person = 65*4 + 392.36 = 652.36; ×4 guests = 2609.44
    assert trip.value("trip.tickets.estimated_cost") == 2609.44
    # FETCHED price seeded from rate card (multi_pass = 35); LL = 35*4*4 = 560.0
    assert trip.value("trip.addons.lightning_lane.price_per_day") == 35.0
    assert trip.value("trip.addons.lightning_lane.estimated_cost") == 560.0


def test_changing_tier_cascades_through_fetched_price(registry):
    trip = Trip()
    _seed(trip)
    recompute(registry, trip, {"trip.park_days", "trip.party.adults",
                               "trip.party.children", "trip.addons.lightning_lane.tier"})

    # Change only the tier → dirties the FETCHED price → dirties the DERIVED LL cost.
    trip.set_input("trip.addons.lightning_lane.tier", "premier")
    changed = recompute(registry, trip, {"trip.addons.lightning_lane.tier"})

    assert "trip.addons.lightning_lane.price_per_day" in changed
    assert "trip.addons.lightning_lane.estimated_cost" in changed
    assert trip.value("trip.addons.lightning_lane.price_per_day") == 449.0
    assert trip.value("trip.addons.lightning_lane.estimated_cost") == 449.0 * 4 * 4
    # Tickets untouched — not downstream of tier.
    assert trip.value("trip.tickets.estimated_cost") == 2609.44


def test_partial_trip_does_not_crash(registry):
    # Only park_days set: formulas needing party size are skipped, not errored.
    trip = Trip()
    trip.set_input("trip.park_days", 3)
    recompute(registry, trip, {"trip.park_days"})
    assert not trip.has("trip.tickets.estimated_cost")

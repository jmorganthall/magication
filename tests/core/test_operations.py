"""Operation model: the provenance firewall, simulate/commit/branch, the log."""
from __future__ import annotations

import pytest

from core.operations import (
    Actor,
    ForbiddenOperation,
    Operation,
    OperationLog,
    OpKind,
    apply_operation,
)
from core.registry import FieldRegistry, UnknownField
from core.trip import Trip


@pytest.fixture(scope="module")
def registry() -> FieldRegistry:
    return FieldRegistry.from_yaml()


def _baseline(registry) -> Trip:
    trip = Trip()
    for op in [
        Operation(OpKind.COMMIT_SET, "trip.park_days", 4),
        Operation(OpKind.COMMIT_SET, "trip.party.adults", 2),
        Operation(OpKind.COMMIT_SET, "trip.party.children", 2),
        Operation(OpKind.COMMIT_SET, "trip.addons.lightning_lane.tier", "multi_pass"),
    ]:
        apply_operation(registry, trip, op)
    return trip


def test_commit_sets_input_and_cascades(registry):
    trip = _baseline(registry)
    assert trip.value("trip.tickets.estimated_cost") == 2609.44


def test_firewall_rejects_setting_derived(registry):
    trip = _baseline(registry)
    with pytest.raises(ForbiddenOperation):
        apply_operation(registry, trip,
                        Operation(OpKind.COMMIT_SET, "trip.tickets.estimated_cost", 1.0))


def test_firewall_rejects_setting_fetched(registry):
    trip = _baseline(registry)
    with pytest.raises(ForbiddenOperation):
        apply_operation(registry, trip,
                        Operation(OpKind.COMMIT_SET, "trip.addons.lightning_lane.price_per_day", 5.0))


def test_unknown_field_raises(registry):
    with pytest.raises(UnknownField):
        apply_operation(registry, Trip(), Operation(OpKind.READ, "trip.nope"))


def test_simulate_does_not_touch_baseline(registry):
    trip = _baseline(registry)
    before = trip.value("trip.addons.lightning_lane.estimated_cost")

    result = apply_operation(registry, trip,
                             Operation(OpKind.SIMULATE_SET, "trip.addons.lightning_lane.tier", "premier"))

    # Baseline unchanged; the branch reflects the simulated change.
    assert trip.value("trip.addons.lightning_lane.estimated_cost") == before
    assert result.trip.value("trip.addons.lightning_lane.tier") == "premier"
    assert "trip.addons.lightning_lane.estimated_cost" in result.changed
    assert not result.committed


def test_ai_edit_is_tagged_ai_proposed(registry):
    trip = _baseline(registry)
    apply_operation(registry, trip,
                    Operation(OpKind.COMMIT_SET, "trip.park_days", 5, actor=Actor.AI))
    assert trip.get("trip.park_days").origin == "ai-proposed"


def test_operation_log_fold_and_undo(registry):
    log = OperationLog()
    log.record(Operation(OpKind.COMMIT_SET, "trip.park_days", 4))
    log.record(Operation(OpKind.COMMIT_SET, "trip.party.adults", 2))
    log.record(Operation(OpKind.COMMIT_SET, "trip.party.children", 2))

    folded = log.fold(registry)
    assert folded.value("trip.tickets.estimated_cost") == 2609.44

    # Undo the last commit → children unset → tickets can't compute.
    assert log.undo() is True
    folded2 = log.fold(registry)
    assert not folded2.has("trip.tickets.estimated_cost")


def test_log_rejects_non_commit(registry):
    log = OperationLog()
    with pytest.raises(ValueError):
        log.record(Operation(OpKind.SIMULATE_SET, "trip.park_days", 4))

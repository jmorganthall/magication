"""Field Registry: loading, alias resolution, validation, the DAG."""
from __future__ import annotations

import pytest

from core.registry import (
    FieldRegistry,
    Provenance,
    RegistryError,
    UnknownField,
    ValidationError,
)


@pytest.fixture(scope="module")
def registry() -> FieldRegistry:
    return FieldRegistry.from_yaml()


def test_loads_and_indexes(registry):
    assert "trip.park_days" in registry
    assert registry.get("trip.window.month").provenance is Provenance.USER_INPUT
    assert registry.get("trip.tickets.estimated_cost").provenance is Provenance.DERIVED
    assert registry.get("trip.addons.lightning_lane.price_per_day").provenance is Provenance.FETCHED


def test_alias_resolution_case_insensitive(registry):
    assert registry.resolve("LL Premier") == "trip.addons.lightning_lane.tier"
    assert registry.resolve("the premium skip-the-line thing") == "trip.addons.lightning_lane.tier"
    assert registry.resolve("kids") == "trip.party.children"
    with pytest.raises(UnknownField):
        registry.resolve("some unregistered phrase")


def test_validate_value(registry):
    assert registry.validate_value("trip.park_days", 4) == 4
    assert registry.validate_value("trip.addons.lightning_lane.tier", "premier") == "premier"
    with pytest.raises(ValidationError):
        registry.validate_value("trip.park_days", 0)          # below range
    with pytest.raises(ValidationError):
        registry.validate_value("trip.park_days", True)       # bool is not an int here
    with pytest.raises(ValidationError):
        registry.validate_value("trip.addons.lightning_lane.tier", "gold")  # not in domain
    with pytest.raises(ValidationError):
        registry.validate_value("weights.cost", 1.5)          # weight outside [0, 1]


def test_topological_order_puts_derived_after_inputs(registry):
    order = registry.topological_order()
    assert order.index("trip.addons.lightning_lane.tier") < order.index(
        "trip.addons.lightning_lane.price_per_day"
    )
    assert order.index("trip.addons.lightning_lane.price_per_day") < order.index(
        "trip.addons.lightning_lane.estimated_cost"
    )


def test_dependents(registry):
    deps = set(registry.dependents("trip.park_days"))
    assert "trip.tickets.estimated_cost" in deps
    assert "trip.addons.lightning_lane.estimated_cost" in deps


def test_user_input_may_not_declare_depends_on():
    bad = [
        {"path": "a", "type": "int_range", "domain": [0, 5], "provenance": "USER_INPUT"},
        {"path": "b", "type": "int_range", "domain": [0, 5], "provenance": "USER_INPUT",
         "depends_on": ["a"]},
    ]
    with pytest.raises(RegistryError):
        FieldRegistry(FieldRegistry._spec_from_dict(d) for d in bad)


def test_cycle_is_rejected():
    cyclic = [
        {"path": "a", "type": "number", "provenance": "DERIVED", "depends_on": ["b"]},
        {"path": "b", "type": "number", "provenance": "DERIVED", "depends_on": ["a"]},
    ]
    with pytest.raises(RegistryError):
        FieldRegistry(FieldRegistry._spec_from_dict(d) for d in cyclic)

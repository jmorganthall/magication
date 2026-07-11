"""The completeness validator (§6.3) — fails loud on an unmapped edge."""
from __future__ import annotations

import pytest

from core.cascade import CompletenessError, check_completeness
from core.formulas import Rule
from core.registry import FieldRegistry


def test_real_registry_is_complete():
    # The shipped registry + formulas/fetchers must wire cleanly.
    check_completeness(FieldRegistry.from_yaml())


def test_forgotten_edge_fails_loud():
    # A DERIVED field whose formula reads an input NOT in depends_on — the classic
    # "month → LL_estimate forgotten" silent-staleness bug.
    specs = [
        {"path": "x", "type": "int_range", "domain": [0, 9], "provenance": "USER_INPUT"},
        {"path": "y", "type": "int_range", "domain": [0, 9], "provenance": "USER_INPUT"},
        {"path": "z", "type": "number", "provenance": "DERIVED", "depends_on": ["x"]},
    ]
    registry = FieldRegistry(FieldRegistry._spec_from_dict(d) for d in specs)
    formulas = {"z": Rule(inputs=("x", "y"), fn=lambda inp: inp["x"] + inp["y"])}
    with pytest.raises(CompletenessError):
        check_completeness(registry, formulas=formulas, fetchers={})


def test_missing_formula_fails_loud():
    specs = [
        {"path": "x", "type": "int_range", "domain": [0, 9], "provenance": "USER_INPUT"},
        {"path": "z", "type": "number", "provenance": "DERIVED", "depends_on": ["x"]},
    ]
    registry = FieldRegistry(FieldRegistry._spec_from_dict(d) for d in specs)
    with pytest.raises(CompletenessError):
        check_completeness(registry, formulas={}, fetchers={})

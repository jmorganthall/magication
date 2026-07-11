"""Mechanical enforcement of the DATAMAP maintenance contract.

Every first-class object defined in `src/core` (a public, non-exception class —
dataclass, enum, protocol, or service) must be catalogued in DATAMAP.md, OR be
listed in EXEMPT with a reason. A new object added without a DATAMAP entry fails
this test — which is the whole point: the map cannot drift silently.
"""
from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

CORE_MODULES = [
    "core.registry",
    "core.trip",
    "core.formulas",
    "core.operations",
    "core.mcda",
    "core.candidate",
    "core.decision",
    "core.solve",
    "core.cascade",
]

# Objects intentionally without their own DATAMAP entry, each with a reason.
# Adding here is a conscious, reviewable decision — not a silent skip.
EXEMPT: dict[str, str] = {
    "OpKind": "enum documented within the Operation entry (§A)",
    "Actor": "enum documented within the Operation / Value entries (§A)",
    "OpResult": "internal return wrapper for apply_operation, not a domain object",
}

_DATAMAP = (Path(__file__).resolve().parents[2] / "DATAMAP.md").read_text()


def _first_class_classes() -> dict[str, str]:
    """{class_name: module} for public, non-exception classes defined in core."""
    found: dict[str, str] = {}
    for modname in CORE_MODULES:
        module = importlib.import_module(modname)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != modname:  # skip imported symbols
                continue
            if name.startswith("_") or issubclass(obj, Exception):
                continue
            found[name] = modname
    return found


def test_every_core_object_is_catalogued_in_datamap():
    missing = [
        f"{name} ({mod})"
        for name, mod in sorted(_first_class_classes().items())
        if name not in EXEMPT and not re.search(rf"\b{re.escape(name)}\b", _DATAMAP)
    ]
    assert not missing, (
        "First-class core objects missing from DATAMAP.md: "
        + ", ".join(missing)
        + " — add an entry (see the Maintenance contract) or add to EXEMPT with a reason."
    )


def test_exemptions_are_justified_and_current():
    classes = _first_class_classes()
    for name, reason in EXEMPT.items():
        assert reason, f"EXEMPT[{name!r}] must carry a reason"
        assert name in classes, f"EXEMPT lists {name!r} but no such core class exists — prune it"

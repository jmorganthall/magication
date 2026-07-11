"""The Trip document (PRD §10.6) — one source of truth for a trip's state.

Every value carries its provenance and an origin tag so an AI-proposed edit
never masquerades as a user assertion (§10.6). Branching is copy-on-write so
exploration never destroys the baseline (§10.4).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.registry import Provenance


@dataclass(frozen=True)
class Value:
    value: Any
    provenance: Provenance
    origin: str  # "user" | "ai-proposed" | "engine" | "fetched"


class Trip:
    def __init__(self) -> None:
        self._values: dict[str, Value] = {}

    # ── reads ─────────────────────────────────────────────────────────────────
    def has(self, path: str) -> bool:
        return path in self._values

    def get(self, path: str) -> Value | None:
        return self._values.get(path)

    def value(self, path: str) -> Any:
        return self._values[path].value

    def snapshot(self) -> dict[str, Any]:
        return {p: v.value for p, v in self._values.items()}

    # ── writes ────────────────────────────────────────────────────────────────
    def set_input(self, path: str, value: Any, origin: str = "user") -> None:
        self._values[path] = Value(value, Provenance.USER_INPUT, origin)

    def set_computed(self, path: str, value: Any, provenance: Provenance) -> None:
        origin = "fetched" if provenance is Provenance.FETCHED else "engine"
        self._values[path] = Value(value, provenance, origin)

    # ── branching (copy-on-write) ───────────────────────────────────────────────
    def branch(self) -> "Trip":
        clone = Trip()
        clone._values = dict(self._values)  # Value is frozen; entries are replaced, never mutated
        return clone

    def promote_from(self, other: "Trip") -> None:
        """Replace this trip's state with a branch's — commits the branch."""
        self._values = dict(other._values)

    def diff(self, other: "Trip") -> dict[str, tuple[Any, Any]]:
        """Paths whose value differs (self is 'new', other is 'old'): {path: (old, new)}."""
        changed: dict[str, tuple[Any, Any]] = {}
        for key in set(self._values) | set(other._values):
            new = self._values[key].value if key in self._values else None
            old = other._values[key].value if key in other._values else None
            if new != old:
                changed[key] = (old, new)
        return changed

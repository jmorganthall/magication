"""The Field Registry (PRD §6) — the keystone.

One registry powers NL resolution (aliases), schema validation (type/domain),
the recompute DAG (depends_on), paywall gating (maturity_level), and cost
metering (cost_to_obtain). Registered once, read everywhere.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


class Provenance(enum.Enum):
    USER_INPUT = "USER_INPUT"  # the only class settable via operations (the LLM firewall)
    DERIVED = "DERIVED"        # engine-computed, deterministic
    FETCHED = "FETCHED"        # adapter-supplied


class Maturity(enum.Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class CostToObtain(enum.Enum):
    FREE_SHARED = "free_shared"
    CACHED = "cached"
    METERED = "metered"


class RegistryError(RuntimeError):
    """Structural problem in the registry itself (fail loud at load)."""


class UnknownField(KeyError):
    pass


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class FieldSpec:
    path: str
    type: str
    provenance: Provenance
    domain: Any = None
    aliases: tuple[str, ...] = ()
    description: str = ""
    depends_on: tuple[str, ...] = ()
    maturity_level: Maturity = Maturity.L0
    cost_to_obtain: CostToObtain = CostToObtain.FREE_SHARED


class FieldRegistry:
    def __init__(self, specs: Iterable[FieldSpec]) -> None:
        self._by_path: dict[str, FieldSpec] = {}
        self._alias: dict[str, str] = {}
        for spec in specs:
            if spec.path in self._by_path:
                raise RegistryError(f"duplicate field path: {spec.path}")
            self._by_path[spec.path] = spec
            self._index_alias(spec.path.lower(), spec.path)
            for alias in spec.aliases:
                self._index_alias(alias.lower(), spec.path)
        self._validate_edges()
        self._topo_order = self._compute_topo_order()

    # ── construction ──────────────────────────────────────────────────────────
    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> "FieldRegistry":
        p = Path(path) if path else Path(__file__).with_name("fields.yaml")
        raw = yaml.safe_load(p.read_text())
        return cls(cls._spec_from_dict(d) for d in raw)

    @staticmethod
    def _spec_from_dict(d: dict) -> FieldSpec:
        return FieldSpec(
            path=d["path"],
            type=d["type"],
            provenance=Provenance(d["provenance"]),
            domain=d.get("domain"),
            aliases=tuple(d.get("aliases") or ()),
            description=d.get("description", ""),
            depends_on=tuple(d.get("depends_on") or ()),
            maturity_level=Maturity(d.get("maturity_level", "L0")),
            cost_to_obtain=CostToObtain(d.get("cost_to_obtain", "free_shared")),
        )

    def _index_alias(self, key: str, path: str) -> None:
        existing = self._alias.get(key)
        if existing is not None and existing != path:
            raise RegistryError(f"alias collision: {key!r} → {existing} and {path}")
        self._alias[key] = path

    # ── lookup ────────────────────────────────────────────────────────────────
    def get(self, path: str) -> FieldSpec:
        try:
            return self._by_path[path]
        except KeyError:
            raise UnknownField(path) from None

    def __contains__(self, path: str) -> bool:
        return path in self._by_path

    def paths(self) -> list[str]:
        return list(self._by_path)

    def specs(self) -> list[FieldSpec]:
        return list(self._by_path.values())

    def resolve(self, token: str) -> str:
        """Resolve a path or alias (case-insensitive) to a canonical path."""
        key = token.strip().lower()
        if key in self._alias:
            return self._alias[key]
        raise UnknownField(token)

    # ── validation ────────────────────────────────────────────────────────────
    def validate_value(self, path: str, value: Any) -> Any:
        spec = self.get(path)
        t = spec.type
        if t == "enum":
            if value not in (spec.domain or []):
                raise ValidationError(f"{path}: {value!r} not in {spec.domain}")
            return value
        if t == "int_range":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError(f"{path}: expected int, got {value!r}")
            lo, hi = spec.domain
            if not (lo <= value <= hi):
                raise ValidationError(f"{path}: {value} outside [{lo}, {hi}]")
            return value
        if t in ("number", "currency"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError(f"{path}: expected number, got {value!r}")
            v = float(value)
            if spec.domain:
                lo, hi = spec.domain
                if not (lo <= v <= hi):
                    raise ValidationError(f"{path}: {v} outside [{lo}, {hi}]")
            if t == "currency" and v < 0:
                raise ValidationError(f"{path}: currency cannot be negative ({v})")
            return v
        raise RegistryError(f"unknown field type {t!r} for {path}")

    # ── the DAG ───────────────────────────────────────────────────────────────
    def dependents(self, path: str) -> list[str]:
        """Direct dependents — fields that declare `path` in their depends_on."""
        return [s.path for s in self._by_path.values() if path in s.depends_on]

    def topological_order(self) -> list[str]:
        return list(self._topo_order)

    def _validate_edges(self) -> None:
        for spec in self._by_path.values():
            for dep in spec.depends_on:
                if dep not in self._by_path:
                    raise RegistryError(f"{spec.path} depends_on unknown field {dep!r}")
            if spec.provenance is Provenance.USER_INPUT and spec.depends_on:
                raise RegistryError(f"USER_INPUT {spec.path} must not declare depends_on")

    def _compute_topo_order(self) -> list[str]:
        adj: dict[str, list[str]] = {p: [] for p in self._by_path}
        indeg: dict[str, int] = {p: 0 for p in self._by_path}
        for spec in self._by_path.values():
            for dep in spec.depends_on:
                adj[dep].append(spec.path)
                indeg[spec.path] += 1
        queue = [p for p, d in indeg.items() if d == 0]
        order: list[str] = []
        while queue:
            node = queue.pop()
            order.append(node)
            for nxt in adj[node]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    queue.append(nxt)
        if len(order) != len(self._by_path):
            raise RegistryError("dependency cycle detected in registry")
        return order

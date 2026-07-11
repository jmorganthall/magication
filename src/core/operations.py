"""The operation model + operation log (PRD §10).

Chat/UI never edit state directly — they emit constrained operations. The engine
validates them against the registry, applies them to a copy-on-write branch, and
runs the recompute cascade. The provenance firewall means an operation may only
set USER_INPUT fields; DERIVED/FETCHED are engine/adapter-owned (§6.1).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Mapping

from core.cascade import recompute
from core.formulas import FETCHERS, FORMULAS, Rule
from core.registry import FieldRegistry, Provenance
from core.trip import Trip


class OpKind(enum.Enum):
    READ = "read"
    SIMULATE_SET = "simulate_set"  # apply to a branch — the default (§10.4)
    COMMIT_SET = "commit_set"      # promote onto the baseline


class Actor(enum.Enum):
    USER = "user"
    AI = "ai"


class ForbiddenOperation(RuntimeError):
    """The provenance firewall rejected the operation (§6.1)."""


@dataclass(frozen=True)
class Operation:
    kind: OpKind
    path: str
    value: Any = None
    actor: Actor = Actor.USER


@dataclass
class OpResult:
    trip: Trip                      # the resulting trip (a branch for simulate, the baseline for commit)
    changed: dict[str, tuple[Any, Any]]
    committed: bool
    read: Any = None


def apply_operation(
    registry: FieldRegistry,
    baseline: Trip,
    op: Operation,
    formulas: Mapping[str, Rule] = FORMULAS,
    fetchers: Mapping[str, Rule] = FETCHERS,
) -> OpResult:
    spec = registry.get(op.path)  # raises UnknownField for an unregistered target

    if op.kind is OpKind.READ:
        value = baseline.value(op.path) if baseline.has(op.path) else None
        return OpResult(trip=baseline, changed={}, committed=False, read=value)

    # SET — the firewall: only USER_INPUT is settable via an operation.
    if spec.provenance is not Provenance.USER_INPUT:
        raise ForbiddenOperation(
            f"{op.path} is {spec.provenance.value}; operations may only set USER_INPUT fields"
        )

    value = registry.validate_value(op.path, op.value)
    origin = "ai-proposed" if op.actor is Actor.AI else "user"

    work = baseline.branch()
    work.set_input(op.path, value, origin)
    recompute(registry, work, {op.path}, formulas, fetchers)
    changed = work.diff(baseline)

    committed = op.kind is OpKind.COMMIT_SET
    if committed:
        baseline.promote_from(work)
        return OpResult(trip=baseline, changed=changed, committed=True)
    return OpResult(trip=work, changed=changed, committed=False)


class OperationLog:
    """Current trip state = a fold over its operation log (PRD §10.5).

    Append-only; gives free undo, audit, and replay. Only COMMIT_SET ops mutate
    state (simulate/read are exploration and are not recorded here)."""

    def __init__(self) -> None:
        self._ops: list[Operation] = []

    def record(self, op: Operation) -> None:
        if op.kind is not OpKind.COMMIT_SET:
            raise ValueError("only COMMIT_SET operations are recorded in the log")
        self._ops.append(op)

    def operations(self) -> list[Operation]:
        return list(self._ops)

    def undo(self) -> bool:
        """Drop the most recent committed operation. Returns False if empty."""
        if not self._ops:
            return False
        self._ops.pop()
        return True

    def fold(
        self,
        registry: FieldRegistry,
        formulas: Mapping[str, Rule] = FORMULAS,
        fetchers: Mapping[str, Rule] = FETCHERS,
    ) -> Trip:
        trip = Trip()
        for op in self._ops:
            origin = "ai-proposed" if op.actor is Actor.AI else "user"
            trip.set_input(op.path, registry.validate_value(op.path, op.value), origin)
            recompute(registry, trip, {op.path}, formulas, fetchers)
        return trip

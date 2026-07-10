"""Ports (interfaces) for wait-time ingestion — the hexagonal boundary (PRD §2.3).

The poller depends only on these Protocols; concrete adapters (Queue-Times,
Postgres) are injected. This keeps the ingestion core ignorant of HTTP and SQL.
"""
from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from moat.models import WaitObservation


@runtime_checkable
class WaitTimesSource(Protocol):
    """A driven adapter that yields current wait observations for a park."""

    name: str

    def fetch_park(self, park_id: int, park_name: str) -> Sequence[WaitObservation]:
        ...


@runtime_checkable
class WaitTimeRepository(Protocol):
    """A driven adapter that appends observations to the history log."""

    def save_many(self, observations: Sequence[WaitObservation]) -> int:
        """Persist observations; returns the number of new rows written."""
        ...

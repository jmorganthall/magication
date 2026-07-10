"""Domain value objects for the accumulation layer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WaitObservation:
    """A single perishable wait-time reading for one ride at one instant."""

    park_id: int
    park_name: str
    ride_id: int
    ride_name: str
    is_open: bool
    wait_minutes: int | None  # None when the ride is closed / wait unknown
    source: str
    observed_at: datetime

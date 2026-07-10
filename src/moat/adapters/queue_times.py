"""Queue-Times adapter (PRD §8.2).

Free real-time wait-time API, 80+ parks, attribution required (queue-times.com).
Commercial-compatible via attribution — this is the day-0 feed that seeds the moat.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

import httpx

from moat.models import WaitObservation

BASE_URL = "https://queue-times.com"
_USER_AGENT = "magication-moat/0.0 (+data via queue-times.com, attribution required)"


class QueueTimesError(RuntimeError):
    """Raised on unrecoverable parse problems — we fail loud, never silent-bucket (§18)."""


def _parse_last_updated(raw: str | None) -> datetime:
    if not raw:
        # No timestamp from source → stamp with ingest time so the row is still keyable.
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - defensive
        raise QueueTimesError(f"unparseable last_updated: {raw!r}") from exc


class QueueTimesSource:
    name = "queue-times"

    def __init__(self, client: httpx.Client | None = None, base_url: str = BASE_URL) -> None:
        self._client = client or httpx.Client(
            timeout=15.0, headers={"User-Agent": _USER_AGENT}
        )
        self._base_url = base_url.rstrip("/")

    # ── park discovery ────────────────────────────────────────────────────────
    def fetch_parks_index(self) -> dict[str, int]:
        """Return {park_name: park_id} across all companies."""
        resp = self._client.get(f"{self._base_url}/parks.json")
        resp.raise_for_status()
        index: dict[str, int] = {}
        for company in resp.json():
            for park in company.get("parks", []):
                index[park["name"]] = park["id"]
        return index

    def resolve_park_ids(self, names: Sequence[str]) -> list[int]:
        """Resolve names → IDs, failing loud if a configured park is unknown."""
        index = self.fetch_parks_index()
        ids: list[int] = []
        for name in names:
            if name not in index:
                raise QueueTimesError(
                    f"park name not found in Queue-Times index (fail loud, not silent): {name!r}"
                )
            ids.append(index[name])
        return ids

    # ── observations ──────────────────────────────────────────────────────────
    def fetch_park(self, park_id: int, park_name: str) -> list[WaitObservation]:
        """Fetch current waits. The queue_times.json payload carries no park name,
        so it is supplied by the caller (the scheduler owns the id→name mapping)."""
        resp = self._client.get(f"{self._base_url}/parks/{park_id}/queue_times.json")
        resp.raise_for_status()
        payload = resp.json()

        # Rides live both at top level and nested under lands.
        rides = list(payload.get("rides", []))
        for land in payload.get("lands", []):
            rides.extend(land.get("rides", []))

        observations: list[WaitObservation] = []
        for ride in rides:
            is_open = bool(ride.get("is_open", False))
            observations.append(
                WaitObservation(
                    park_id=park_id,
                    park_name=park_name,
                    ride_id=ride["id"],
                    ride_name=ride["name"],
                    is_open=is_open,
                    wait_minutes=ride.get("wait_time") if is_open else None,
                    source=self.name,
                    observed_at=_parse_last_updated(ride.get("last_updated")),
                )
            )
        return observations

"""Postgres persistence adapter for wait observations (append-only history)."""
from __future__ import annotations

from typing import Sequence

import psycopg

from moat.models import WaitObservation

_INSERT_SQL = """
INSERT INTO wait_time_history
    (park_id, park_name, ride_id, ride_name, is_open, wait_minutes, source, observed_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (source, park_id, ride_id, observed_at) DO NOTHING
"""


class PgWaitTimeRepository:
    """Appends observations; idempotent via the natural-key unique constraint (§7.3)."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def save_many(self, observations: Sequence[WaitObservation]) -> int:
        if not observations:
            return 0
        rows = [
            (
                o.park_id,
                o.park_name,
                o.ride_id,
                o.ride_name,
                o.is_open,
                o.wait_minutes,
                o.source,
                o.observed_at,
            )
            for o in observations
        ]
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.executemany(_INSERT_SQL, rows)
                written = cur.rowcount
            conn.commit()
        # rowcount reflects rows actually inserted (conflicts skipped); guard negatives.
        return written if written and written > 0 else 0

"""The day-0 wait-time poller (PRD §13, §17 Phase 0).

Fans out across parks with per-park error isolation and exponential-backoff retry:
one flaky fetch degrades to a *gap*, never a total-run failure (§18).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Sequence, Tuple

from moat.ports.wait_times import WaitTimeRepository, WaitTimesSource

log = logging.getLogger("moat.wait_poller")

# (park_id, park_name)
Park = Tuple[int, str]


@dataclass(frozen=True)
class PollResult:
    parks_ok: int
    parks_failed: int
    observations: int
    saved: int


def _fetch_with_retry(
    source: WaitTimesSource,
    park: Park,
    max_retries: int,
    sleep: Callable[[float], None],
):
    park_id, park_name = park
    attempt = 0
    while True:
        try:
            return source.fetch_park(park_id, park_name)
        except Exception as exc:  # noqa: BLE001 - isolation boundary
            attempt += 1
            if attempt > max_retries:
                raise
            backoff = 2 ** attempt
            log.warning(
                "fetch failed for park %s (%s), retry %d/%d in %ds: %s",
                park_id, park_name, attempt, max_retries, backoff, exc,
            )
            sleep(backoff)


def poll_once(
    source: WaitTimesSource,
    repo: WaitTimeRepository,
    parks: Sequence[Park],
    *,
    max_retries: int = 4,
    sleep: Callable[[float], None] = time.sleep,
) -> PollResult:
    parks_ok = parks_failed = total_obs = total_saved = 0
    for park in parks:
        park_id, park_name = park
        try:
            observations = _fetch_with_retry(source, park, max_retries, sleep)
        except Exception:  # noqa: BLE001
            parks_failed += 1
            log.exception(
                "giving up on park %s (%s) this run; degrading to a gap, not a total failure",
                park_id, park_name,
            )
            continue

        parks_ok += 1
        total_obs += len(observations)
        try:
            total_saved += repo.save_many(observations)
        except Exception:  # noqa: BLE001 - persistence failure isolated per park
            log.exception("failed to persist observations for park %s (%s)", park_id, park_name)

    return PollResult(parks_ok, parks_failed, total_obs, total_saved)

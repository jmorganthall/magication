"""Poller error isolation + retry — in-memory fakes, no DB, no network."""
from __future__ import annotations

from datetime import datetime, timezone

from moat.ingest.wait_poller import poll_once
from moat.models import WaitObservation


class FakeSource:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[int] = []

    def fetch_park(self, park_id: int, park_name: str):
        self.calls.append(park_id)
        if park_id == 999:
            raise RuntimeError("boom")
        return [
            WaitObservation(park_id, park_name, 1, "Ride", True, 10, "fake",
                            datetime.now(timezone.utc))
        ]


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list[WaitObservation] = []

    def save_many(self, observations):
        self.saved.extend(observations)
        return len(observations)


def test_error_isolation_one_bad_park_does_not_sink_the_run():
    src, repo = FakeSource(), FakeRepo()
    parks = [(6, "Good"), (999, "Bad")]

    result = poll_once(src, repo, parks, max_retries=2, sleep=lambda _s: None)

    assert result.parks_ok == 1
    assert result.parks_failed == 1
    assert result.observations == 1
    assert result.saved == 1
    # bad park retried max_retries times after the initial attempt
    assert src.calls.count(999) == 3
    assert len(repo.saved) == 1  # good park still persisted


def test_all_parks_ok():
    src, repo = FakeSource(), FakeRepo()
    result = poll_once(src, repo, [(6, "A"), (7, "B")], max_retries=1, sleep=lambda _s: None)
    assert result.parks_ok == 2
    assert result.parks_failed == 0
    assert result.saved == 2

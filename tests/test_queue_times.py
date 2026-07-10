"""Queue-Times adapter parsing — no network (httpx.MockTransport)."""
from __future__ import annotations

import httpx
import pytest

from moat.adapters.queue_times import QueueTimesError, QueueTimesSource

QUEUE_JSON = {
    "lands": [
        {
            "id": 1,
            "name": "Fantasyland",
            "rides": [
                {"id": 101, "name": "Peter Pan's Flight", "is_open": True,
                 "wait_time": 45, "last_updated": "2024-06-01T12:00:00.000Z"},
                {"id": 102, "name": "It's a Small World", "is_open": False,
                 "wait_time": 0, "last_updated": "2024-06-01T12:00:00.000Z"},
            ],
        }
    ],
    "rides": [
        {"id": 200, "name": "Standalone Coaster", "is_open": True,
         "wait_time": 30, "last_updated": "2024-06-01T12:00:00.000Z"}
    ],
}

PARKS_JSON = [
    {"id": 1, "name": "Walt Disney Attractions", "parks": [
        {"id": 6, "name": "Disney Magic Kingdom"},
        {"id": 5, "name": "Epcot"},
    ]}
]


def _client(routes: dict[str, object]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        body = routes.get(request.url.path)
        if body is None:
            return httpx.Response(404)
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_park_parses_lands_and_toplevel_rides():
    src = QueueTimesSource(client=_client({"/parks/6/queue_times.json": QUEUE_JSON}))
    obs = src.fetch_park(6, "Disney Magic Kingdom")

    assert len(obs) == 3
    by_id = {o.ride_id: o for o in obs}
    assert by_id[101].wait_minutes == 45
    assert by_id[200].ride_name == "Standalone Coaster"  # top-level ride captured
    assert all(o.park_name == "Disney Magic Kingdom" for o in obs)
    assert all(o.source == "queue-times" for o in obs)


def test_closed_ride_has_no_wait():
    src = QueueTimesSource(client=_client({"/parks/6/queue_times.json": QUEUE_JSON}))
    closed = next(o for o in src.fetch_park(6, "MK") if o.ride_id == 102)
    assert closed.is_open is False
    assert closed.wait_minutes is None


def test_resolve_park_ids_fail_loud_on_unknown():
    src = QueueTimesSource(client=_client({"/parks.json": PARKS_JSON}))
    assert src.resolve_park_ids(["Epcot"]) == [5]
    with pytest.raises(QueueTimesError):
        src.resolve_park_ids(["Nonexistent Park"])

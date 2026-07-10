"""APScheduler worker entrypoint (`moat-poll`).

The first inhabitant of the ingestion layer (PRD §13). A self-contained scheduler
keeps Phase 0 runnable and testable; n8n is the eventual production home.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from moat.adapters.queue_times import QueueTimesSource
from moat.config import Config, load_config
from moat.db import PgWaitTimeRepository
from moat.ingest.wait_poller import Park, poll_once

log = logging.getLogger("moat.scheduler")

# Default Orlando park set, resolved to IDs by name against /parks.json at boot.
# Override with QUEUE_TIMES_PARK_IDS when Queue-Times naming drifts.
DEFAULT_PARK_NAMES = [
    "Disney Magic Kingdom",
    "Epcot",
    "Disney Hollywood Studios",
    "Disney Animal Kingdom",
    "Universal Studios At Universal Orlando",
    "Islands Of Adventure At Universal Orlando",
]


def resolve_parks(source: QueueTimesSource, cfg: Config) -> list[Park]:
    index = source.fetch_parks_index()  # name -> id
    if cfg.park_ids:
        by_id = {pid: name for name, pid in index.items()}
        parks = [(pid, by_id.get(pid, f"park {pid}")) for pid in cfg.park_ids]
    else:
        parks = []
        for name in DEFAULT_PARK_NAMES:
            if name not in index:
                log.warning("configured park not found in Queue-Times index, skipping: %s", name)
                continue
            parks.append((index[name], name))
    if not parks:
        raise RuntimeError(
            "no parks resolved — set QUEUE_TIMES_PARK_IDS or check Queue-Times park names"
        )
    return parks


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = load_config()
    source = QueueTimesSource()
    repo = PgWaitTimeRepository(cfg.database_url)
    parks = resolve_parks(source, cfg)
    log.info("polling %d parks every %ds", len(parks), cfg.poll_interval_seconds)

    def job() -> None:
        result = poll_once(source, repo, parks, max_retries=cfg.max_retries)
        log.info("poll complete: %s", result)

    job()  # bank a first snapshot immediately on boot
    scheduler = BlockingScheduler()
    scheduler.add_job(
        job,
        "interval",
        seconds=cfg.poll_interval_seconds,
        max_instances=1,
        coalesce=True,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover
        log.info("shutting down poller")


if __name__ == "__main__":  # pragma: no cover
    main()

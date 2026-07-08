# Task Checklist — Phase 0

- [x] `pyproject.toml` (package + deps)
- [x] `db/schema.sql` (wait_time_history + stub history tables)
- [x] `src/moat/config.py`, `models.py`, package `__init__`s
- [x] `src/moat/ports/wait_times.py` (ports)
- [x] `src/moat/adapters/queue_times.py` (Queue-Times adapter, fail-loud)
- [x] `src/moat/db.py` (Postgres repository, append-only)
- [x] `src/moat/ingest/wait_poller.py` (error isolation + retry)
- [x] `src/moat/scheduler.py` (APScheduler worker)
- [x] `Dockerfile`, `docker-compose.yml`, `.env.example`
- [x] `tests/` (parse, fail-loud, error isolation)
- [x] Verify: `pip install -e .[dev] && pytest` green (5 passed)
- [x] README Phase 0 + attribution note
- [x] Commit + push

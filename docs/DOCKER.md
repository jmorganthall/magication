# Docker template reference

The stack is defined in [`docker-compose.yml`](../docker-compose.yml) and built by the
multi-stage [`Dockerfile`](../Dockerfile). Everything defaults sensibly — `docker compose up`
works with no `.env` — and every value is overridable via a local `.env` (see
[`.env.example`](../.env.example)).

## Services

| Service | Image | Purpose | Default port |
|---|---|---|---|
| `postgres` | `postgres:16` | Durable reference store + history/operation logs (PRD §7.2). Loads `db/schema.sql` on first init. | `5432` |
| `redis` | `redis:7` | Ephemeral TTL cache (PRD §7.2). Persistence disabled — it's a cache. | `6379` |
| `open-meteo` | `ghcr.io/open-meteo/open-meteo` | Self-hosted weather (PRD §8.1). **Profile-gated** (`weather`). | `8080` |
| `poller` | built from `Dockerfile` | The day-0 wait-time poller (`moat-poll`). | — |

## Common commands

```bash
docker compose up -d                  # start postgres + redis + poller (detached)
docker compose --profile weather up   # also start the self-hosted Open-Meteo service
docker compose logs -f poller         # follow the poller
docker compose build poller           # rebuild after code changes
docker compose down                   # stop (keeps the pgdata volume)
docker compose down -v                # stop and DELETE the database volume
```

## Image design

- **Multi-stage build.** A `builder` stage produces a wheel; the `runtime` stage installs only that
  wheel — no build toolchain, smaller and faster to pull.
- **Non-root.** The runtime runs as uid `10001` (`moat`).
- **Healthcheck.** The container reports healthy while the package imports cleanly.
- **Versioning.** Inside the image, setuptools-scm resolves to `fallback_version` (the `.git` dir is
  excluded from the build context via `.dockerignore`). Real versions come from CI on push to `main`,
  not from local image builds — see [`RELEASING.md`](../RELEASING.md).

## Configuration

Compose-level (`POSTGRES_*`, `*_PORT`) and app-level (`DATABASE_URL`, `QUEUE_TIMES_PARK_IDS`,
`POLL_INTERVAL_SECONDS`, `HTTP_TIMEOUT_SECONDS`, `MAX_RETRIES`) knobs all live in `.env.example`.
The `poller` service builds its `DATABASE_URL` from the `POSTGRES_*` values, so you set credentials
in one place.

## Notes & gotchas

- **Schema loads once.** `db/schema.sql` runs only when the `pgdata` volume is first created. After
  editing the schema, either apply a migration by hand or recreate the volume with
  `docker compose down -v` (destroys data).
- **Ingestion before the app.** In Phase 0 the `poller` is the only app service; the API/UI join in
  later phases (PRD §17). n8n is the eventual production home for scheduled ingestion (PRD §13).
- **Production.** For real deployments, override `POSTGRES_PASSWORD`, avoid publishing DB/Redis ports
  to the host, and consider a managed Postgres over the in-compose one.

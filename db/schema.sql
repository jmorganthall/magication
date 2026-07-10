-- Phase 0 schema (PRD §7.6) — history tables committed from day 1.
-- These capture PERISHABLE observations: unrecoverable if not banked as they happen.
-- Cache-key discipline (§7.3): natural keys of the shared dimension only — NO tenant/user.

-- ─────────────────────────────────────────────────────────────────────────────
-- Live inhabitant of the ingestion layer: wait-time observations.
-- Source: Queue-Times / themeparks.wiki (attribution-licensed). Append-only.
CREATE TABLE IF NOT EXISTS wait_time_history (
    id            BIGSERIAL   PRIMARY KEY,
    park_id       INTEGER     NOT NULL,
    park_name     TEXT        NOT NULL,
    ride_id       INTEGER     NOT NULL,
    ride_name     TEXT        NOT NULL,
    is_open       BOOLEAN     NOT NULL,
    wait_minutes  INTEGER,                         -- NULL when closed / unknown
    source        TEXT        NOT NULL,            -- 'queue-times' | 'themeparks.wiki'
    observed_at   TIMESTAMPTZ NOT NULL,            -- the source's own last_updated
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Idempotency: re-polling before the source advances last_updated is a no-op.
    UNIQUE (source, park_id, ride_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_wait_hist_park_time ON wait_time_history (park_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_wait_hist_ride_time ON wait_time_history (ride_id, observed_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- STUB history tables (§7.6). Shipped in the schema now so a year of capturable
-- data is not lost before the corresponding adapters land in later phases.

CREATE TABLE IF NOT EXISTS offer_history (
    id           BIGSERIAL   PRIMARY KEY,
    offer_key    TEXT        NOT NULL,             -- natural key of the offer/promo
    title        TEXT,
    details      JSONB,
    source       TEXT        NOT NULL,
    observed_at  TIMESTAMPTZ NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_offer_hist_key_time ON offer_history (offer_key, observed_at);

CREATE TABLE IF NOT EXISTS flight_price_history (
    id           BIGSERIAL   PRIMARY KEY,
    origin       TEXT        NOT NULL,
    destination  TEXT        NOT NULL,
    depart_date  DATE        NOT NULL,
    return_date  DATE,
    price_cents  INTEGER     NOT NULL,
    currency     TEXT        NOT NULL DEFAULT 'USD',
    carrier      TEXT,
    source       TEXT        NOT NULL,
    observed_at  TIMESTAMPTZ NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_flight_hist_route_time
    ON flight_price_history (origin, destination, depart_date, observed_at);

CREATE TABLE IF NOT EXISTS room_price_history (
    id           BIGSERIAL   PRIMARY KEY,
    resort       TEXT        NOT NULL,
    room_type    TEXT        NOT NULL,
    stay_date    DATE        NOT NULL,
    price_cents  INTEGER,
    currency     TEXT        NOT NULL DEFAULT 'USD',
    source       TEXT        NOT NULL,
    observed_at  TIMESTAMPTZ NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_room_hist_resort_time
    ON room_price_history (resort, room_type, stay_date, observed_at);

-- DVC availability: each call is "X was available for date D, occupancy O, as seen on T" (§8.4).
-- room_type is SKU-derived upstream and must FAIL LOUD on an unknown SKU (§18) — never silent UNK.
CREATE TABLE IF NOT EXISTS dvc_availability_history (
    id                 BIGSERIAL   PRIMARY KEY,
    resort             TEXT        NOT NULL,
    room_type          TEXT        NOT NULL,
    stay_date          DATE        NOT NULL,
    occupancy          TEXT        NOT NULL,
    availability_level TEXT,
    point_cost         INTEGER,
    rental_cost_cents  INTEGER,
    source             TEXT        NOT NULL,
    observed_at        TIMESTAMPTZ NOT NULL,
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dvc_hist_resort_time
    ON dvc_availability_history (resort, room_type, stay_date, occupancy, observed_at);

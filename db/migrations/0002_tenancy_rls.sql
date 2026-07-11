-- Multi-tenancy floor (PRD §12.2): forced row-level security, fail-closed.
-- Isolation is enforced BELOW the application layer, so an app bug cannot cross
-- tenants. No tenant context ⇒ no rows, never all rows.

CREATE TABLE IF NOT EXISTS tenant (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    -- pool = shared DB + RLS (default); silo = dedicated schema/db (§12.3).
    isolation   TEXT NOT NULL DEFAULT 'pool' CHECK (isolation IN ('pool', 'silo')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_user (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenant(id),
    email       TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'member',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS trip (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenant(id),
    maturity    TEXT NOT NULL DEFAULT 'L1',
    state       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The operation log (PRD §10.5): trip state = a fold over these rows.
CREATE TABLE IF NOT EXISTS trip_operation (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenant(id),
    trip_id     UUID NOT NULL REFERENCES trip(id),
    seq         INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    path        TEXT NOT NULL,
    value       JSONB,
    actor       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (trip_id, seq)
);

-- Non-superuser application role (a superuser would bypass RLS entirely).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'moat_app') THEN
        CREATE ROLE moat_app NOLOGIN NOSUPERUSER;
    END IF;
END$$;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant, app_user, trip, trip_operation TO moat_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO moat_app;

-- ENABLE turns policies on; FORCE applies them even to the table owner, so no
-- role (short of superuser) can read cross-tenant.
ALTER TABLE tenant          ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_user        ENABLE ROW LEVEL SECURITY;
ALTER TABLE trip            ENABLE ROW LEVEL SECURITY;
ALTER TABLE trip_operation  ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant          FORCE ROW LEVEL SECURITY;
ALTER TABLE app_user        FORCE ROW LEVEL SECURITY;
ALTER TABLE trip            FORCE ROW LEVEL SECURITY;
ALTER TABLE trip_operation  FORCE ROW LEVEL SECURITY;

-- Fail-closed: current_setting('app.tenant_id', true) returns NULL when unset,
-- so the predicate is false and zero rows match. A forgotten tenant context can
-- never widen to all rows.
CREATE POLICY tenant_isolation ON tenant
    USING (id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY user_isolation ON app_user
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY trip_isolation ON trip
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY trip_op_isolation ON trip_operation
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Usage (set per request/session, below the app): SET app.tenant_id = '<uuid>';

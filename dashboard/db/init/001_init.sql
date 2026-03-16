-- ============================================
-- Schema: observability — core tables
-- ============================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS observability;

CREATE SEQUENCE IF NOT EXISTS observability.log_event_id_seq;

CREATE TABLE IF NOT EXISTS observability.log_operation (
    operation_id   TEXT PRIMARY KEY,
    route          TEXT NOT NULL,
    method         TEXT NOT NULL DEFAULT 'POST',
    client_ip      TEXT,
    id_user        TEXT,
    batch_size     INTEGER DEFAULT 1,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at    TIMESTAMPTZ,
    duration_ms    INTEGER,
    status         TEXT NOT NULL DEFAULT 'started',
    error_message  TEXT,
    attrs          JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_op_started  ON observability.log_operation (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_op_status   ON observability.log_operation (status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_op_user     ON observability.log_operation (id_user, started_at DESC) WHERE id_user IS NOT NULL;

CREATE TABLE IF NOT EXISTS observability.log_event (
    event_id       BIGINT NOT NULL DEFAULT nextval('observability.log_event_id_seq'),
    operation_id   TEXT,
    document_id    TEXT,
    expediente_key TEXT,
    id_user        TEXT,
    stage          TEXT NOT NULL,
    status         TEXT NOT NULL,
    is_error       BOOLEAN NOT NULL DEFAULT FALSE,
    error_code     TEXT,
    error_class    TEXT,
    message        TEXT,
    duration_ms    INTEGER,
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attrs          JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (occurred_at, event_id)
) PARTITION BY RANGE (occurred_at);

CREATE INDEX IF NOT EXISTS idx_evt_doc_time  ON observability.log_event (document_id, occurred_at DESC, event_id DESC)  WHERE document_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_evt_exp_time  ON observability.log_event (expediente_key, occurred_at DESC, event_id DESC) WHERE expediente_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_evt_stage     ON observability.log_event (stage, status, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_evt_errors    ON observability.log_event (occurred_at DESC, event_id DESC) WHERE is_error = true;
CREATE INDEX IF NOT EXISTS idx_evt_op        ON observability.log_event (operation_id, occurred_at DESC);

COMMIT;

-- ============================================
-- Observability: partition function + initial partitions
-- ============================================
BEGIN;

CREATE OR REPLACE FUNCTION observability.create_monthly_partition(target_date DATE)
RETURNS VOID AS $$
DECLARE
    p_name TEXT;
    p_start DATE;
    p_end   DATE;
BEGIN
    p_start := DATE_TRUNC('month', target_date)::DATE;
    p_end   := (p_start + INTERVAL '1 month')::DATE;
    p_name  := 'log_event_' || TO_CHAR(p_start, 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS observability.%I PARTITION OF observability.log_event FOR VALUES FROM (%L) TO (%L)',
        p_name, p_start, p_end
    );
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE d DATE;
BEGIN
    d := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    FOR i IN 0..17 LOOP
        PERFORM observability.create_monthly_partition((d + (i || ' months')::INTERVAL)::DATE);
    END LOOP;
END;
$$;

CREATE TABLE IF NOT EXISTS observability.log_event_default
    PARTITION OF observability.log_event DEFAULT;

COMMIT;

-- ============================================
-- Schema: dashboard_auth
-- ============================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS dashboard_auth;

CREATE TABLE IF NOT EXISTS dashboard_auth.users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'viewer',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dashboard_auth.sessions (
    id         TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES dashboard_auth.users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sess_user    ON dashboard_auth.sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sess_expires ON dashboard_auth.sessions (expires_at);

CREATE TABLE IF NOT EXISTS dashboard_auth.audit_login (
    id         SERIAL PRIMARY KEY,
    username   TEXT NOT NULL,
    success    BOOLEAN NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_time ON dashboard_auth.audit_login (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON dashboard_auth.audit_login (username, created_at DESC);

COMMIT;

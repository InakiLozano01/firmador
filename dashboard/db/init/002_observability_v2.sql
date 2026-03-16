BEGIN;

CREATE TABLE IF NOT EXISTS observability.operation_run (
    operation_id           UUID PRIMARY KEY,
    operation_key          TEXT NOT NULL,
    route                  TEXT NOT NULL,
    method                 TEXT NOT NULL,
    client_ip              TEXT,
    id_user                TEXT,
    batch_size             INTEGER DEFAULT 1,
    http_status_code       INTEGER,
    operation_status       TEXT NOT NULL DEFAULT 'running',
    request_content_type   TEXT,
    request_size_bytes     INTEGER,
    response_content_type  TEXT,
    response_size_bytes    INTEGER,
    started_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at            TIMESTAMPTZ,
    duration_ms            INTEGER,
    error_message          TEXT,
    attrs                  JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_operation_run_started ON observability.operation_run (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_run_key ON observability.operation_run (operation_key, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_run_status ON observability.operation_run (operation_status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_run_batch_expr ON observability.operation_run ((attrs ->> 'batch_id'));

CREATE TABLE IF NOT EXISTS observability.operation_subject (
    subject_id         BIGSERIAL PRIMARY KEY,
    operation_id       UUID NOT NULL REFERENCES observability.operation_run(operation_id) ON DELETE CASCADE,
    parent_subject_id  BIGINT REFERENCES observability.operation_subject(subject_id) ON DELETE SET NULL,
    subject_type       TEXT NOT NULL,
    subject_key        TEXT NOT NULL,
    display_name       TEXT,
    id_user            TEXT,
    subject_status     TEXT NOT NULL DEFAULT 'running',
    started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at        TIMESTAMPTZ,
    duration_ms        INTEGER,
    error_message      TEXT,
    attrs              JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (operation_id, subject_type, subject_key)
);

CREATE INDEX IF NOT EXISTS idx_operation_subject_type_key ON observability.operation_subject (subject_type, subject_key, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_subject_op_type ON observability.operation_subject (operation_id, subject_type);
CREATE INDEX IF NOT EXISTS idx_operation_subject_status ON observability.operation_subject (subject_status, started_at DESC);

CREATE TABLE IF NOT EXISTS observability.stage_run (
    stage_id          BIGSERIAL PRIMARY KEY,
    operation_id      UUID NOT NULL REFERENCES observability.operation_run(operation_id) ON DELETE CASCADE,
    subject_id        BIGINT REFERENCES observability.operation_subject(subject_id) ON DELETE SET NULL,
    parent_stage_id   BIGINT REFERENCES observability.stage_run(stage_id) ON DELETE SET NULL,
    stage_key         TEXT NOT NULL,
    stage_label       TEXT NOT NULL,
    stage_status      TEXT NOT NULL DEFAULT 'running',
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at       TIMESTAMPTZ,
    duration_ms       INTEGER,
    error_message     TEXT,
    error_class       TEXT,
    attrs             JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_stage_run_operation_time ON observability.stage_run (operation_id, started_at ASC);
CREATE INDEX IF NOT EXISTS idx_stage_run_subject_time ON observability.stage_run (subject_id, started_at ASC);
CREATE INDEX IF NOT EXISTS idx_stage_run_key_status ON observability.stage_run (stage_key, stage_status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_stage_run_parent ON observability.stage_run (parent_stage_id);
CREATE INDEX IF NOT EXISTS idx_stage_run_key_time ON observability.stage_run (stage_key, started_at DESC) WHERE duration_ms IS NOT NULL;

CREATE TABLE IF NOT EXISTS observability.stage_entry (
    entry_id            BIGINT GENERATED ALWAYS AS IDENTITY,
    operation_id        UUID NOT NULL REFERENCES observability.operation_run(operation_id) ON DELETE CASCADE,
    subject_id          BIGINT REFERENCES observability.operation_subject(subject_id) ON DELETE SET NULL,
    stage_id            BIGINT REFERENCES observability.stage_run(stage_id) ON DELETE SET NULL,
    entry_kind          TEXT NOT NULL,
    log_level           TEXT,
    logger_name         TEXT,
    title               TEXT,
    message             TEXT,
    payload_json        JSONB,
    payload_text        TEXT,
    payload_hash        TEXT,
    payload_bytes       INTEGER,
    payload_truncated   BOOLEAN NOT NULL DEFAULT FALSE,
    sanitized           BOOLEAN NOT NULL DEFAULT TRUE,
    http_method         TEXT,
    url                 TEXT,
    route               TEXT,
    status_code         INTEGER,
    error_code          TEXT,
    error_class         TEXT,
    stacktrace          TEXT,
    attrs               JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (occurred_at, entry_id)
) PARTITION BY RANGE (occurred_at);

CREATE INDEX IF NOT EXISTS idx_stage_entry_operation_time ON observability.stage_entry (operation_id, occurred_at DESC, entry_id DESC);
CREATE INDEX IF NOT EXISTS idx_stage_entry_stage_time ON observability.stage_entry (stage_id, occurred_at ASC, entry_id ASC);
CREATE INDEX IF NOT EXISTS idx_stage_entry_subject_time ON observability.stage_entry (subject_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_stage_entry_kind_time ON observability.stage_entry (entry_kind, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_stage_entry_errors ON observability.stage_entry (occurred_at DESC, entry_id DESC) WHERE entry_kind = 'error';
CREATE INDEX IF NOT EXISTS idx_stage_entry_logger_time ON observability.stage_entry (logger_name, occurred_at DESC) WHERE logger_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stage_entry_operation_kind_time ON observability.stage_entry (operation_id, entry_kind, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_stage_entry_batch_expr ON observability.stage_entry ((attrs ->> 'batch_id'));
CREATE INDEX IF NOT EXISTS idx_stage_entry_dependency_expr ON observability.stage_entry ((attrs ->> 'dependency'));
CREATE INDEX IF NOT EXISTS idx_stage_entry_context_result_expr ON observability.stage_entry ((attrs ->> 'context_result'));
CREATE INDEX IF NOT EXISTS idx_stage_entry_attempt_count_expr ON observability.stage_entry (((CASE WHEN (attrs ->> 'attempt_count') ~ '^-?[0-9]+$' THEN (attrs ->> 'attempt_count')::int ELSE NULL END))) WHERE attrs ? 'attempt_count';
CREATE INDEX IF NOT EXISTS idx_stage_entry_retryable_expr ON observability.stage_entry (((CASE WHEN LOWER(COALESCE(attrs ->> 'retryable', '')) IN ('true', 'false') THEN (attrs ->> 'retryable')::boolean ELSE NULL END))) WHERE attrs ? 'retryable';
CREATE INDEX IF NOT EXISTS idx_stage_entry_error_code ON observability.stage_entry (error_code, occurred_at DESC) WHERE error_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS observability.payload_vault (
    vault_id         BIGSERIAL,
    operation_id     UUID REFERENCES observability.operation_run(operation_id) ON DELETE CASCADE,
    subject_id       BIGINT REFERENCES observability.operation_subject(subject_id) ON DELETE SET NULL,
    stage_id         BIGINT REFERENCES observability.stage_run(stage_id) ON DELETE SET NULL,
    entry_kind       TEXT NOT NULL,
    route            TEXT,
    stage_key        TEXT,
    payload_hash     TEXT NOT NULL,
    content_kind     TEXT NOT NULL,
    ciphertext       BYTEA NOT NULL,
    nonce            BYTEA NOT NULL,
    algorithm        TEXT NOT NULL,
    compression      TEXT NOT NULL,
    raw_bytes        INTEGER NOT NULL,
    stored_bytes     INTEGER NOT NULL,
    truncated        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at       TIMESTAMPTZ NOT NULL,
    attrs            JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (created_at, vault_id)
) PARTITION BY RANGE (created_at);

CREATE INDEX IF NOT EXISTS idx_payload_vault_created ON observability.payload_vault (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payload_vault_expires ON observability.payload_vault (expires_at ASC);
CREATE INDEX IF NOT EXISTS idx_payload_vault_hash ON observability.payload_vault (payload_hash, created_at DESC);

CREATE TABLE IF NOT EXISTS observability.payload_reveal_audit (
    audit_id      BIGSERIAL PRIMARY KEY,
    vault_id      BIGINT NOT NULL,
    username      TEXT NOT NULL,
    action        TEXT NOT NULL,
    reason        TEXT,
    client_ip     TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attrs         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_payload_reveal_audit_time ON observability.payload_reveal_audit (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payload_reveal_audit_vault_time ON observability.payload_reveal_audit (vault_id, created_at DESC);

CREATE TABLE IF NOT EXISTS observability.runtime_status (
    service_name    TEXT PRIMARY KEY,
    instance_id     TEXT,
    queue_depth     INTEGER NOT NULL DEFAULT 0,
    dropped_events  BIGINT NOT NULL DEFAULT 0,
    last_flush_at   TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attrs           JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS observability.repair_manifest (
    manifest_id      BIGSERIAL PRIMARY KEY,
    operation_id     UUID REFERENCES observability.operation_run(operation_id) ON DELETE SET NULL,
    id_doc           TEXT,
    manifest_path    TEXT NOT NULL UNIQUE,
    target_path      TEXT NOT NULL,
    temp_path        TEXT NOT NULL,
    hash_doc         TEXT NOT NULL,
    payload_sha256   TEXT NOT NULL,
    bytes_written    INTEGER,
    status           TEXT NOT NULL DEFAULT 'pending',
    retryable        BOOLEAN NOT NULL DEFAULT TRUE,
    db_committed     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recovered_at     TIMESTAMPTZ,
    last_error       TEXT,
    attrs            JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_repair_manifest_status_time ON observability.repair_manifest (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_repair_manifest_operation ON observability.repair_manifest (operation_id, created_at DESC) WHERE operation_id IS NOT NULL;

CREATE OR REPLACE FUNCTION observability.create_stage_entry_monthly_partition(target_date DATE)
RETURNS VOID AS $$
DECLARE
    p_name TEXT;
    p_start DATE;
    p_end DATE;
BEGIN
    p_start := DATE_TRUNC('month', target_date)::DATE;
    p_end := (p_start + INTERVAL '1 month')::DATE;
    p_name := 'stage_entry_' || TO_CHAR(p_start, 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS observability.%I PARTITION OF observability.stage_entry FOR VALUES FROM (%L) TO (%L)',
        p_name, p_start, p_end
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION observability.create_payload_vault_monthly_partition(target_date DATE)
RETURNS VOID AS $$
DECLARE
    p_name TEXT;
    p_start DATE;
    p_end DATE;
BEGIN
    p_start := DATE_TRUNC('month', target_date)::DATE;
    p_end := (p_start + INTERVAL '1 month')::DATE;
    p_name := 'payload_vault_' || TO_CHAR(p_start, 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS observability.%I PARTITION OF observability.payload_vault FOR VALUES FROM (%L) TO (%L)',
        p_name, p_start, p_end
    );
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE d DATE;
BEGIN
    d := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    FOR i IN 0..17 LOOP
        PERFORM observability.create_stage_entry_monthly_partition((d + (i || ' months')::INTERVAL)::DATE);
        PERFORM observability.create_payload_vault_monthly_partition((d + (i || ' months')::INTERVAL)::DATE);
    END LOOP;
END;
$$;

CREATE TABLE IF NOT EXISTS observability.stage_entry_default
    PARTITION OF observability.stage_entry DEFAULT;

CREATE TABLE IF NOT EXISTS observability.payload_vault_default
    PARTITION OF observability.payload_vault DEFAULT;

CREATE OR REPLACE VIEW observability.v_stage_entry_enriched AS
SELECT
    e.entry_id::text AS entry_id,
    e.operation_id::text AS operation_id,
    e.subject_id::text AS subject_id,
    e.stage_id::text AS stage_id,
    e.entry_kind,
    e.log_level,
    e.logger_name,
    e.title,
    e.message,
    e.payload_json,
    e.payload_text,
    e.payload_hash,
    e.payload_bytes,
    e.payload_truncated,
    e.sanitized,
    e.http_method,
    e.url,
    e.route,
    e.status_code,
    e.error_code,
    e.error_class,
    e.stacktrace,
    e.attrs,
    e.occurred_at,
    s.stage_key,
    s.stage_label,
    s.stage_status,
    subj.subject_type,
    subj.subject_key,
    subj.display_name AS subject_display_name,
    subj.subject_status,
    op.operation_key,
    op.route AS operation_route,
    COALESCE(e.attrs ->> 'batch_id', s.attrs ->> 'batch_id', subj.attrs ->> 'batch_id', op.attrs ->> 'batch_id') AS batch_id,
    COALESCE(e.attrs ->> 'dependency', s.attrs ->> 'dependency') AS dependency,
    e.attrs ->> 'context_result' AS context_result,
    CASE
        WHEN e.attrs ? 'attempt_count' AND (e.attrs ->> 'attempt_count') ~ '^-?[0-9]+$'
        THEN (e.attrs ->> 'attempt_count')::int
        ELSE NULL
    END AS attempt_count,
    CASE
        WHEN e.attrs ? 'retryable' AND LOWER(COALESCE(e.attrs ->> 'retryable', '')) IN ('true', 'false')
        THEN (e.attrs ->> 'retryable')::boolean
        ELSE NULL
    END AS retryable,
    e.attrs ->> 'repair_manifest' AS repair_manifest,
    CASE
        WHEN e.attrs ? 'raw_payload_id' AND (e.attrs ->> 'raw_payload_id') ~ '^[0-9]+$'
        THEN (e.attrs ->> 'raw_payload_id')::bigint
        ELSE NULL
    END AS raw_payload_id,
    COALESCE(
        CASE
            WHEN e.attrs ? 'raw_payload_available' AND NULLIF(e.attrs ->> 'raw_payload_available', '') IS NOT NULL
            THEN (e.attrs ->> 'raw_payload_available')::boolean
            ELSE NULL
        END,
        FALSE
    ) AS raw_payload_available,
    COALESCE(
        CASE
            WHEN e.attrs ? 'raw_payload_truncated' AND NULLIF(e.attrs ->> 'raw_payload_truncated', '') IS NOT NULL
            THEN (e.attrs ->> 'raw_payload_truncated')::boolean
            ELSE NULL
        END,
        FALSE
    ) AS raw_payload_truncated
FROM observability.stage_entry e
LEFT JOIN observability.stage_run s ON s.stage_id = e.stage_id
LEFT JOIN observability.operation_subject subj ON subj.subject_id = e.subject_id
JOIN observability.operation_run op ON op.operation_id = e.operation_id;

CREATE OR REPLACE VIEW observability.v_operation_enriched AS
WITH batch_map AS (
    SELECT
        op.operation_id,
        COALESCE(op.attrs ->> 'batch_id', MAX(vse.batch_id)) AS batch_id
    FROM observability.operation_run op
    LEFT JOIN observability.v_stage_entry_enriched vse ON vse.operation_id::uuid = op.operation_id
    GROUP BY op.operation_id, op.attrs
),
entry_counts AS (
    SELECT
        operation_id::uuid AS operation_id,
        COUNT(*) FILTER (WHERE entry_kind = 'error')::int AS error_count,
        COUNT(*) FILTER (WHERE context_result = 'busy')::int AS context_busy_count,
        COUNT(*) FILTER (WHERE context_result = 'conflict')::int AS context_conflict_count,
        COUNT(*) FILTER (WHERE context_result = 'released')::int AS context_release_count,
        COUNT(*) FILTER (WHERE context_result = 'finalized')::int AS context_finalize_count,
        COUNT(*) FILTER (WHERE error_code = 'PDF_REPAIR_REQUIRED')::int AS repair_error_count
    FROM observability.v_stage_entry_enriched
    GROUP BY operation_id::uuid
),
repair_counts AS (
    SELECT
        operation_id,
        COUNT(*)::int AS repair_count,
        COUNT(*) FILTER (WHERE status = 'pending')::int AS pending_repair_count
    FROM observability.repair_manifest
    GROUP BY operation_id
),
subject_counts AS (
    SELECT
        operation_id,
        COUNT(*)::int AS subject_count
    FROM observability.operation_subject
    GROUP BY operation_id
),
stage_counts AS (
    SELECT
        operation_id,
        COUNT(*)::int AS stage_count
    FROM observability.stage_run
    GROUP BY operation_id
),
related_counts AS (
    SELECT
        batch_id,
        COUNT(*)::int AS related_operation_count
    FROM batch_map
    WHERE batch_id IS NOT NULL
    GROUP BY batch_id
)
SELECT
    op.operation_id::text AS operation_id,
    op.operation_key,
    op.route,
    op.method,
    op.client_ip,
    op.id_user,
    op.batch_size,
    op.http_status_code,
    op.operation_status,
    op.request_content_type,
    op.request_size_bytes,
    op.response_content_type,
    op.response_size_bytes,
    op.started_at,
    op.finished_at,
    op.duration_ms,
    op.error_message,
    op.attrs,
    batch_map.batch_id,
    COALESCE(entry_counts.error_count, 0) AS error_count,
    COALESCE(subject_counts.subject_count, 0) AS subject_count,
    COALESCE(stage_counts.stage_count, 0) AS stage_count,
    COALESCE(entry_counts.context_busy_count, 0) AS context_busy_count,
    COALESCE(entry_counts.context_conflict_count, 0) AS context_conflict_count,
    COALESCE(entry_counts.context_release_count, 0) AS context_release_count,
    COALESCE(entry_counts.context_finalize_count, 0) AS context_finalize_count,
    COALESCE(entry_counts.repair_error_count, 0) AS repair_error_count,
    COALESCE(repair_counts.repair_count, 0) AS repair_count,
    COALESCE(repair_counts.pending_repair_count, 0) AS pending_repair_count,
    GREATEST(COALESCE(related_counts.related_operation_count, 1) - 1, 0) AS related_operation_count
FROM observability.operation_run op
LEFT JOIN batch_map ON batch_map.operation_id = op.operation_id
LEFT JOIN entry_counts ON entry_counts.operation_id = op.operation_id
LEFT JOIN subject_counts ON subject_counts.operation_id = op.operation_id
LEFT JOIN stage_counts ON stage_counts.operation_id = op.operation_id
LEFT JOIN repair_counts ON repair_counts.operation_id = op.operation_id
LEFT JOIN related_counts ON related_counts.batch_id = batch_map.batch_id;

CREATE OR REPLACE VIEW observability.v_batch_summary AS
WITH op_summary AS (
    SELECT *
    FROM observability.v_operation_enriched
    WHERE batch_id IS NOT NULL
)
SELECT
    op_summary.batch_id,
    MIN(op_summary.started_at) AS first_seen_at,
    MAX(COALESCE(op_summary.finished_at, op_summary.started_at)) AS last_seen_at,
    COUNT(*)::int AS operation_count,
    COUNT(*) FILTER (WHERE op_summary.operation_status IN ('failed', 'partial_error', 'rejected'))::int AS flagged_operation_count,
    COUNT(DISTINCT subj.subject_key) FILTER (WHERE subj.subject_type = 'document')::int AS document_count,
    COUNT(DISTINCT subj.subject_key) FILTER (WHERE subj.subject_type = 'expediente')::int AS expediente_count,
    COALESCE(SUM(op_summary.error_count), 0)::int AS error_count,
    COALESCE(SUM(op_summary.repair_count), 0)::int AS repair_count,
    COALESCE(SUM(op_summary.pending_repair_count), 0)::int AS pending_repair_count,
    MAX(op_summary.context_busy_count)::int AS max_context_busy_count,
    MAX(op_summary.context_conflict_count)::int AS max_context_conflict_count
FROM op_summary
LEFT JOIN observability.operation_subject subj ON subj.operation_id::text = op_summary.operation_id
GROUP BY op_summary.batch_id;

CREATE OR REPLACE VIEW observability.v_repair_backlog AS
SELECT
    rm.manifest_id::text AS manifest_id,
    rm.operation_id::text AS operation_id,
    rm.id_doc,
    rm.manifest_path,
    rm.target_path,
    rm.temp_path,
    rm.hash_doc,
    rm.payload_sha256,
    rm.bytes_written,
    rm.status,
    rm.retryable,
    rm.db_committed,
    rm.created_at,
    rm.recovered_at,
    rm.last_error,
    rm.attrs,
    op.operation_key,
    op.route,
    COALESCE(op.attrs ->> 'batch_id', MAX(vse.batch_id)) AS batch_id
FROM observability.repair_manifest rm
LEFT JOIN observability.operation_run op ON op.operation_id = rm.operation_id
LEFT JOIN observability.v_stage_entry_enriched vse ON vse.operation_id::uuid = rm.operation_id
GROUP BY
    rm.manifest_id,
    rm.operation_id,
    rm.id_doc,
    rm.manifest_path,
    rm.target_path,
    rm.temp_path,
    rm.hash_doc,
    rm.payload_sha256,
    rm.bytes_written,
    rm.status,
    rm.retryable,
    rm.db_committed,
    rm.created_at,
    rm.recovered_at,
    rm.last_error,
    rm.attrs,
    op.operation_key,
    op.route,
    op.attrs;

COMMIT;

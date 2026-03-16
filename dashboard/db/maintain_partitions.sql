-- Run monthly (e.g. via cron or pg_cron) to create upcoming partitions
-- and optionally drop very old ones.
DO $$
DECLARE d DATE;
BEGIN
    d := DATE_TRUNC('month', CURRENT_DATE);
    FOR i IN 0..17 LOOP
        PERFORM observability.create_stage_entry_monthly_partition(d + (i || ' months')::INTERVAL);
        PERFORM observability.create_payload_vault_monthly_partition(d + (i || ' months')::INTERVAL);
    END LOOP;

    -- Optional: drop partitions older than 180 days
    -- EXECUTE format('DROP TABLE IF EXISTS observability.stage_entry_%s',
    --     TO_CHAR(CURRENT_DATE - INTERVAL '180 days', 'YYYY_MM'));
END;
$$;

DELETE FROM observability.payload_vault WHERE expires_at < NOW();

-- Purge expired dashboard sessions
DELETE FROM dashboard_auth.sessions WHERE expires_at < NOW();

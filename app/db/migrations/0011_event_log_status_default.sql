-- Ensure legacy event_log.status has a default to satisfy NOT NULL inserts

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'event_log'
          AND column_name = 'status'
    ) THEN
        BEGIN
            EXECUTE 'ALTER TABLE event_log ALTER COLUMN status SET DEFAULT ''error''';
        EXCEPTION WHEN others THEN
        END;
    END IF;
END $$;

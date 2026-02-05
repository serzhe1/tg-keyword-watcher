-- Relax unexpected NOT NULL constraints on event_log source fields (compat with current repo)

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'event_log'
          AND column_name = 'source_chat_id'
    ) THEN
        BEGIN
            EXECUTE 'ALTER TABLE event_log ALTER COLUMN source_chat_id DROP NOT NULL';
        EXCEPTION WHEN others THEN
        END;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'event_log'
          AND column_name = 'source_message_id'
    ) THEN
        BEGIN
            EXECUTE 'ALTER TABLE event_log ALTER COLUMN source_message_id DROP NOT NULL';
        EXCEPTION WHEN others THEN
        END;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'event_log'
          AND column_name = 'target_chat'
    ) THEN
        BEGIN
            EXECUTE 'ALTER TABLE event_log ALTER COLUMN target_chat DROP NOT NULL';
        EXCEPTION WHEN others THEN
        END;
    END IF;
END $$;

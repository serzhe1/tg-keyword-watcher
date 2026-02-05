-- Relax unexpected NOT NULL constraint on forwarded_messages.target_chat (compat with current repo)

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'forwarded_messages'
          AND column_name = 'target_chat'
    ) THEN
        BEGIN
            EXECUTE 'ALTER TABLE forwarded_messages ALTER COLUMN target_chat DROP NOT NULL';
        EXCEPTION WHEN others THEN
            -- ignore if already nullable or not supported
        END;
    END IF;
END $$;

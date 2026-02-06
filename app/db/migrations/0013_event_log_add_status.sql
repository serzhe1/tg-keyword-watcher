-- Add missing status column to event_log for backward compatibility

ALTER TABLE event_log
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'error';

UPDATE event_log
SET status = 'error'
WHERE status IS NULL;

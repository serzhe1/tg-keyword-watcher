-- Add missing level column to event_log for backward compatibility

ALTER TABLE event_log
    ADD COLUMN IF NOT EXISTS level text NOT NULL DEFAULT 'error';

UPDATE event_log
SET level = 'error'
WHERE level IS NULL;

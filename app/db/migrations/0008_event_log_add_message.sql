-- Add missing message column to event_log for backward compatibility

ALTER TABLE event_log
    ADD COLUMN IF NOT EXISTS message text NOT NULL DEFAULT '';

UPDATE event_log
SET message = ''
WHERE message IS NULL;

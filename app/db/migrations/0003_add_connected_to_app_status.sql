-- Add connected flag for dashboard and bot status.
-- Must be backward compatible with already created tables.

ALTER TABLE app_status
    ADD COLUMN IF NOT EXISTS connected boolean NOT NULL DEFAULT false;

-- Normalize existing rows (in case table already had data).
UPDATE app_status
SET connected = false
WHERE connected IS NULL;
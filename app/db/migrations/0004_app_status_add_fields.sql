-- Bring app_status schema in sync with Repo/app UI expectations.
-- Backward compatible: only adds columns if missing.

ALTER TABLE app_status
    ADD COLUMN IF NOT EXISTS connected boolean NOT NULL DEFAULT false;

ALTER TABLE app_status
    ADD COLUMN IF NOT EXISTS last_error text;

ALTER TABLE app_status
    ADD COLUMN IF NOT EXISTS last_event_time timestamptz;

ALTER TABLE app_status
    ADD COLUMN IF NOT EXISTS last_event_message text;

-- Ensure at least one row exists (singleton pattern).
INSERT INTO app_status (id)
VALUES (1)
    ON CONFLICT (id) DO NOTHING;
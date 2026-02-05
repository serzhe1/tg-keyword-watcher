-- Add missing timestamps to forwarded_messages for repo compatibility

ALTER TABLE forwarded_messages
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT NOW();

ALTER TABLE forwarded_messages
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT NOW();

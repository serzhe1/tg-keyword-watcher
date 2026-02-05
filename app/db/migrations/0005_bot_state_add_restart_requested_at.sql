ALTER TABLE bot_state
    ADD COLUMN IF NOT EXISTS restart_requested_at timestamptz;
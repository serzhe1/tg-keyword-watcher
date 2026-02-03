-- 002_auth_and_state.sql
CREATE TABLE IF NOT EXISTS app_status (
                                          id SMALLINT PRIMARY KEY DEFAULT 1,
                                          bot_connected BOOLEAN NOT NULL DEFAULT FALSE,
                                          last_event_at TIMESTAMPTZ NULL,
                                          last_error TEXT NULL,
                                          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

INSERT INTO app_status (id)
VALUES (1)
    ON CONFLICT (id) DO NOTHING;
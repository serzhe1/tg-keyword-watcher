-- 001_init.sql
CREATE TABLE IF NOT EXISTS keywords (
                                        id BIGSERIAL PRIMARY KEY,
                                        keyword TEXT NOT NULL UNIQUE,
                                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

CREATE TABLE IF NOT EXISTS bot_state (
                                         id SMALLINT PRIMARY KEY DEFAULT 1,
                                         enabled BOOLEAN NOT NULL DEFAULT TRUE,
                                         restart_requested BOOLEAN NOT NULL DEFAULT FALSE,
                                         updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

INSERT INTO bot_state (id)
VALUES (1)
    ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS channel_checkpoint (
                                                  channel_id BIGINT PRIMARY KEY,
                                                  last_message_id BIGINT NOT NULL,
                                                  last_message_date TIMESTAMPTZ NULL,
                                                  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

CREATE TABLE IF NOT EXISTS forwarded_messages (
                                                  id BIGSERIAL PRIMARY KEY,
                                                  source_chat_id BIGINT NOT NULL,
                                                  source_message_id BIGINT NOT NULL,
                                                  target_chat TEXT NOT NULL, -- ты выбрал @channelname
                                                  forwarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    matched_keywords TEXT NOT NULL DEFAULT '',
    UNIQUE (source_chat_id, source_message_id)
    );

CREATE TABLE IF NOT EXISTS event_log (
                                         id BIGSERIAL PRIMARY KEY,
                                         created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_chat_id BIGINT NOT NULL,
    source_message_id BIGINT NOT NULL,
    status TEXT NOT NULL, -- ok / fail
    matched_count INT NOT NULL DEFAULT 0,
    error_short TEXT NULL
    );

CREATE INDEX IF NOT EXISTS idx_event_log_created_at ON event_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_forwarded_messages_source ON forwarded_messages(source_chat_id, source_message_id);
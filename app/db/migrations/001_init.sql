-- 001_init.sql

-- keywords
CREATE TABLE IF NOT EXISTS keywords (
                                        id BIGSERIAL PRIMARY KEY,
                                        keyword TEXT NOT NULL UNIQUE,
                                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

-- forwarded_messages
CREATE TABLE IF NOT EXISTS forwarded_messages (
                                                  id BIGSERIAL PRIMARY KEY,
                                                  source_chat_id BIGINT NOT NULL,
                                                  source_message_id INTEGER NOT NULL,
                                                  status TEXT NOT NULL DEFAULT 'pending',
                                                  claimed_at TIMESTAMPTZ NULL,
                                                  sent_at TIMESTAMPTZ NULL,
                                                  fail_count INTEGER NOT NULL DEFAULT 0,
                                                  last_error TEXT NULL,
                                                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_chat_id, source_message_id)
    );

CREATE INDEX IF NOT EXISTS idx_forwarded_messages_status ON forwarded_messages(status);
CREATE INDEX IF NOT EXISTS idx_forwarded_messages_claimed_at ON forwarded_messages(claimed_at);

-- channel_checkpoint
CREATE TABLE IF NOT EXISTS channel_checkpoint (
                                                  chat_id BIGINT PRIMARY KEY,
                                                  last_message_id INTEGER NOT NULL,
                                                  last_message_date TIMESTAMPTZ NULL,
                                                  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

-- event_log
CREATE TABLE IF NOT EXISTS event_log (
                                         id BIGSERIAL PRIMARY KEY,
                                         level TEXT NOT NULL DEFAULT 'error',
                                         message TEXT NOT NULL,
                                         created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

CREATE INDEX IF NOT EXISTS idx_event_log_created_at ON event_log(created_at);

-- bot_state (1 строка)
CREATE TABLE IF NOT EXISTS bot_state (
                                         id SMALLINT PRIMARY KEY DEFAULT 1,
                                         enabled BOOLEAN NOT NULL DEFAULT FALSE,
                                         updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

INSERT INTO bot_state(id, enabled)
VALUES (1, FALSE)
    ON CONFLICT (id) DO NOTHING;

-- app_status (1 строка)
CREATE TABLE IF NOT EXISTS app_status (
                                          id SMALLINT PRIMARY KEY DEFAULT 1,
                                          connected BOOLEAN NOT NULL DEFAULT FALSE,
                                          last_error TEXT NULL,
                                          last_event_time TIMESTAMPTZ NULL,
                                          last_event_message TEXT NULL,
                                          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

INSERT INTO app_status(id, connected)
VALUES (1, FALSE)
    ON CONFLICT (id) DO NOTHING;
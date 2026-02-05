from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg


@dataclass(frozen=True)
class BotState:
    enabled: bool
    restart_requested_at: datetime | None


@dataclass(frozen=True)
class AppStatus:
    connected: bool
    last_error: str | None
    last_event_time: datetime | None
    last_event_message: str | None


class Repo:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ----------------------------
    # Keywords
    # ----------------------------
    async def keyword_create(self, word: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO keywords(keyword)
                VALUES ($1)
                    ON CONFLICT (keyword) DO NOTHING;
                """,
                word,
            )

    async def keyword_delete(self, word: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM keywords WHERE keyword = $1;", word)

    async def keyword_list(self, q: str | None, limit: int, offset: int) -> tuple[list[str], int]:
        q = (q or "").strip()
        async with self._pool.acquire() as conn:
            if q:
                rows = await conn.fetch(
                    """
                    SELECT keyword
                    FROM keywords
                    WHERE keyword ILIKE '%' || $1 || '%'
                    ORDER BY keyword ASC
                        LIMIT $2 OFFSET $3;
                    """,
                    q,
                    limit,
                    offset,
                )
                total = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM keywords
                    WHERE keyword ILIKE '%' || $1 || '%';
                    """,
                    q,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT keyword
                    FROM keywords
                    ORDER BY keyword ASC
                        LIMIT $1 OFFSET $2;
                    """,
                    limit,
                    offset,
                )
                total = await conn.fetchval("SELECT COUNT(*) FROM keywords;")

        return [r["keyword"] for r in rows], int(total)

    async def keyword_all(self) -> list[str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT keyword FROM keywords ORDER BY keyword ASC;")
            return [r["keyword"] for r in rows]

    # ----------------------------
    # Forwarded messages (idempotency skeleton; will be used later)
    # ----------------------------
    async def forwarded_claim(
            self,
            source_chat_id: int,
            source_message_id: int,
            pending_timeout_seconds: int,
    ) -> bool:
        """
        Idempotency claim:
        - Insert as pending if not exists.
        - If exists as sent -> cannot claim.
        - If exists as pending and not expired -> cannot claim.
        - If pending expired -> re-claim (update updated_at).
        """
        now = datetime.now(timezone.utc)
        timeout = now - timedelta(seconds=pending_timeout_seconds)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT status, updated_at
                    FROM forwarded_messages
                    WHERE source_chat_id = $1 AND source_message_id = $2
                        FOR UPDATE;
                    """,
                    source_chat_id,
                    source_message_id,
                )

                if row is None:
                    await conn.execute(
                        """
                        INSERT INTO forwarded_messages(source_chat_id, source_message_id, status, created_at, updated_at)
                        VALUES ($1, $2, 'pending', $3, $3);
                        """,
                        source_chat_id,
                        source_message_id,
                        now,
                    )
                    return True

                status = row["status"]
                updated_at = row["updated_at"]

                if status == "sent":
                    return False

                if status == "pending" and updated_at is not None and updated_at > timeout:
                    return False

                await conn.execute(
                    """
                    UPDATE forwarded_messages
                    SET status = 'pending', updated_at = $3
                    WHERE source_chat_id = $1 AND source_message_id = $2;
                    """,
                    source_chat_id,
                    source_message_id,
                    now,
                )
                return True

    async def forwarded_mark_sent(self, source_chat_id: int, source_message_id: int) -> None:
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE forwarded_messages
                SET status = 'sent', updated_at = $3
                WHERE source_chat_id = $1 AND source_message_id = $2;
                """,
                source_chat_id,
                source_message_id,
                now,
            )

    async def forwarded_mark_failed(self, source_chat_id: int, source_message_id: int, error: str) -> None:
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE forwarded_messages
                SET status = 'failed', last_error = $3, updated_at = $4
                WHERE source_chat_id = $1 AND source_message_id = $2;
                """,
                source_chat_id,
                source_message_id,
                error,
                now,
            )

    # ----------------------------
    # Channel checkpoint (skeleton; will be used later)
    # ----------------------------
    async def checkpoint_get(self, source_chat_id: int) -> tuple[int | None, datetime | None]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT last_message_id, last_message_date
                FROM channel_checkpoint
                WHERE channel_id = $1;
                """,
                source_chat_id,
            )
            if not row:
                return None, None
            return row["last_message_id"], row["last_message_date"]

    async def checkpoint_upsert(self, source_chat_id: int, last_message_id: int, last_message_date: datetime) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO channel_checkpoint(channel_id, last_message_id, last_message_date, updated_at)
                VALUES ($1, $2, $3, $4)
                    ON CONFLICT (channel_id)
                DO UPDATE SET
                    last_message_id = EXCLUDED.last_message_id,
                                           last_message_date = EXCLUDED.last_message_date,
                                           updated_at = EXCLUDED.updated_at;
                """,
                source_chat_id,
                last_message_id,
                last_message_date,
                datetime.now(timezone.utc),
            )

    # ----------------------------
    # Event log
    # ----------------------------
    async def event_error_add(self, message: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO event_log(status, level, message, created_at)
                VALUES ('error', 'error', $1, $2);
                """,
                message,
                datetime.now(timezone.utc),
            )

    async def event_error_latest(self, limit: int = 100) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, message, created_at
                FROM event_log
                WHERE level = 'error'
                ORDER BY created_at DESC
                    LIMIT $1;
                """,
                limit,
            )
            return [dict(r) for r in rows]

    # ----------------------------
    # Singleton tables: bot_state / app_status
    # ----------------------------
    async def bot_state_get(self) -> BotState:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT enabled, restart_requested_at
                FROM bot_state
                WHERE id = 1;
                """
            )
            if row is None:
                await conn.execute(
                    "INSERT INTO bot_state(id, enabled, restart_requested_at) VALUES (1, false, NULL) ON CONFLICT (id) DO NOTHING;"
                )
                return BotState(enabled=False, restart_requested_at=None)

            return BotState(enabled=bool(row["enabled"]), restart_requested_at=row["restart_requested_at"])

    async def bot_state_set_enabled(self, enabled: bool) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bot_state(id, enabled, restart_requested_at)
                VALUES (1, $1, NULL)
                    ON CONFLICT (id)
                DO UPDATE SET enabled = EXCLUDED.enabled;
                """,
                enabled,
            )

    async def bot_state_request_restart(self) -> None:
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bot_state(id, enabled, restart_requested_at)
                VALUES (1, true, $1)
                    ON CONFLICT (id)
                DO UPDATE SET restart_requested_at = EXCLUDED.restart_requested_at;
                """,
                now,
            )

    async def app_status_get(self) -> AppStatus:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT connected, last_error, last_event_time, last_event_message
                FROM app_status
                WHERE id = 1;
                """
            )
            if row is None:
                await conn.execute(
                    """
                    INSERT INTO app_status(id, connected, last_error, last_event_time, last_event_message)
                    VALUES (1, false, NULL, NULL, NULL)
                        ON CONFLICT (id) DO NOTHING;
                    """
                )
                return AppStatus(
                    connected=False,
                    last_error=None,
                    last_event_time=None,
                    last_event_message=None,
                )

            return AppStatus(
                connected=bool(row["connected"]),
                last_error=row["last_error"],
                last_event_time=row["last_event_time"],
                last_event_message=row["last_event_message"],
            )

    async def app_status_set_connected(self, connected: bool) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO app_status(id, connected, last_error, last_event_time, last_event_message)
                VALUES (1, $1, NULL, NULL, NULL)
                    ON CONFLICT (id)
                DO UPDATE SET connected = EXCLUDED.connected, 
                                           last_error = NULL;
                """,
                connected,
            )

    async def app_status_set_error(self, error: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO app_status(id, connected, last_error, last_event_time, last_event_message)
                VALUES (1, false, $1, NULL, NULL)
                    ON CONFLICT (id)
                DO UPDATE SET last_error = EXCLUDED.last_error;
                """,
                error,
            )

    async def app_status_set_event(self, message: str) -> None:
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO app_status(id, connected, last_error, last_event_time, last_event_message)
                VALUES (1, false, NULL, $1, $2)
                    ON CONFLICT (id)
                DO UPDATE SET last_event_time = EXCLUDED.last_event_time,
                                           last_event_message = EXCLUDED.last_event_message;
                """,
                now,
                message,
            )

    # ----------------------------
    # Cleanup
    # ----------------------------
    async def cleanup(self) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        log_cutoff = now - timedelta(days=7)
        forwards_cutoff = now - timedelta(days=30)

        async with self._pool.acquire() as conn:
            deleted_logs = await conn.execute(
                "DELETE FROM event_log WHERE created_at < $1;",
                log_cutoff,
            )
            deleted_forwards = await conn.execute(
                "DELETE FROM forwarded_messages WHERE created_at < $1;",
                forwards_cutoff,
            )

        # asyncpg returns "DELETE <n>"
        def _count(cmd: str) -> int:
            try:
                return int(cmd.split()[-1])
            except Exception:
                return 0

        return {"event_log": _count(deleted_logs), "forwarded_messages": _count(deleted_forwards)}

    # ----------------------------
    # Settings
    # ----------------------------
    async def app_setting_get(self, key: str, default: str | None = None) -> str | None:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval(
                "SELECT value FROM app_settings WHERE key = $1;",
                key,
            )
            if value is None:
                return default
            return str(value)

    async def app_setting_set(self, key: str, value: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO app_settings(key, value, updated_at)
                VALUES ($1, $2, $3)
                    ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value,
                              updated_at = EXCLUDED.updated_at;
                """,
                key,
                value,
                datetime.now(timezone.utc),
            )

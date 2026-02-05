from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import asyncpg


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_keyword(s: str) -> str:
    # Normalize for case-insensitive matching and treat "ё" == "е"
    s = s.strip()
    s = s.replace("Ё", "Е").replace("ё", "е")
    return s.lower()


@dataclass(frozen=True)
class KeywordRow:
    id: int
    keyword: str
    created_at: datetime


@dataclass(frozen=True)
class EventLogRow:
    id: int
    level: str
    message: str
    created_at: datetime


@dataclass(frozen=True)
class AppStatus:
    connected: bool
    last_error: str | None
    last_event_time: datetime | None
    last_event_message: str | None


@dataclass(frozen=True)
class BotState:
    enabled: bool


class Repo:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ---------- keywords ----------

    async def keywords_list(
            self,
            q: str | None,
            limit: int,
            offset: int,
    ) -> tuple[list[KeywordRow], int]:
        """
        Returns (items, total).
        Search is substring-based, case-insensitive, and treats "ё" == "е".
        """
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        qn = normalize_keyword(q) if q else None

        async with self._pool.acquire() as conn:
            if qn:
                total = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM keywords
                    WHERE replace(lower(keyword), 'ё', 'е') LIKE '%' || $1 || '%'
                    """,
                    qn,
                )
                rows = await conn.fetch(
                    """
                    SELECT id, keyword, created_at
                    FROM keywords
                    WHERE replace(lower(keyword), 'ё', 'е') LIKE '%' || $1 || '%'
                    ORDER BY created_at DESC, id DESC
                        LIMIT $2 OFFSET $3
                    """,
                    qn,
                    limit,
                    offset,
                )
            else:
                total = await conn.fetchval("SELECT COUNT(*) FROM keywords;")
                rows = await conn.fetch(
                    """
                    SELECT id, keyword, created_at
                    FROM keywords
                    ORDER BY created_at DESC, id DESC
                        LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset,
                )

        items = [KeywordRow(id=r["id"], keyword=r["keyword"], created_at=r["created_at"]) for r in rows]
        return items, int(total)

    async def keywords_add(self, keyword: str) -> bool:
        """
        Returns True if inserted, False if already exists (idempotent add).
        Duplicate check is done in normalized form so "еж" and "ёж" are treated as the same.
        """
        kw = keyword.strip()
        if not kw:
            raise ValueError("keyword is empty")

        async with self._pool.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT 1
                FROM keywords
                WHERE replace(lower(keyword), 'ё', 'е') = $1
                    LIMIT 1
                """,
                normalize_keyword(kw),
            )
            if exists:
                return False

            await conn.execute("INSERT INTO keywords(keyword) VALUES($1);", kw)
            return True

    async def keywords_delete(self, keyword_id: int) -> bool:
        async with self._pool.acquire() as conn:
            res = await conn.execute("DELETE FROM keywords WHERE id=$1;", int(keyword_id))
        # asyncpg returns "DELETE <n>"
        return res.endswith("1")

    async def keywords_all_normalized(self) -> list[str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT keyword FROM keywords ORDER BY id ASC;")
        return [normalize_keyword(r["keyword"]) for r in rows]

    # ---------- forwarded_messages: idempotency / pending-retry ----------

    async def forwarded_claim(
            self,
            source_chat_id: int,
            source_message_id: int,
            retry_after_seconds: int,
    ) -> bool:
        """
        Atomic claim for processing:
        - inserts a pending row if it doesn't exist
        - re-claims pending/failed if claim is older than retry_after_seconds
        - never allows re-processing if status == sent
        Returns True if the caller should process now, otherwise False.
        """
        retry_after_seconds = max(1, retry_after_seconds)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT status, claimed_at
                    FROM forwarded_messages
                    WHERE source_chat_id=$1 AND source_message_id=$2
                    """,
                    int(source_chat_id),
                    int(source_message_id),
                )

                now = utc_now()

                if row is None:
                    await conn.execute(
                        """
                        INSERT INTO forwarded_messages(source_chat_id, source_message_id, status, claimed_at)
                        VALUES ($1, $2, 'pending', $3)
                        """,
                        int(source_chat_id),
                        int(source_message_id),
                        now,
                    )
                    return True

                status = row["status"]
                claimed_at = row["claimed_at"]

                if status == "sent":
                    return False

                # Allow retry if claim is missing or expired
                if claimed_at is None or (now - claimed_at) >= timedelta(seconds=retry_after_seconds):
                    await conn.execute(
                        """
                        UPDATE forwarded_messages
                        SET status='pending', claimed_at=$3, updated_at=NOW()
                        WHERE source_chat_id=$1 AND source_message_id=$2
                        """,
                        int(source_chat_id),
                        int(source_message_id),
                        now,
                    )
                    return True

                return False

    async def forwarded_mark_sent(self, source_chat_id: int, source_message_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE forwarded_messages
                SET status='sent', sent_at=NOW(), updated_at=NOW()
                WHERE source_chat_id=$1 AND source_message_id=$2
                """,
                int(source_chat_id),
                int(source_message_id),
            )

    async def forwarded_mark_failed(self, source_chat_id: int, source_message_id: int, error: str) -> None:
        err = (error or "").strip()
        if len(err) > 4000:
            err = err[:4000]

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE forwarded_messages
                SET status='failed',
                    fail_count = fail_count + 1,
                    last_error=$3,
                    updated_at=NOW()
                WHERE source_chat_id=$1 AND source_message_id=$2
                """,
                int(source_chat_id),
                int(source_message_id),
                err,
            )

    # ---------- channel_checkpoint ----------

    async def checkpoint_get(self, chat_id: int) -> tuple[int, datetime | None] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT last_message_id, last_message_date
                FROM channel_checkpoint
                WHERE chat_id=$1
                """,
                int(chat_id),
            )
        if row is None:
            return None
        return int(row["last_message_id"]), row["last_message_date"]

    async def checkpoint_upsert(self, chat_id: int, last_message_id: int, last_message_date: datetime | None) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO channel_checkpoint(chat_id, last_message_id, last_message_date, updated_at)
                VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (chat_id) DO UPDATE
                                                 SET last_message_id=EXCLUDED.last_message_id,
                                                 last_message_date=EXCLUDED.last_message_date,
                                                 updated_at=NOW()
                """,
                int(chat_id),
                int(last_message_id),
                last_message_date,
            )

    # ---------- event_log (errors only) ----------

    async def log_error(self, message: str) -> None:
        msg = (message or "").strip()
        if not msg:
            msg = "unknown error"
        if len(msg) > 4000:
            msg = msg[:4000]

        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO event_log(level, message) VALUES('error', $1);",
                msg,
            )

    async def event_log_list(self, limit: int = 100) -> list[EventLogRow]:
        limit = max(1, min(limit, 200))
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, level, message, created_at
                FROM event_log
                ORDER BY id DESC
                    LIMIT $1
                """,
                limit,
            )
        return [EventLogRow(id=r["id"], level=r["level"], message=r["message"], created_at=r["created_at"]) for r in rows]

    # ---------- bot_state / app_status ----------

    async def bot_state_get(self) -> BotState:
        async with self._pool.acquire() as conn:
            enabled = await conn.fetchval("SELECT enabled FROM bot_state WHERE id=1;")
        return BotState(enabled=bool(enabled))

    async def bot_state_set(self, enabled: bool) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE bot_state
                SET enabled=$1, updated_at=NOW()
                WHERE id=1
                """,
                bool(enabled),
            )

    async def app_status_get(self) -> AppStatus:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT connected, last_error, last_event_time, last_event_message
                FROM app_status
                WHERE id=1
                """
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
                UPDATE app_status
                SET connected=$1, updated_at=NOW()
                WHERE id=1
                """,
                bool(connected),
            )

    async def app_status_set_error(self, error: str | None) -> None:
        err = (error or "").strip() if error else None
        if err and len(err) > 4000:
            err = err[:4000]

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE app_status
                SET last_error=$1, updated_at=NOW()
                WHERE id=1
                """,
                err,
            )

    async def app_status_set_last_event(self, when: datetime, message: str) -> None:
        msg = (message or "").strip()
        if len(msg) > 4000:
            msg = msg[:4000]

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE app_status
                SET last_event_time=$1,
                    last_event_message=$2,
                    updated_at=NOW()
                WHERE id=1
                """,
                when,
                msg,
            )

    # ---------- cleanup ----------

    async def cleanup(self, event_log_days: int = 7, forwarded_days: int = 30) -> dict[str, int]:
        event_log_days = max(1, event_log_days)
        forwarded_days = max(1, forwarded_days)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                res1 = await conn.execute(
                    "DELETE FROM event_log WHERE created_at < NOW() - ($1::text || ' days')::interval;",
                    str(event_log_days),
                )
                res2 = await conn.execute(
                    "DELETE FROM forwarded_messages WHERE created_at < NOW() - ($1::text || ' days')::interval;",
                    str(forwarded_days),
                )

        def parse_count(res: str) -> int:
            # asyncpg returns "DELETE <n>"
            try:
                return int(res.split()[-1])
            except Exception:
                return 0

        return {"event_log": parse_count(res1), "forwarded_messages": parse_count(res2)}
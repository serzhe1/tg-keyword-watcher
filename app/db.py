from dataclasses import dataclass
from typing import Optional
from psycopg_pool import ConnectionPool
from typing import List, Tuple

from app.config import DATABASE_URL

pool: ConnectionPool | None = None


@dataclass
class BotState:
    enabled: bool
    restart_requested: bool


@dataclass
class AppStatus:
    bot_connected: bool
    last_event_at: Optional[str]
    last_error: Optional[str]



def init_pool() -> None:
    global pool
    if pool is None:
        pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=5, open=True)


def close_pool() -> None:
    global pool
    if pool is not None:
        pool.close()
        pool = None


def get_bot_state() -> BotState:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT enabled, restart_requested FROM bot_state WHERE id=1;")
            row = cur.fetchone()
            # на случай если таблица пуста (не должна быть при миграциях)
            if not row:
                cur.execute("INSERT INTO bot_state(id) VALUES (1) ON CONFLICT DO NOTHING;")
                conn.commit()
                return BotState(enabled=True, restart_requested=False)
            return BotState(enabled=bool(row[0]), restart_requested=bool(row[1]))


def set_enabled(enabled: bool) -> None:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bot_state SET enabled=%s, updated_at=now() WHERE id=1;",
                (enabled,),
            )
        conn.commit()


def request_restart() -> None:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bot_state SET restart_requested=TRUE, updated_at=now() WHERE id=1;"
            )
        conn.commit()


def clear_restart_request() -> None:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bot_state SET restart_requested=FALSE, updated_at=now() WHERE id=1;"
            )
        conn.commit()


def get_app_status() -> AppStatus:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bot_connected, last_event_at, last_error FROM app_status WHERE id=1;"
            )
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO app_status(id) VALUES (1) ON CONFLICT DO NOTHING;")
                conn.commit()
                return AppStatus(bot_connected=False, last_event_at=None, last_error=None)

            return AppStatus(
                bot_connected=bool(row[0]),
                last_event_at=row[1].isoformat() if row[1] else None,
                last_error=row[2],
            )


def set_app_status(bot_connected: bool, last_event_at=None, last_error=None) -> None:
    """
    later: бот будет обновлять это.
    сейчас оставляем утилиту.
    """
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE app_status
                SET bot_connected=%s,
                    last_event_at=COALESCE(%s, last_event_at),
                    last_error=COALESCE(%s, last_error),
                    updated_at=now()
                WHERE id=1;
                """,
                (bot_connected, last_event_at, last_error),
            )
        conn.commit()


def list_keywords() -> List[Tuple[int, str, str]]:
    """
    Returns: [(id, keyword, created_at_iso), ...]
    """
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, keyword, created_at FROM keywords ORDER BY keyword ASC;"
            )
            rows = cur.fetchall()
            return [
                (int(r[0]), str(r[1]), r[2].isoformat() if r[2] else "")
                for r in rows
            ]


def add_keyword(keyword: str) -> None:
    assert pool is not None
    kw = keyword.strip()
    if not kw:
        raise ValueError("EMPTY")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO keywords(keyword) VALUES (%s);",
                    (kw,),
                )
            except Exception as e:
                # psycopg будет кидать исключение на unique violation
                # мы не будем тащить специфичные типы ошибок — обработаем на уровне роутов
                raise
        conn.commit()


def delete_keyword(keyword_id: int) -> None:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM keywords WHERE id=%s;", (keyword_id,))
        conn.commit()
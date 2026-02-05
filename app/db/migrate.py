import os
from dataclasses import dataclass
from pathlib import Path

import asyncpg


@dataclass(frozen=True)
class Migration:
    filename: str
    sql: str


MIGRATIONS_DIR = Path("/app/app/db/migrations")


async def load_migrations() -> list[Migration]:
    if not MIGRATIONS_DIR.is_dir():
        raise RuntimeError(f"Migrations dir not found: {MIGRATIONS_DIR}")

    files = sorted([p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file()])
    return [Migration(filename=p.name, sql=p.read_text(encoding="utf-8")) for p in files]


async def table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema='public' AND table_name=$1
            """,
            table_name,
        )
    )


async def column_exists(conn: asyncpg.Connection, table_name: str, column_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=$1 AND column_name=$2
            """,
            table_name,
            column_name,
        )
    )


async def ensure_schema_migrations(conn: asyncpg.Connection) -> None:
    """
    Ensures schema_migrations exists and has a 'filename' column.
    If schema_migrations exists in an unexpected format, it is recreated.
    If 'keywords' table already exists, we assume 001_init.sql was effectively applied
    and mark it as applied to avoid re-running it.
    """
    exists = await table_exists(conn, "schema_migrations")

    if not exists:
        await conn.execute(
            """
            CREATE TABLE schema_migrations (
                                               filename TEXT PRIMARY KEY,
                                               applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        return

    has_filename = await column_exists(conn, "schema_migrations", "filename")
    if has_filename:
        return

    init_applied = await table_exists(conn, "keywords")

    async with conn.transaction():
        await conn.execute("DROP TABLE schema_migrations;")
        await conn.execute(
            """
            CREATE TABLE schema_migrations (
                                               filename TEXT PRIMARY KEY,
                                               applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        if init_applied:
            await conn.execute(
                "INSERT INTO schema_migrations(filename) VALUES($1) ON CONFLICT DO NOTHING;",
                "001_init.sql",
            )


async def apply_migrations(database_url: str) -> None:
    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(database_url)

        await ensure_schema_migrations(conn)

        applied_rows = await conn.fetch("SELECT filename FROM schema_migrations;")
        applied = {r["filename"] for r in applied_rows}

        migrations = await load_migrations()
        for m in migrations:
            if m.filename in applied:
                continue

            async with conn.transaction():
                await conn.execute(m.sql)
                await conn.execute(
                    "INSERT INTO schema_migrations(filename) VALUES($1);",
                    m.filename,
                )
    finally:
        if conn is not None:
            await conn.close()


def get_database_url_from_env() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL env is required for migrations")
    return url
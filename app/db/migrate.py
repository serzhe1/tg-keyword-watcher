import os
from dataclasses import dataclass
from pathlib import Path

import asyncpg


@dataclass(frozen=True)
class Migration:
    filename: str
    sql: str


MIGRATIONS_DIR = Path("/app/app/db/migrations")


async def ensure_migrations_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
                                                         filename TEXT PRIMARY KEY,
                                                         applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """
    )


async def load_migrations() -> list[Migration]:
    if not MIGRATIONS_DIR.is_dir():
        raise RuntimeError(f"Migrations dir not found: {MIGRATIONS_DIR}")

    files = sorted([p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file()])
    migrations: list[Migration] = []
    for p in files:
        migrations.append(Migration(filename=p.name, sql=p.read_text(encoding="utf-8")))
    return migrations


async def apply_migrations(database_url: str) -> None:
    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(database_url)
        await ensure_migrations_table(conn)

        applied_rows = await conn.fetch("SELECT filename FROM schema_migrations;")
        applied = {r["filename"] for r in applied_rows}

        migrations = await load_migrations()
        for m in migrations:
            if m.filename in applied:
                continue

            # Одна миграция = одна транзакция (явно и предсказуемо)
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
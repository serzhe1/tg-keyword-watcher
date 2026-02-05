import asyncio
import os
from datetime import datetime, timezone
from app.bot.runtime import BotRuntime

import asyncpg
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.migrate import apply_migrations, get_database_url_from_env
from app.db.repo import Repo
from app.web.routes_auth import router as auth_router
from app.web.routes_controls import router as controls_router
from app.web.routes_dashboard import router as dashboard_router
from app.web.routes_keywords import router as keywords_router
from app.web.routes_logs import router as logs_router


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_dir(path: str) -> None:
    if not os.path.isdir(path):
        raise RuntimeError(f"Required directory not found: {path}")


app = FastAPI(title="tg-keyword-watcher")

PROJECT_ROOT = "/app"
APP_DIR = os.path.join(PROJECT_ROOT, "app")

TEMPLATES_DIR = os.path.join(APP_DIR, "web", "templates")
STATIC_DIR = os.path.join(APP_DIR, "web", "static")

require_dir(TEMPLATES_DIR)
require_dir(STATIC_DIR)

templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routes
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(controls_router)
app.include_router(keywords_router)
app.include_router(logs_router)


@app.on_event("startup")
async def on_startup() -> None:
    db_url = get_database_url_from_env()

    # Apply SQL migrations on startup (explicit, no Alembic).
    await apply_migrations(db_url)

    # Create DB pool and repository.
    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=10)
    app.state.db_pool = pool
    app.state.repo = Repo(pool)
    app.state.bot_runtime = BotRuntime(app.state.repo)
    await app.state.bot_runtime.start()
    app.state.cleanup_task = asyncio.create_task(_cleanup_loop(app.state.repo))


@app.on_event("shutdown")
async def on_shutdown() -> None:
    pool = getattr(app.state, "db_pool", None)
    if pool is not None:
        await pool.close()
    runtime = getattr(app.state, "bot_runtime", None)
    if runtime is not None:
        await runtime.stop()
    cleanup_task = getattr(app.state, "cleanup_task", None)
    if cleanup_task is not None:
        cleanup_task.cancel()


async def _cleanup_loop(repo: Repo) -> None:
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run.replace(day=next_run.day + 1)
        sleep_seconds = max(1, int((next_run - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)

        result = await repo.cleanup()
        await repo.app_status_set_event(
            f"Cleanup done: event_log={result.get('event_log', 0)}, "
            f"forwarded_messages={result.get('forwarded_messages', 0)}"
        )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "time_utc": utc_now_iso()}

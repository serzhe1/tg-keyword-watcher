import os
from datetime import datetime, timezone

import asyncpg
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.migrate import apply_migrations, get_database_url_from_env
from app.db.repo import Repo
from app.web.routes_auth import router as auth_router
from app.web.routes_dashboard import router as dashboard_router


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


@app.on_event("startup")
async def on_startup() -> None:
    db_url = get_database_url_from_env()

    # Apply SQL migrations on startup (explicit, no Alembic).
    await apply_migrations(db_url)

    # Create DB pool and repository.
    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=10)
    app.state.db_pool = pool
    app.state.repo = Repo(pool)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    pool = getattr(app.state, "db_pool", None)
    if pool is not None:
        await pool.close()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "time_utc": utc_now_iso()}
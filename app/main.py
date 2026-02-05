import os
from datetime import datetime, timezone

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.migrate import apply_migrations, get_database_url_from_env
from app.db.repo import Repo


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


@app.on_event("startup")
async def on_startup() -> None:
    db_url = get_database_url_from_env()

    await apply_migrations(db_url)

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
    # health без реального ping БД (простота). Потом добавим /health/db если надо.
    return {"status": "ok", "time_utc": utc_now_iso()}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    ctx = {
        "request": request,
        "target_channel": os.getenv("TARGET_CHANNEL", ""),
        "session_name": os.getenv("SESSION_NAME", ""),
        "database_url": os.getenv("DATABASE_URL", ""),
    }
    return templates.TemplateResponse("index.html", ctx)
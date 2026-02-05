import os
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


app = FastAPI(title="tg-keyword-watcher")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "web", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "web", "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "time_utc": utc_now_iso()}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    # Пустой UI-заглушка (в T2 будет нормальная админка)
    ctx = {
        "request": request,
        "target_channel": os.getenv("TARGET_CHANNEL", ""),
        "session_name": os.getenv("SESSION_NAME", ""),
        "database_url": os.getenv("DATABASE_URL", ""),
    }
    return templates.TemplateResponse("index.html", ctx)
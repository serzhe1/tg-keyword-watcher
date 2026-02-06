from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.web.deps import RedirectToLogin, require_auth
from app.web.i18n import apply_lang_cookie, build_lang_urls, resolve_lang, t


router = APIRouter()


def _templates() -> Jinja2Templates:
    from app.main import templates  # noqa: WPS433

    return templates


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        from app.web.deps import login_redirect

        return login_redirect(next_path="/")

    lang, set_cookie = resolve_lang(request)
    repo = request.app.state.repo
    env_target = os.getenv("TARGET_CHANNEL", "")
    target_channel = (await repo.app_setting_get("target_channel", env_target) or "").strip()
    error = (request.query_params.get("error") or "").strip()
    bot_state = await repo.bot_state_get()
    app_status = await repo.app_status_get()

    tpl = _templates()
    resp = tpl.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "nav_active": "dashboard",
            "lang": lang,
            "lang_urls": build_lang_urls(request),
            "t": t,
            "target_channel": target_channel,
            "session_name": os.getenv("SESSION_NAME", ""),
            "error": error,
            "connected": bool(app_status.connected),
            "bot_enabled": bool(bot_state.enabled),
            "last_error": app_status.last_error or "",
            "last_event_time": app_status.last_event_time.isoformat() if app_status.last_event_time else "",
            "last_event_message": app_status.last_event_message or "",
            "server_time_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    apply_lang_cookie(resp, lang, set_cookie)
    return resp


@router.get("/api/status", response_class=JSONResponse)
async def dashboard_status(request: Request) -> JSONResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    repo = request.app.state.repo
    bot_state = await repo.bot_state_get()
    app_status = await repo.app_status_get()
    return JSONResponse(
        {
            "connected": bool(app_status.connected),
            "bot_enabled": bool(bot_state.enabled),
            "last_error": app_status.last_error or "",
            "last_event_time": app_status.last_event_time.isoformat() if app_status.last_event_time else "",
            "last_event_message": app_status.last_event_message or "",
        }
    )

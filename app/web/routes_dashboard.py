from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
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
            "target_channel": os.getenv("TARGET_CHANNEL", ""),
            "session_name": os.getenv("SESSION_NAME", ""),
            "connected": "YES" if app_status.connected else "NO",
            "bot_enabled": "YES" if bot_state.enabled else "NO",
            "last_error": app_status.last_error or "",
            "last_event_time": app_status.last_event_time.isoformat() if app_status.last_event_time else "",
            "last_event_message": app_status.last_event_message or "",
            "server_time_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    apply_lang_cookie(resp, lang, set_cookie)
    return resp

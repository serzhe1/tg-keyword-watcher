from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.deps import RedirectToLogin, require_auth
from app.web.i18n import apply_lang_cookie, build_lang_urls, resolve_lang, t


router = APIRouter()


def _short_message(value: str, limit: int = 220) -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request) -> HTMLResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        from app.web.deps import login_redirect

        return login_redirect(next_path="/logs")

    lang, set_cookie = resolve_lang(request)
    repo = request.app.state.repo
    rows = await repo.event_error_latest(limit=100)
    logs = [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "message": _short_message(r["message"] or ""),
        }
        for r in rows
    ]

    from app.main import templates  # noqa: WPS433

    resp = templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "nav_active": "logs",
            "lang": lang,
            "lang_urls": build_lang_urls(request),
            "t": t,
            "logs": logs,
        },
    )
    apply_lang_cookie(resp, lang, set_cookie)
    return resp

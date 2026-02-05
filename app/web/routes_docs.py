from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.deps import RedirectToLogin, require_auth
from app.web.i18n import apply_lang_cookie, build_lang_urls, resolve_lang, t


router = APIRouter()


@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request) -> HTMLResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        from app.web.deps import login_redirect

        return login_redirect(next_path="/docs")

    lang, set_cookie = resolve_lang(request)
    from app.main import templates  # noqa: WPS433

    resp = templates.TemplateResponse(
        "docs.html",
        {
            "request": request,
            "nav_active": "docs",
            "lang": lang,
            "lang_urls": build_lang_urls(request),
            "t": t,
        },
    )
    apply_lang_cookie(resp, lang, set_cookie)
    return resp

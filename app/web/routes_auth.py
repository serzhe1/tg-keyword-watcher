from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.web.auth import login_expiry_utc, set_logged_in, verify_credentials, clear_login
from app.web.i18n import apply_lang_cookie, build_lang_urls, resolve_lang, t


router = APIRouter()


def _templates() -> Jinja2Templates:
    # Import templates lazily to avoid circular imports.
    from app.main import templates  # noqa: WPS433

    return templates


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/") -> HTMLResponse:
    tpl = _templates()
    lang, set_cookie = resolve_lang(request)
    resp = tpl.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next": next,
            "error": None,
            "lang": lang,
            "lang_urls": build_lang_urls(request),
            "t": t,
        },
    )
    apply_lang_cookie(resp, lang, set_cookie)
    return resp


@router.post("/login")
async def login_action(
        request: Request,
        login: str = Form(...),
        password: str = Form(...),
        next: str = Form("/"),
) -> Response:
    tpl = _templates()

    lang, set_cookie = resolve_lang(request)

    if not verify_credentials(login, password):
        resp = tpl.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next": next,
                "error": t("login.error", lang),
                "lang": lang,
                "lang_urls": build_lang_urls(request),
                "t": t,
            },
            status_code=401,
        )
        apply_lang_cookie(resp, lang, set_cookie)
        return resp

    resp = RedirectResponse(url=next or "/", status_code=303)
    set_logged_in(resp)
    apply_lang_cookie(resp, lang, set_cookie)
    return resp


@router.post("/logout")
async def logout_action(next: str = "/login") -> RedirectResponse:
    resp = RedirectResponse(url=next, status_code=303)
    clear_login(resp)
    return resp


@router.get("/auth/debug")
async def auth_debug() -> dict:
    # Debug-only endpoint. We keep it for now; can be removed later.
    return {"cookie_expires_utc": login_expiry_utc()}

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.web.auth import login_expiry_utc, set_logged_in, verify_credentials, clear_login


router = APIRouter()


def _templates() -> Jinja2Templates:
    # Import templates lazily to avoid circular imports.
    from app.main import templates  # noqa: WPS433

    return templates


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/") -> HTMLResponse:
    tpl = _templates()
    return tpl.TemplateResponse(
        "login.html",
        {"request": request, "next": next, "error": None},
    )


@router.post("/login")
async def login_action(
        request: Request,
        login: str = Form(...),
        password: str = Form(...),
        next: str = Form("/"),
) -> Response:
    tpl = _templates()

    if not verify_credentials(login, password):
        return tpl.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next": next,
                "error": "Invalid login or password",
            },
            status_code=401,
        )

    resp = RedirectResponse(url=next or "/", status_code=303)
    set_logged_in(resp)
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
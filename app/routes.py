from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import HTTPException

from app import db
from app.auth import is_logged_in, verify_credentials, set_login_cookie, clear_login_cookie

templates = Jinja2Templates(directory="templates")
router = APIRouter()


def require_auth(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    return None


@router.get("/health")
def health():
    # простая проверка БД
    _ = db.get_bot_state()
    return {"ok": True}


@router.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_post(
        request: Request,
        login: str = Form(...),
        password: str = Form(...),
):
    if not verify_credentials(login, password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль"},
            status_code=401,
        )

    resp = RedirectResponse(url="/dashboard", status_code=302)
    set_login_cookie(resp)
    return resp


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    clear_login_cookie(resp)
    return resp


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    redir = require_auth(request)
    if redir:
        return redir

    bot_state = db.get_bot_state()
    app_status = db.get_app_status()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "bot": bot_state, "status": app_status},
    )


@router.post("/bot/enable")
def bot_enable(request: Request):
    redir = require_auth(request)
    if redir:
        return redir
    db.set_enabled(True)
    return RedirectResponse(url="/dashboard", status_code=302)


@router.post("/bot/disable")
def bot_disable(request: Request):
    redir = require_auth(request)
    if redir:
        return redir
    db.set_enabled(False)
    return RedirectResponse(url="/dashboard", status_code=302)


@router.post("/bot/restart")
def bot_restart(request: Request):
    redir = require_auth(request)
    if redir:
        return redir
    db.request_restart()
    return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/keywords", response_class=HTMLResponse)
def keywords_page(request: Request):
    redir = require_auth(request)
    if redir:
        return redir

    items = db.list_keywords()
    return templates.TemplateResponse(
        "keywords.html",
        {
            "request": request,
            "items": items,
            "error": None,
        },
    )


@router.post("/keywords/add")
def keywords_add(
        request: Request,
        keyword: str = Form(...),
):
    redir = require_auth(request)
    if redir:
        return redir

    kw = keyword.strip()
    if not kw:
        items = db.list_keywords()
        return templates.TemplateResponse(
            "keywords.html",
            {"request": request, "items": items, "error": "Ключевое слово не может быть пустым"},
            status_code=400,
        )

    try:
        db.add_keyword(kw)
    except Exception:
        # чаще всего это duplicate из-за UNIQUE(keyword)
        items = db.list_keywords()
        return templates.TemplateResponse(
            "keywords.html",
            {"request": request, "items": items, "error": "Такое ключевое слово уже существует"},
            status_code=409,
        )

    return RedirectResponse(url="/keywords", status_code=302)


@router.post("/keywords/delete")
def keywords_delete(
        request: Request,
        keyword_id: int = Form(...),
):
    redir = require_auth(request)
    if redir:
        return redir

    db.delete_keyword(keyword_id)
    return RedirectResponse(url="/keywords", status_code=302)
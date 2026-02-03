from fastapi import Request
from itsdangerous import URLSafeSerializer, BadSignature

from app.config import ADMIN_LOGIN, ADMIN_PASSWORD, COOKIE_SECRET

_cookie_name = "tgmon_session"
_ser = URLSafeSerializer(COOKIE_SECRET, salt="tgmon")


def verify_credentials(login: str, password: str) -> bool:
    return login == ADMIN_LOGIN and password == ADMIN_PASSWORD


def set_login_cookie(response) -> None:
    token = _ser.dumps({"ok": True})
    response.set_cookie(
        _cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=False,  # на VPS за реверс-прокси/https можно поставить True
        max_age=60 * 60 * 24 * 30,
    )


def clear_login_cookie(response) -> None:
    response.delete_cookie(_cookie_name)


def is_logged_in(request: Request) -> bool:
    token = request.cookies.get(_cookie_name)
    if not token:
        return False
    try:
        data = _ser.loads(token)
        return bool(data.get("ok"))
    except BadSignature:
        return False
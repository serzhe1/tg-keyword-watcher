from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer


def _get_secret() -> str:
    # Must be set via env (.env), never committed.
    secret = os.getenv("APP_SECRET_KEY", "").strip()
    if not secret:
        raise RuntimeError("APP_SECRET_KEY env is required (used to sign session cookies)")
    return secret


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_get_secret(), salt="tgmon-auth-v1")


COOKIE_NAME = "tgmon_session"
COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _admin_creds() -> tuple[str, str]:
    login = os.getenv("ADMIN_LOGIN", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not login or not password:
        raise RuntimeError("ADMIN_LOGIN and ADMIN_PASSWORD env are required")
    return login, password


def verify_credentials(login: str, password: str) -> bool:
    expected_login, expected_password = _admin_creds()
    return login == expected_login and password == expected_password


def set_logged_in(response: Response) -> None:
    s = _serializer()
    token = s.dumps({"v": 1, "logged_in": True})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,  # no reverse proxy / https by default
        path="/",
    )


def clear_login(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def is_logged_in(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False

    s = _serializer()
    try:
        data = s.loads(token, max_age=COOKIE_MAX_AGE_SECONDS)
    except BadSignature:
        return False

    return bool(data.get("logged_in") is True)


def login_expiry_utc() -> str:
    expires = datetime.now(timezone.utc) + timedelta(seconds=COOKIE_MAX_AGE_SECONDS)
    return expires.isoformat()
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.web.auth import is_logged_in


def require_auth(request: Request) -> None:
    if is_logged_in(request):
        return
    # Raise a redirect by returning a response from endpoints (see usage in routes).
    raise RedirectToLogin()


class RedirectToLogin(Exception):
    pass


def login_redirect(next_path: str = "/") -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={next_path}", status_code=303)
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.deps import RedirectToLogin, require_auth


router = APIRouter()


@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request) -> HTMLResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        from app.web.deps import login_redirect

        return login_redirect(next_path="/docs")

    from app.main import templates  # noqa: WPS433

    return templates.TemplateResponse(
        "docs.html",
        {
            "request": request,
            "nav_active": "docs",
        },
    )

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.deps import RedirectToLogin, require_auth


router = APIRouter()


@router.get("/keywords", response_class=HTMLResponse)
async def keywords_page(request: Request) -> HTMLResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        from app.web.deps import login_redirect

        return login_redirect(next_path="/keywords")

    repo = request.app.state.repo
    q = (request.query_params.get("q") or "").strip()
    error = (request.query_params.get("error") or "").strip()
    try:
        page = int(request.query_params.get("page") or "1")
    except ValueError:
        page = 1
    page = max(page, 1)
    limit = 10
    offset = (page - 1) * limit

    keywords, total = await repo.keyword_list(q=q, limit=limit, offset=offset)
    total_pages = max(1, (total + limit - 1) // limit)
    if page > total_pages:
        page = total_pages
        offset = (page - 1) * limit
        keywords, total = await repo.keyword_list(q=q, limit=limit, offset=offset)

    from app.main import templates  # noqa: WPS433

    return templates.TemplateResponse(
        "keywords.html",
        {
            "request": request,
            "nav_active": "keywords",
            "q": q,
            "error": error,
            "total": total,
            "keywords": keywords,
            "page": page,
            "total_pages": total_pages,
            "offset": offset,
        },
    )


@router.post("/keywords/add")
async def keywords_add(request: Request) -> RedirectResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        return RedirectResponse(url="/login?next=/keywords", status_code=303)

    form = await request.form()
    word = (form.get("keyword") or "").strip()
    q = (form.get("q") or "").strip()
    page = (form.get("page") or "").strip()
    params = {}
    if q:
        params["q"] = q
    if page:
        params["page"] = page
    query = f"?{urlencode(params)}" if params else ""
    if not word:
        return RedirectResponse(
            url=f"/keywords?error=Keyword%20is%20empty{query}",
            status_code=303,
        )

    repo = request.app.state.repo
    await repo.keyword_create(word)
    return RedirectResponse(url=f"/keywords{query}", status_code=303)


@router.post("/keywords/delete")
async def keywords_delete(request: Request) -> RedirectResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        return RedirectResponse(url="/login?next=/keywords", status_code=303)

    form = await request.form()
    word = (form.get("keyword") or "").strip()
    q = (form.get("q") or "").strip()
    page = (form.get("page") or "").strip()
    params = {}
    if q:
        params["q"] = q
    if page:
        params["page"] = page
    query = f"?{urlencode(params)}" if params else ""
    if word:
        repo = request.app.state.repo
        await repo.keyword_delete(word)

    return RedirectResponse(url=f"/keywords{query}", status_code=303)

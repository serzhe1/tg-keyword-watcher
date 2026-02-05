from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.web.deps import RedirectToLogin, require_auth


router = APIRouter()


@router.post("/controls/enable")
async def enable_bot(request: Request) -> RedirectResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        return RedirectResponse(url="/login?next=/", status_code=303)

    repo = request.app.state.repo
    await repo.bot_state_set_enabled(True)
    return RedirectResponse(url="/", status_code=303)


@router.post("/controls/disable")
async def disable_bot(request: Request) -> RedirectResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        return RedirectResponse(url="/login?next=/", status_code=303)

    repo = request.app.state.repo
    await repo.bot_state_set_enabled(False)
    return RedirectResponse(url="/", status_code=303)


@router.post("/controls/restart")
async def restart_bot(request: Request) -> RedirectResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        return RedirectResponse(url="/login?next=/", status_code=303)

    repo = request.app.state.repo
    await repo.bot_state_request_restart()
    return RedirectResponse(url="/", status_code=303)
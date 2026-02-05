from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from urllib.parse import urlencode

from app.web.deps import RedirectToLogin, require_auth
from app.web.i18n import t


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


@router.post("/controls/cleanup")
async def cleanup_data(request: Request) -> RedirectResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        return RedirectResponse(url="/login?next=/", status_code=303)

    repo = request.app.state.repo
    result = await repo.cleanup()
    await repo.app_status_set_event(
        f"Cleanup done: event_log={result.get('event_log', 0)}, "
        f"forwarded_messages={result.get('forwarded_messages', 0)}"
    )
    return RedirectResponse(url="/", status_code=303)


@router.post("/controls/target-channel")
async def update_target_channel(request: Request) -> RedirectResponse:
    try:
        require_auth(request)
    except RedirectToLogin:
        return RedirectResponse(url="/login?next=/", status_code=303)

    form = await request.form()
    target = (form.get("target_channel") or "").strip()
    lang = (form.get("lang") or "").strip()
    if not target:
        params = {"error": t("dashboard.target_error_empty", lang)}
        if lang:
            params["lang"] = lang
        return RedirectResponse(url=f"/?{urlencode(params)}", status_code=303)

    repo = request.app.state.repo
    await repo.app_setting_set("target_channel", target)
    await repo.app_status_set_event(f'Target channel updated via UI: "{target}"')
    return RedirectResponse(url=f"/?{urlencode({'lang': lang})}" if lang else "/", status_code=303)

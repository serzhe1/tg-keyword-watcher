from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.db.repo import Repo


class BotRuntime:
    def __init__(self, repo: Repo) -> None:
        self._repo = repo
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task

    async def _run_loop(self) -> None:
        """
        Main bot loop.
        - Polls bot_state from DB
        - Handles enable/disable
        - Handles soft restart via restart_requested_at
        """
        last_restart_seen: datetime | None = None

        await self._repo.app_status_set_event("Bot runtime started")

        try:
            while not self._stop_event.is_set():
                state = await self._repo.bot_state_get()

                # Restart requested
                if state.restart_requested_at and state.restart_requested_at != last_restart_seen:
                    last_restart_seen = state.restart_requested_at
                    await self._repo.app_status_set_event("Soft restart requested")
                    await self._repo.app_status_set_connected(False)
                    await asyncio.sleep(1)
                    continue

                if not state.enabled:
                    await self._repo.app_status_set_connected(False)
                    await asyncio.sleep(1)
                    continue

                # Bot is enabled (real Telethon logic will be here)
                await self._repo.app_status_set_connected(True)

                # Heartbeat / placeholder work
                await asyncio.sleep(2)

        except Exception as exc:
            await self._repo.app_status_set_error(str(exc))
            raise
        finally:
            await self._repo.app_status_set_connected(False)
            await self._repo.app_status_set_event("Bot runtime stopped")
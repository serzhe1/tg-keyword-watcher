from __future__ import annotations

import asyncio
import os
from datetime import datetime

from telethon import TelegramClient
from telethon.errors import RPCError

from app.db.repo import Repo


class BotRuntime:
    def __init__(self, repo: Repo) -> None:
        self._repo = repo
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

        self._client: TelegramClient | None = None

        # Local in-memory cache to avoid spamming DB with the same status updates.
        self._connected_cache: bool | None = None
        self._last_error_cache: str | None = None

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
        - Manages Telethon client lifecycle (connect / disconnect)
        """
        last_restart_seen: datetime | None = None

        await self._repo.app_status_set_event("Bot runtime started")

        try:
            while not self._stop_event.is_set():
                state = await self._repo.bot_state_get()

                # Soft-restart requested from UI.
                if state.restart_requested_at and state.restart_requested_at != last_restart_seen:
                    last_restart_seen = state.restart_requested_at
                    await self._repo.app_status_set_event("Soft restart requested")
                    await self._disconnect_client()
                    await self._set_connected(False)
                    await asyncio.sleep(1)
                    continue

                # Disabled from UI.
                if not state.enabled:
                    await self._disconnect_client()
                    await self._set_connected(False)
                    await asyncio.sleep(1)
                    continue

                # Enabled: ensure Telegram connection exists.
                ok = await self._ensure_connected()

                # If we can't connect right now, back off a little.
                await asyncio.sleep(1 if ok else 3)

        except Exception as exc:
            await self._repo.app_status_set_error(str(exc))
            await self._repo.event_error_add(str(exc))
            raise
        finally:
            await self._disconnect_client()
            await self._set_connected(False)
            await self._repo.app_status_set_event("Bot runtime stopped")

    # ----------------------------
    # Telethon bootstrap
    # ----------------------------
    async def _ensure_connected(self) -> bool:
        """
        Creates and connects Telethon client using mounted .session file.
        Updates app_status.connected and last_error accordingly.
        """
        try:
            api_id_raw = os.environ.get("TELEGRAM_API_ID", "").strip()
            api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
            session_dir = os.environ.get("TELEGRAM_SESSION_DIR", "/app/session").strip()
            session_filename = os.environ.get("TELEGRAM_SESSION_FILE", "monitor.session").strip()
            session_path = os.path.join(session_dir, session_filename)

            api_id = int(api_id_raw or "0")
            if api_id <= 0 or not api_hash:
                await self._set_error("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH in .env")
                await self._set_connected(False)
                return False

            if not os.path.exists(session_path):
                await self._set_error(f"Session file not found: {session_path}")
                await self._set_connected(False)
                return False

            if self._client is None:
                # Telethon can accept full session path (string); it will create additional files if needed.
                self._client = TelegramClient(session_path, api_id, api_hash)
                await self._repo.app_status_set_event("Telethon client created")

            if not self._client.is_connected():
                await self._client.connect()

            # Session must be authorized (created by tools/login.py).
            if not await self._client.is_user_authorized():
                await self._set_error("Telegram session is not authorized. Re-create .session using tools/login.py")
                await self._disconnect_client()
                await self._set_connected(False)
                return False

            await self._set_connected(True)
            await self._set_error(None)
            return True

        except (OSError, ValueError) as exc:
            # OSError: filesystem / socket issues, ValueError: invalid env values
            await self._set_error(str(exc))
            await self._set_connected(False)
            await self._disconnect_client()
            return False

        except RPCError as exc:
            # Telegram RPC-level errors (auth revoked, flood wait, etc.)
            await self._set_error(f"Telegram RPC error: {exc.__class__.__name__}: {exc}")
            await self._set_connected(False)
            await self._disconnect_client()
            return False

        except Exception as exc:
            await self._set_error(f"Telethon connect failed: {exc}")
            await self._set_connected(False)
            await self._disconnect_client()
            return False

    async def _disconnect_client(self) -> None:
        if self._client is None:
            return
        try:
            if self._client.is_connected():
                await asyncio.wait_for(self._client.disconnect(), timeout=10)
        except Exception:
            # Ignore shutdown errors; status will be reported on the next connect attempt anyway.
            pass
        finally:
            self._client = None

    # ----------------------------
    # Status helpers (DB writes throttled)
    # ----------------------------
    async def _set_connected(self, connected: bool) -> None:
        if self._connected_cache is connected:
            return
        self._connected_cache = connected
        await self._repo.app_status_set_connected(connected)

    async def _set_error(self, error: str | None) -> None:
        if error == self._last_error_cache:
            return
        self._last_error_cache = error
        if error is None:
            return
        await self._repo.app_status_set_error(error)
        await self._repo.event_error_add(error)
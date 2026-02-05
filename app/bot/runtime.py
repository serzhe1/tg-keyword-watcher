from __future__ import annotations

import asyncio
import os
import re
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

        # Target channel cache (resolved from dialogs by title)
        self._target_chat_id: int | None = None
        self._target_title: str | None = None

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

    def get_client(self) -> TelegramClient | None:
        """
        Returns Telethon client when created.
        Used by next steps (live handlers / backfill).
        """
        return self._client

    def get_target_chat_id(self) -> int | None:
        """
        Returns resolved target chat id when connected.
        """
        return self._target_chat_id

    def is_target_chat(self, chat_id: int | None) -> bool:
        """
        Prevent infinite forwarding loops.
        Any event/message from target channel must be ignored.
        """
        if chat_id is None or self._target_chat_id is None:
            return False
        return int(chat_id) == int(self._target_chat_id)

    def should_monitor_chat(self, chat_id: int | None) -> bool:
        """
        Centralized rule: never monitor the target channel.
        Future rules can be added here (blacklist, etc.).
        """
        if chat_id is None:
            return False
        if self.is_target_chat(chat_id):
            return False
        return True

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
        Resolves target channel by title (TARGET_CHANNEL env).
        Updates app_status.connected and last_error accordingly.
        """
        try:
            api_id_raw = os.environ.get("TELEGRAM_API_ID", "").strip()
            api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
            session_dir = os.environ.get("TELEGRAM_SESSION_DIR", "/app/session").strip()
            session_filename = os.environ.get("TELEGRAM_SESSION_FILE", "monitor.session").strip()
            session_path = os.path.join(session_dir, session_filename)

            target_title = os.environ.get("TARGET_CHANNEL", "").strip()
            if not target_title:
                await self._set_error("Missing TARGET_CHANNEL in .env (must be target channel title)")
                await self._set_connected(False)
                return False

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

            # Resolve target channel id by title (private channels are resolvable only from dialogs).
            resolved = await self._resolve_target_channel_id(target_title)
            if resolved is None:
                await self._set_connected(False)
                await self._disconnect_client()
                return False

            self._target_chat_id = resolved
            self._target_title = target_title

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

    async def _resolve_target_channel_id(self, target_title: str) -> int | None:
        """
        Resolves target chat id ONLY by dialog title.
        This works for private channels if the account is already a member (dialog exists).
        """
        if self._client is None:
            await self._set_error("Internal error: Telethon client not initialized")
            return None

        wanted = self._normalize_title(target_title)

        matches: list[int] = []
        async for dialog in self._client.iter_dialogs():
            name = (dialog.name or "").strip()
            if not name:
                continue

            if self._normalize_title(name) != wanted:
                continue

            matches.append(int(dialog.id))

        if not matches:
            await self._set_error(
                f'Target channel with title "{target_title}" was not found in account dialogs. '
                f"Make sure the account is already joined and the title matches exactly."
            )
            return None

        if len(matches) > 1:
            await self._set_error(
                f'Multiple dialogs found with title "{target_title}". '
                f"Rename the target channel to a unique title to avoid sending to a wrong destination."
            )
            return None

        await self._repo.app_status_set_event(f'Target channel resolved: "{target_title}"')
        return matches[0]

    @staticmethod
    def _normalize_title(value: str) -> str:
        """
        Normalization rules:
        - case-insensitive
        - treat 'ё' as 'е'
        - collapse multiple spaces
        """
        v = value.strip().lower().replace("ё", "е")
        v = re.sub(r"\s+", " ", v)
        return v

    async def _disconnect_client(self) -> None:
        # Reset caches related to Telegram session
        self._target_chat_id = None
        self._target_title = None

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
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime

from telethon import TelegramClient, events
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

        # Live handlers lifecycle
        self._handlers_installed: bool = False

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
        """Returns Telethon client when created."""
        return self._client

    def get_target_chat_id(self) -> int | None:
        """Returns resolved target chat id when connected."""
        return self._target_chat_id

    def is_target_chat(self, chat_id: int | None) -> bool:
        """Prevent infinite forwarding loops."""
        if chat_id is None or self._target_chat_id is None:
            return False
        return int(chat_id) == int(self._target_chat_id)

    def should_monitor_chat(self, chat_id: int | None) -> bool:
        """Centralized rule: never monitor the target channel."""
        if chat_id is None:
            return False
        if self.is_target_chat(chat_id):
            return False
        return True

    async def _run_loop(self) -> None:
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

    async def _ensure_connected(self) -> bool:
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

            if not await self._client.is_user_authorized():
                await self._set_error("Telegram session is not authorized. Re-create .session using tools/login.py")
                await self._disconnect_client()
                await self._set_connected(False)
                return False
            # Ensure no updates gap after reconnect (important for channels with high traffic).
            try:
                await self._client.catch_up()
            except Exception as exc:
                # Do not fail connection, but report the issue for visibility.
                await self._repo.app_status_set_error(f"Telethon catch_up failed: {exc}")
                await self._repo.event_error_add(f"Telethon catch_up failed: {exc}")
            # Resolve target channel id by title (dialogs scan).
            resolved = await self._resolve_target_channel_id(target_title)
            if resolved is None:
                await self._set_connected(False)
                await self._disconnect_client()
                return False

            # Preserve last event: do not overwrite it on every reconnect.
            prev_target_id = self._target_chat_id
            prev_target_title = self._target_title

            self._target_chat_id = resolved
            self._target_title = target_title

            if prev_target_id != resolved or (prev_target_title or "") != target_title:
                await self._repo.app_status_set_event(f'Target channel resolved: "{target_title}"')

            # Install live monitoring handlers once per client lifecycle.
            if not self._handlers_installed:
                self._install_live_handlers()
                self._handlers_installed = True
                await self._repo.app_status_set_event("Live monitoring enabled")

            await self._set_connected(True)
            await self._set_error(None)
            return True

        except (OSError, ValueError) as exc:
            await self._set_error(str(exc))
            await self._set_connected(False)
            await self._disconnect_client()
            return False

        except RPCError as exc:
            await self._set_error(f"Telegram RPC error: {exc.__class__.__name__}: {exc}")
            await self._set_connected(False)
            await self._disconnect_client()
            return False

        except Exception as exc:
            await self._set_error(f"Telethon connect failed: {exc}")
            await self._set_connected(False)
            await self._disconnect_client()
            return False

    def _install_live_handlers(self) -> None:
        """
        Live monitoring for all groups and channels the account is subscribed to.
        IMPORTANT: Do not call get_chat()/get_entity() here (hot path).
        """
        if self._client is None:
            return

        async def _on_new_message(event: events.NewMessage.Event) -> None:
            try:
                chat_id = int(event.chat_id) if event.chat_id is not None else None

                # Monitor only groups/channels, ignore private dialogs.
                if not (event.is_channel or event.is_group):
                    return

                # Never react to messages from target channel (loop protection).
                if not self.should_monitor_chat(chat_id):
                    return

                # We only record the last event for UI (no success logs).
                msg_id = int(getattr(event.message, "id", 0) or 0)
                text = (getattr(event.message, "message", "") or "").strip()
                if len(text) > 120:
                    text = text[:120] + "..."

                await self._repo.app_status_set_event(
                    f"New message: chat_id={chat_id} message_id={msg_id} text={text}"
                )

            except Exception as exc:
                await self._repo.app_status_set_error(str(exc))
                await self._repo.event_error_add(str(exc))

        self._client.add_event_handler(_on_new_message, events.NewMessage())

    async def _resolve_target_channel_id(self, target_title: str) -> int | None:
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

        return matches[0]

    @staticmethod
    def _normalize_title(value: str) -> str:
        v = value.strip().lower().replace("ё", "е")
        v = re.sub(r"\s+", " ", v)
        return v

    async def _disconnect_client(self) -> None:
        # Reset caches related to Telegram session
        self._target_chat_id = None
        self._target_title = None
        self._handlers_installed = False

        if self._client is None:
            return
        try:
            if self._client.is_connected():
                await asyncio.wait_for(self._client.disconnect(), timeout=10)
        except Exception:
            pass
        finally:
            self._client = None

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
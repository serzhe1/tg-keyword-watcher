import os
import asyncio
from telethon import TelegramClient

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]

SESSION_DIR = os.environ.get("SESSION_DIR_LOCAL", "./data/session")
SESSION_NAME = os.environ.get("SESSION_NAME", "monitor")

os.makedirs(SESSION_DIR, exist_ok=True)
session_path = os.path.join(SESSION_DIR, SESSION_NAME)


async def main():
    print(f"Session will be saved to: {session_path}.session")
    print("You will be asked for phone number and code (and 2FA password if enabled).")

    async with TelegramClient(session_path, API_ID, API_HASH) as client:
        await client.start()
        me = await client.get_me()

        name = me.username or me.first_name or "unknown"
        print(f"Logged in as: {name} (id={me.id})")


if __name__ == "__main__":
    asyncio.run(main())
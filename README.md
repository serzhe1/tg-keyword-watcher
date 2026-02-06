# tg-keyword-watcher

Telegram monitoring bot with a small admin UI.  
It scans channels and groups for keywords and forwards matched messages to a target channel.

**What it does**
- Monitors all channels and groups the account is subscribed to
- Searches messages by keywords (case-insensitive, `е` equals `ё`, substring match)
- Forwards matches to the target channel with a short preface message
- Prevents duplicates with idempotent DB logic
- Supports backfill after downtime using per-channel checkpoints
- Provides an admin UI for status, keywords, logs, and docs
- Cleans up old data (manual or nightly schedule)

## Quick Start (Docker)

1. Create `.env` from `.env.example` and fill values.
2. Create a Telegram session file (see below).
3. Start services:
```bash
docker compose up -d --build
```
4. Open `http://localhost:8080` and log in.

## Create Telegram Session File

The bot uses a Telethon `.session` file. You must create it **once** and place it into `./data/session`.

### Steps

1. Get `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`:
   - Go to https://my.telegram.org
   - Create an application (API Development Tools)
   - Copy the `api_id` and `api_hash`

2. Run the login helper locally (tools/login.py):
```bash
export TELEGRAM_API_ID=...
export TELEGRAM_API_HASH=...
export SESSION_DIR_LOCAL=./data/session
export SESSION_NAME=monitor
python tools/login.py
```

You will be asked for:
- your phone number
- Telegram confirmation code
- 2FA password (if enabled)

3. The script will create:
```
./data/session/monitor.session
```

In Docker, the folder `./data/session` is mounted to `/app/session`,
so the container will see the same session file.

### Tips
- The session is bound to the Telegram account used during login.
- If the session becomes invalid, re-run `tools/login.py`.

## Environment Variables

Set these in `.env`:

| Variable | Required | Example | Description |
|---|---|---|---|
| `POSTGRES_DB` | yes | `tgmon` | Database name |
| `POSTGRES_USER` | yes | `tgmon` | Database user |
| `POSTGRES_PASSWORD` | yes | `change_me` | Database password |
| `DATABASE_URL` | yes | `postgresql://tgmon:change_me@db:5432/tgmon` | App DB connection |
| `ADMIN_LOGIN` | yes | `admin` | Admin UI login |
| `ADMIN_PASSWORD` | yes | `strong_password` | Admin UI password |
| `APP_SECRET_KEY` | yes | `long_random_string` | Signs session cookies |
| `TELEGRAM_API_ID` | yes | `123456` | Telegram API ID |
| `TELEGRAM_API_HASH` | yes | `abc123...` | Telegram API hash |
| `TARGET_CHANNEL` | yes | `My Target Channel` | Destination channel title or @username |
| `TELEGRAM_SESSION_DIR` | yes | `/app/session` | Where `.session` is stored in container |
| `TELEGRAM_SESSION_FILE` | yes | `monitor.session` | Session filename |
| `APP_NAME` | no | `My Bot` | UI branding |
| `BACKFILL_PAGE_SIZE` | no | `100` | Backfill page size |
| `FORWARD_PENDING_TIMEOUT_SECONDS` | no | `300` | Retry window for duplicate protection |

Local-only (used by `tools/login.py`):

| Variable | Required | Example | Description |
|---|---|---|---|
| `SESSION_DIR_LOCAL` | no | `./data/session` | Local folder for session creation |
| `SESSION_NAME` | no | `monitor` | Session name for local login |

## Admin UI

Main pages:
- Dashboard: status and control buttons
- Keywords: add/remove/search keywords
- Logs: recent errors with pagination
- Docs: non-technical instructions

Dashboard fields:
- **Connected**: bot is connected to Telegram
- **Bot enabled**: monitoring is enabled
- **Last error**: most recent error
- **Last event**: last important action

Buttons:
- **Enable**: start monitoring
- **Disable**: stop monitoring
- **Restart**: soft reconnect (keeps server running)
- **Cleanup**: removes old data

## Backfill (Missed Messages)

Backfill means the bot checks messages that appeared while it was offline or restarting.

How it works:
- For each channel, the bot stores a checkpoint (last processed message).
- After reconnect, it scans messages after that checkpoint.
- It forwards matches and updates the checkpoint.

This prevents missing messages during downtime.

## Cleanup Policy

Manual cleanup (button in Dashboard) and nightly cleanup:
- `event_log`: delete records older than 7 days
- `forwarded_messages`: delete records older than 30 days

Nightly cleanup runs at **03:00 UTC**.

## Operations (Makefile)

Common commands:
- `make deploy` — build and start
- `make rebuild` — full rebuild and restart
- `make rebuild-clean` — rebuild and prune unused images
- `make destroy` — remove containers, volumes, images, and local data

Run `make help` to see all targets.

## Troubleshooting

If `Connected = NO`:
- Check the `.session` file is present and valid
- Verify `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- Press **Restart** in Dashboard

If messages are not forwarded:
- Check the keyword list
- Confirm the target channel is correct
- Look at **Logs**

If login fails:
- Verify `ADMIN_LOGIN` / `ADMIN_PASSWORD`
- Ensure `APP_SECRET_KEY` is set

## Security Notes

- Never commit `.env` or session files
- Use a strong `APP_SECRET_KEY`
- Keep the admin URL private or protect it with a reverse proxy if public

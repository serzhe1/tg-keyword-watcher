import os

def _must(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

DATABASE_URL = _must("DATABASE_URL")
ADMIN_LOGIN = _must("ADMIN_LOGIN")
ADMIN_PASSWORD = _must("ADMIN_PASSWORD")
COOKIE_SECRET = _must("COOKIE_SECRET")
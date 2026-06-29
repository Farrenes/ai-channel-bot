from __future__ import annotations

import os
from typing import Iterable, List, Set

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - lightweight fallback
    def load_dotenv() -> None:
        return None


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

ROUTERAI_API_KEY = os.getenv("ROUTERAI_API_KEY")
ROUTERAI_BASE_URL = os.getenv("ROUTERAI_BASE_URL", "https://routerai.ru/api/v1")
ROUTERAI_MODEL = os.getenv("ROUTERAI_MODEL", "deepseek/deepseek-v4-pro")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

_allowed_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: Set[int] = {int(uid) for uid in _allowed_raw.split(",") if uid.strip().isdigit()}

ENV_VALUES = {
    "BOT_TOKEN": BOT_TOKEN,
    "ADMIN_BOT_TOKEN": ADMIN_BOT_TOKEN,
    "CHANNEL_ID": CHANNEL_ID,
    "ROUTERAI_API_KEY": ROUTERAI_API_KEY,
    "DB_HOST": DB_HOST,
    "DB_NAME": DB_NAME,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
}

CORE_ENV_NAMES = (
    "ROUTERAI_API_KEY",
    "DB_HOST",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)
MAIN_BOT_ENV_NAMES = CORE_ENV_NAMES + ("BOT_TOKEN", "CHANNEL_ID")
ADMIN_BOT_ENV_NAMES = MAIN_BOT_ENV_NAMES + ("ADMIN_BOT_TOKEN",)


def get_missing_env_vars(required_names: Iterable[str] = MAIN_BOT_ENV_NAMES) -> List[str]:
    return [name for name in required_names if not ENV_VALUES.get(name)]


def validate_required_env(required_names: Iterable[str] = MAIN_BOT_ENV_NAMES) -> None:
    missing = get_missing_env_vars(required_names)
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))

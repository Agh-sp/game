"""تنظیمات پروژه — توکن‌ها و مسیر دیتابیس از فایل .env یا متغیرهای محیطی."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            v = value.strip()
            if v:
                os.environ[key.strip()] = v
    except Exception:
        pass


_load_env()

GAME_BOT_TOKEN = os.getenv("GAME_BOT_TOKEN", "")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "wwgame.db"))


def check_tokens(admin: bool = True) -> None:
    """در زمان اجرا بررسی می‌کند توکن‌ها تنظیم شده باشند."""
    missing = []
    if not GAME_BOT_TOKEN:
        missing.append("GAME_BOT_TOKEN")
    if admin and not ADMIN_BOT_TOKEN:
        missing.append("ADMIN_BOT_TOKEN")
    if missing:
        raise SystemExit(
            "❌ توکن‌های ربات تنظیم نشده‌اند: "
            + ", ".join(missing)
            + "\nفایل .env.example را به .env تغییر نام دهید و توکن‌ها را از @BotFather بگیرید."
        )

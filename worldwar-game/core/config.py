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
_raw_db = os.getenv("DB_PATH", "").strip()
if _raw_db:
    DB_PATH = str(Path(_raw_db).resolve()) if os.path.isabs(_raw_db) else str((BASE_DIR / _raw_db).resolve())
else:
    DB_PATH = str((BASE_DIR / "wwgame.db").resolve())


# ── Webhook (اجرای ربات‌ها روی یک آدرس عمومی به‌جای polling) ──
WEBHOOK_ENABLED = os.getenv("WEBHOOK_ENABLED", "0").strip() in ("1", "true", "True", "yes")
# آدرس عمومی اپلیکیشن (همان Web App) — مثلاً https://myapp.example.com
PUBLIC_BASE_URL = (os.getenv("WEBHOOK_BASE_URL") or os.getenv("PUBLIC_URL") or "").strip().rstrip("/")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080") or 8080)
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0") or "0.0.0.0"
# کلید امنیتی تلگرام برای وبهوک (هدر X-Telegram-Bot-Api-Secret-Token)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
WEBHOOK_PATH_GAME = "/webhook/game"
WEBHOOK_PATH_ADMIN = "/webhook/admin"
# فاصله پینگ سلامت (دقیقه) — برای زنده نگه‌داشتن سرویس
KEEPALIVE_MINUTES = int(os.getenv("KEEPALIVE_MINUTES", "10") or 10)


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

"""تنظیمات پروژه — توکن ربات‌ها، آیدی ادمین و مسیر دیتابیس.

توکن‌ها و آیدی ادمین **مستقیماً در همین فایل** ثبت شده‌اند (خواستهٔ مالک پروژه)،
بنابراین ربات‌ها بدون هیچ فایل `.env` هم بالا می‌آیند. اگر فایل `.env` یا متغیر
محیطی وجود داشته باشد، همان مقدار اولویت دارد و می‌تواند این پیش‌فرض‌ها را
بازنویسی کند.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ─── اطلاعات ربات‌ها (ثابت — داخل کد) ───
# توکن ربات اصلی بازی (ربات بازیکن‌ها)
DEFAULT_GAME_BOT_TOKEN = "9201202722:AAGuSaJQw16F_ugrKXUidttYfMqI9Cz3SVE"
# توکن ربات ادمین (پنل مدیریت)
DEFAULT_ADMIN_BOT_TOKEN = "9000162449:AAG-xoIDUSgE1LFWr1L3BOZjygueYuCZOfU"
# آیدی عددی ادمینِ کل (سوپرادمین اصلی)
DEFAULT_ADMIN_ID = 8666501866


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

GAME_BOT_TOKEN = os.getenv("GAME_BOT_TOKEN", "").strip() or DEFAULT_GAME_BOT_TOKEN
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip() or DEFAULT_ADMIN_BOT_TOKEN

# ── ادمین‌ها ──
# سوپرادمین‌های ثابت بازی (همیشه دسترسی کامل دارند، حتی بدون تنظیم .env)
DEFAULT_SUPER_ADMIN_IDS: tuple[int, ...] = (DEFAULT_ADMIN_ID,)


def _parse_ids(raw: str) -> list[int]:
    """تبدیل «1,2 3;4» به لیست آیدی عددی."""
    out: list[int] = []
    for part in str(raw or "").replace(";", ",").replace("،", ",").split(","):
        for token in part.split():
            token = token.strip()
            if token.isdigit():
                out.append(int(token))
    return out


SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0").strip() or 0) or DEFAULT_ADMIN_ID
# آیدی‌های اضافی از .env: SUPER_ADMIN_IDS=111111,222222
SUPER_ADMIN_IDS: tuple[int, ...] = tuple(dict.fromkeys(
    [SUPER_ADMIN_ID, *_parse_ids(os.getenv("SUPER_ADMIN_IDS", "")), *DEFAULT_SUPER_ADMIN_IDS]
))
_raw_db = os.getenv("DB_PATH", "").strip()
if _raw_db:
    DB_PATH = str(Path(_raw_db).resolve()) if os.path.isabs(_raw_db) else str((BASE_DIR / _raw_db).resolve())
else:
    DB_PATH = str((BASE_DIR / "wwgame.db").resolve())


# ── وب (پنل فرماندهی + وبهوک) ──
# پورت سرویس وب (همان پنلی که در مرورگر باز می‌شود)
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "3000")) or 3000)
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0") or "0.0.0.0"

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
# اجرای خودکار ربات‌ها هنگام بالا آمدن سرور وب (AUTOSTART_BOTS=0 خاموش می‌کند)
BOTS_AUTOSTART = os.getenv("AUTOSTART_BOTS", "1").strip().lower() not in ("0", "false", "no", "off")
# وضعیت پیش‌فرض اجرای ربات‌ها: polling (پیش‌فرض) یا webhook
WEBHOOK_MODE = os.getenv("WEBHOOK_MODE", os.getenv("WEBHOOK_ENABLED", "0")).strip().lower() in ("1", "true", "yes")


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
            + "\nتوکن‌ها را در worldwar-game/core/config.py یا فایل .env قرار دهید."
        )

"""🛡 امنیت عملیاتی — لاگ اقدام‌های حساس، محدودیت نرخ، قفل اعلان همگانی و
هشدارهای خودکار.

چرا این ماژول؟
  پیش از این، یک پیام همگانی (ارسال به همهٔ کاربران) فقط با یک دکمه از پنل
  ادمین قابل اجرا بود و **هیچ‌جا ثبت نمی‌شد**. اگر کسی به حساب ادمین یا توکن
  ربات دست پیدا می‌کرد، می‌توانست برای همهٔ بازیکنان پیام بفرستد و هیچ ردّی هم
  نمی‌ماند. این ماژول سه لایه می‌گذارد:

  ۱) **لاگ امنیتی** (`security_events`): هر اقدام حساس (همگانی، تغییر تنظیمات،
     ریست، خروجی گرفتن از پنل وب، تلاش ناموفق احراز هویت) با آیدی، IP و زمان.
  ۲) **محدودیت نرخ**: هر کاربر در بازهٔ مشخص فقط چند بار می‌تواند اقدام حساس
     انجام دهد (ضد اسپم/ضد سوءاستفاده در صورت لو رفتن حساب).
  ۳) **قفل همگانی + تأیید دو‌مرحله‌ای**: ارسال به همه فقط با کد تأیید همراه
     است؛ کد یک‌بار مصرف است و در لاگ ثبت می‌شود.

همچنین `alert()` هر رخداد مشکوک را فوراً به مالک ربات (سوپرادمین) می‌فرستد تا
اگر کسی از بیرون پیام فرستاد، در همان لحظه بفهمید.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict

from core.db import db, get_setting, set_setting
from core.utils import fmt, iso

log = logging.getLogger(__name__)

# ─── برچسب انواع رخداد ───
KIND_TITLES = {
    "broadcast": "📣 پیام همگانی",
    "broadcast_denied": "🚫 تلاش رد‌شدهٔ پیام همگانی",
    "settings": "⚙️ تغییر تنظیمات",
    "reset": "🧨 ریست",
    "user_edit": "👤 تغییر کاربر",
    "auth_fail": "🔑 تلاش ناموفق ورود",
    "web_api": "🌐 درخواست حساس پنل وب",
    "weird_text": "🧩 متن مشکوک به دستکاری",
    "lock": "🔒 قفل ایمنی",
}


async def init_tables() -> None:
    """ساخت جدول‌های امنیتی (idempotent)."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS security_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT DEFAULT '',
          user_id INTEGER DEFAULT 0,
          ip TEXT DEFAULT '',
          detail TEXT DEFAULT '',
          created_at TEXT DEFAULT (datetime('now'))
        )""")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS security_alerts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          to_user INTEGER DEFAULT 0,
          text TEXT DEFAULT '',
          sent INTEGER DEFAULT 0,
          created_at TEXT DEFAULT (datetime('now'))
        )""")
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_sec_events_kind ON security_events(kind, created_at)")


# ─── لاگ ───

async def record(kind: str, user_id: int = 0, detail: str = "",
                 ip: str = "") -> None:
    """ثبت یک رخداد امنیتی (اگر جدول نبود، بی‌صدا رد می‌شود)."""
    try:
        await db.execute(
            "INSERT INTO security_events(kind, user_id, ip, detail, created_at) "
            "VALUES(?,?,?,?,?)",
            (kind[:40], int(user_id or 0), (ip or "")[:60], (detail or "")[:400], iso()))
    except Exception:
        log.exception("security record failed")


async def recent(kind: str | None = None, limit: int = 20) -> list[dict]:
    """آخرین رخدادهای امنیتی (برای پنل ادمین)."""
    try:
        if kind:
            return await db.fetchall(
                "SELECT * FROM security_events WHERE kind=? ORDER BY id DESC LIMIT ?",
                (kind, int(limit)))
        return await db.fetchall(
            "SELECT * FROM security_events ORDER BY id DESC LIMIT ?", (int(limit),))
    except Exception:
        return []


async def counts_since(hours: float = 24) -> dict[str, int]:
    """شمارش رخدادها در بازهٔ ساعت‌های اخیر."""
    from core.utils import parse, now
    from datetime import timedelta
    since = iso(now() - timedelta(hours=hours))
    out: dict[str, int] = {}
    try:
        rows = await db.fetchall(
            "SELECT kind, COUNT(*) c FROM security_events WHERE created_at>=? GROUP BY kind",
            (since,))
        for r in rows:
            out[r["kind"]] = int(r["c"] or 0)
    except Exception:
        pass
    return out


# ─── محدودیت نرخ ───

_BUCKETS: dict[tuple[str, int], list[float]] = defaultdict(list)


def rate_ok(action: str, user_id: int, limit: int, window_seconds: int,
            consume: bool = True) -> tuple[bool, int]:
    """آیا این کاربر در این بازه مجاز به تکرار اقدام است؟

    خروجی: (مجاز؟, ثانیه تا آزاد شدن). حافظه‌ای است و برای چند ادمین کافی است.
    با `consume=False` فقط بررسی می‌شود و شمارنده بالا نمی‌رود (برای مراحل
    میانی یک جریان چند‌پیامی مثل پیام همگانی).
    """
    key = (action, int(user_id or 0))
    now_ts = time.time()
    bucket = [t for t in _BUCKETS[key] if now_ts - t < window_seconds]
    _BUCKETS[key] = bucket
    if len(bucket) >= limit:
        wait = int(window_seconds - (now_ts - bucket[0])) + 1
        return False, max(1, wait)
    if consume:
        bucket.append(now_ts)
    return True, 0


def reset_rate(action: str | None = None) -> None:
    """پاک‌کردن حافظهٔ محدودیت نرخ (برای تست)."""
    if action is None:
        _BUCKETS.clear()
        return
    for key in list(_BUCKETS):
        if key[0] == action:
            _BUCKETS.pop(key, None)


# ─── قفل ایمنی همگانی ───

async def broadcast_lock_active() -> bool:
    """آیا ارسال همگانی موقتاً قفل شده است؟"""
    until = await get_setting("broadcast_lock_until", "")
    from core.utils import is_past
    return bool(until) and not is_past(until)


async def lock_broadcast(minutes: int = 60, reason: str = "") -> str:
    """قفل اضطراری پیام همگانی (پس از سوءاستفاده)."""
    from core.utils import add_hours
    until = add_hours(minutes / 60)
    await set_setting("broadcast_lock_until", until)
    await record("lock", 0, f"قفل همگانی تا {until} — {reason}")
    return until


async def unlock_broadcast() -> None:
    await set_setting("broadcast_lock_until", "")
    await record("lock", 0, "قفل همگانی برداشته شد")


# ─── کد تأیید یک‌بارمصرف ───

_PENDING: dict[int, dict] = {}


def make_code(user_id: int, text: str) -> str:
    """ساخت کد ۴رقمی برای تأیید ارسال همگانی (۱۰ دقیقه اعتبار)."""
    import random
    code = f"{random.randint(1000, 9999)}"
    _PENDING[int(user_id)] = {"code": code, "text": text, "at": time.time()}
    return code


def check_code(user_id: int, code: str) -> tuple[bool, str]:
    """بررسی کد تأیید؛ یک‌بار مصرف و حداکثر ۱۰ دقیقه اعتبار."""
    item = _PENDING.get(int(user_id))
    if not item:
        return False, "کدی برای تأیید ثبت نشده است."
    if time.time() - item["at"] > 600:
        _PENDING.pop(int(user_id), None)
        return False, "کد منقضی شده — دوباره تلاش کنید."
    if str(code).strip() != item["code"]:
        return False, "کد اشتباه است."
    _PENDING.pop(int(user_id), None)
    return True, item["text"]


def pending_text(user_id: int) -> str | None:
    item = _PENDING.get(int(user_id))
    if not item or time.time() - item["at"] > 600:
        return None
    return item["text"]


# ─── هشدار به مالک ───

ALERT_TO_SETTING = "security_alert_to"


async def alert_targets() -> list[int]:
    """گیرندگان هشدار امنیتی: مقدار تنظیم + .env + سوپرادمین‌های کانفیگ."""
    import os

    targets: list[int] = []
    try:
        raw = ((await get_setting(ALERT_TO_SETTING, "")) or "").strip()
        raw = f"{raw},{os.getenv('SECURITY_ALERT_TO', '')}"
        for part in raw.replace("،", ",").split(","):
            part = part.strip()
            if part.isdigit():
                targets.append(int(part))
    except Exception:
        pass
    try:
        from core.config import SUPER_ADMIN_IDS
        targets.extend(int(i) for i in SUPER_ADMIN_IDS if i)
    except Exception:
        pass
    return list(dict.fromkeys(targets))


async def alert(bot, text: str, kind: str = "alert") -> None:
    """ارسال فوری هشدار امنیتی به مالک ربات‌ها."""
    if bot is None:
        return
    body = f"🛡 <b>هشدار امنیتی</b>\n\n{text}"
    for uid in await alert_targets():
        try:
            await bot.send_message(uid, body)
        except Exception:
            continue
    await record(kind, 0, text)


# ─── کمک‌کنندهٔ امن متن ───

WEIRD_TOKENS = ("\u200b", "\u200c\u200c", "\u2066", "\u2067", "\u2068", "\u2069",
                "\u202a", "\u202b", "\u202c", "\u202d", "\u202e")


def sanitize_text(text: str, limit: int = 3500) -> tuple[str, list[str]]:
    """پاک‌سازی متن ارسالی به کاربران.

    • حذف نویسه‌های کنترلی دوطرفه (RTL override) که برای جعل ظاهر پیام
      استفاده می‌شوند،
    • حذف تگ‌های HTML غیرمجاز (تلگرام فقط b/i/u/s/code/pre/a/blockquote را
      می‌پذیرد و تگ ناشناخته کل پیام را خراب می‌کند)،
    • محدودیت طول،
    • برگرداندن فهرست هشدارها تا در لاگ ثبت شود.
    """
    import re

    warnings: list[str] = []
    raw = text or ""
    for token in WEIRD_TOKENS:
        if token in raw:
            raw = raw.replace(token, "")
            warnings.append("نویسهٔ کنترلی دوطرفه حذف شد")
    if raw.count("<") > 40:
        warnings.append("تعداد تگ‌های HTML زیاد است")
    allowed = ("b", "i", "u", "s", "code", "pre", "a", "blockquote", "tg-spoiler")

    def _tag(match: re.Match) -> str:
        full, closing, name = match.group(0), match.group(1), match.group(2).lower()
        if name not in allowed:
            warnings.append(f"تگ غیرمجاز حذف شد: <{name}>")
            return ""
        return full

    raw = re.sub(r"<(/?)\s*([a-zA-Z0-9-]+)[^>]*>", _tag, raw)
    return raw[:limit], list(dict.fromkeys(warnings))


def security_summary(counts: dict[str, int]) -> str:
    """خلاصهٔ خوانا از شمارش رخدادها."""
    if not counts:
        return "— هیچ رخداد امنیتی ثبت نشده —"
    lines = []
    for kind, value in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"  • {KIND_TITLES.get(kind, kind)}: <b>{fmt(value)}</b>")
    return "\n".join(lines)


# ═══════════════════════════════ کلید وبهوک ═══════════════════════════════
# قانون طلایی: اگر کلید وبهوک خالی باشد، **هر کسی** می‌تواند یک Update جعلی
# به /webhook/... POST کند و خودش را جای ادمین جا بزند. پس کلید همیشه هست:
# از .env، وگرنه از دیتابیس، وگرنه همین‌جا با طول ۴۳ نویسه ساخته و ذخیره می‌شود.

MIN_SECRET_LEN = 16


async def ensure_webhook_secret() -> tuple[str, bool]:
    """کلید وبهوک را برمی‌گرداند و اگر نبود می‌سازد. (کلید, تازه‌ساخته‌شد؟)"""
    import os
    import secrets as _secrets

    from core import config as cfg

    current = (os.getenv("WEBHOOK_SECRET") or cfg.WEBHOOK_SECRET or "").strip()
    if len(current) >= MIN_SECRET_LEN:
        cfg.WEBHOOK_SECRET = current
        return current, False
    try:
        stored = (await get_setting("webhook_secret", "") or "").strip()
    except Exception:
        stored = ""
    if len(stored) >= MIN_SECRET_LEN:
        cfg.WEBHOOK_SECRET = stored
        os.environ["WEBHOOK_SECRET"] = stored
        return stored, False
    fresh = _secrets.token_urlsafe(32)
    try:
        await set_setting("webhook_secret", fresh)
    except Exception:
        log.exception("ذخیرهٔ کلید وبهوک ناموفق بود (کلید فقط در حافظه می‌ماند)")
    cfg.WEBHOOK_SECRET = fresh
    os.environ["WEBHOOK_SECRET"] = fresh
    log.warning("🔐 کلید وبهوک ساخته شد (چون تنظیم نبود) — در دیتابیس ذخیره شد")
    return fresh, True


def secret_matches(expected: str, got: str) -> bool:
    """مقایسهٔ زمان‌ثابت کلید وبهوک — بدون کلید، همیشه رد می‌شود."""
    import hmac

    expected = (expected or "").strip()
    got = (got or "").strip()
    if not expected:
        return False
    return hmac.compare_digest(expected.encode(), got.encode())


class ReplayGuard:
    """جلوگیری از پردازش دوبارهٔ یک آپدیت (update_id تکراری).

    اگر کسی یک آپدیت را ضبط و دوباره ارسال کند (replay) یا تلگرام دوباره
    بفرستد، اثر دوگانه (مثلاً دو پیام همگانی) نمی‌گذارد.
    """

    def __init__(self, ttl: int = 1800, max_items: int = 8000) -> None:
        self.ttl = ttl
        self.max_items = max_items
        self._seen: dict[str, float] = {}

    def duplicate(self, key: str) -> bool:
        now_ts = time.time()
        if len(self._seen) > self.max_items:
            self._seen = {k: v for k, v in self._seen.items() if now_ts - v < self.ttl}
        old = self._seen.get(key)
        self._seen[key] = now_ts
        return old is not None and now_ts - old < self.ttl

    def clear(self) -> None:
        self._seen.clear()


class RateLimiter:
    """سطل توکنی ساده برای محدودکردن نرخ درخواست‌های وبهوک/پنل."""

    def __init__(self, per_minute: int = 240) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now_ts = time.time()
        window = [t for t in self._hits[key] if now_ts - t < 60]
        self._hits[key] = window
        if len(window) >= self.per_minute:
            return False
        window.append(now_ts)
        return True


# ═══════════════════════════════ گذرواژهٔ پنل ═══════════════════════════════
# پنل وب قبلاً هیچ احراز هویتی نداشت: هر کسی که آدرس سایت را می‌دانست می‌توانست
# توکن‌ها را از /api/secrets بخواند، کاربران را حذف کند یا ربات را خاموش کند.

PANEL_PASSWORD_KEY = "panel_password"
PANEL_TOKEN_TTL = 12 * 3600


async def ensure_panel_password() -> tuple[str, bool]:
    """گذرواژهٔ پنل وب: از .env یا دیتابیس؛ اگر نبود ساخته می‌شود."""
    import os
    import secrets as _secrets

    env = (os.getenv("PANEL_PASSWORD") or "").strip()
    if len(env) >= 6:
        return env, False
    try:
        stored = (await get_setting(PANEL_PASSWORD_KEY, "") or "").strip()
    except Exception:
        stored = ""
    if len(stored) >= 6:
        os.environ["PANEL_PASSWORD"] = stored
        return stored, False
    fresh = _secrets.token_urlsafe(12)
    try:
        await set_setting(PANEL_PASSWORD_KEY, fresh)
    except Exception:
        log.exception("ذخیرهٔ گذرواژهٔ پنل ناموفق بود")
    log.warning("🔑 گذرواژهٔ پنل وب ساخته شد: %s  (برای دیدن دوباره: پنل ادمین → 🔐 امنیت)", fresh)
    return fresh, True


async def set_panel_password(new_password: str) -> str:
    """تعیین گذرواژهٔ تازه برای پنل وب (حداقل ۸ نویسه)."""
    import secrets as _secrets

    pwd = (new_password or "").strip()
    if len(pwd) < 8:
        pwd = _secrets.token_urlsafe(12)
    await set_setting(PANEL_PASSWORD_KEY, pwd)
    import os
    os.environ["PANEL_PASSWORD"] = pwd
    await record("lock", 0, "گذرواژهٔ پنل وب تغییر کرد")
    return pwd


def sign_session(password: str, ttl: int = PANEL_TOKEN_TTL) -> str:
    """ساخت کوکی نشست امضاشده: «<انقضا>.<امضا>»."""
    import hashlib
    import hmac

    exp = int(time.time()) + int(ttl)
    mac = hmac.new(password.encode(), f"panel|{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{mac}"


def verify_session(password: str, token: str) -> bool:
    """اعتبارسنجی کوکی نشست (امضا + انقضا)."""
    import hashlib
    import hmac

    if not password or not token or "." not in token:
        return False
    exp_s, mac = token.split(".", 1)
    if not exp_s.isdigit() or int(exp_s) < int(time.time()):
        return False
    want = hmac.new(password.encode(), f"panel|{int(exp_s)}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, mac)

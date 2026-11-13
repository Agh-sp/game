"""🔌 نقطهٔ ورود WSGI برای میزبانی ربات‌ها روی **PythonAnywhere** (یا هر هاست WSGI).

در این حالت ربات‌ها با **Webhook** کار می‌کنند: خودِ تلگرام هر پیام را به آدرس
عمومی این فایل POST می‌کند و ما آن را به Dispatcher های aiogram می‌دهیم. بنابراین:

  • نیازی به polling، پروسهٔ همیشه روشن، ترد یا پس‌زمینه نیست (روی پلن رایگان
    PythonAnywhere هیچ‌کدام از این‌ها مجاز نیست)،
  • روی حساب رایگان PythonAnywhere فقط باید از **پروکسی** برای تماس با تلگرام
    استفاده شود (`PAW_PROXY=1`) — این فایل خودش پروکسی را تنظیم می‌کند،
  • دیتابیس SQLite کنار پروژه ساخته می‌شود (`worldwar-game/wwgame.db`).

── راه‌اندازی روی PythonAnywhere ──────────────────────────────────────────────
۱) کد را در `/home/USERNAME/game` قرار دهید (Git یا Upload).

۲) در «Bash console»:
       cd /home/USERNAME/game/worldwar-game
       pip3.10 install --user -r requirements.txt flask

۳) فایل WSGI (از تب **Web → WSGI configuration file**) را کاملاً با این محتوا
   جایگزین کنید (USERNAME را عوض کنید):

       import sys, os
       sys.path.insert(0, "/home/USERNAME/game/worldwar-game")
       sys.path.insert(0, "/home/USERNAME/game")
       os.environ["PAW_PROXY"] = "1"          # فقط برای حساب رایگان
       os.environ["PUBLIC_BASE_URL"] = "https://USERNAME.pythonanywhere.com"
       from webapp.paw_wsgi import application

۴) در تب **Web**: دکمهٔ **Reload** را بزنید.

۵) یک‌بار وبهوک را ثبت کنید (Bash console):

       cd /home/USERNAME/game/worldwar-game
       python3 paw_start.py --base-url https://USERNAME.pythonanywhere.com

   یا از مرورگر، آدرس زیر را باز کنید (اگر `WEBHOOK_SECRET` تنظیم نشده باشد):

       https://USERNAME.pythonanywhere.com/setup

   بعد از آن ربات‌ها فعال‌اند: در تلگرام `/start` بفرستید. 🎉

── نکات مهم ──────────────────────────────────────────────────────────────────
• «همیشه روشن» نیست: PythonAnywhere وب‌اپ رایگان را بعد از بی‌استفادگی می‌خوابانَد؛
  یک‌بار باز کردن آدرس سایت بیدارش می‌کند. آپدیت‌هایی که تلگرام در خواب سرویس
  می‌فرستد، ذخیره می‌شوند و بعد از بیدار شدن تحویل داده می‌شوند.
• منطق بازی (زمان‌بندها، درآمد دوره‌ای، انقلاب، نفت) در هر درخواست، حداکثر یک‌بار
  در دقیقه اجرا می‌شود — بنگر `run_due_tasks`.
• اگر حساب پلاس (Whitelist رفع‌شده) دارید، `PAW_PROXY=0` بگذارید.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# ─── مسیرها باید قبل از import پروژه تنظیم شوند ───
_HERE = Path(__file__).resolve()
WW_DIR = _HERE.parent.parent            # worldwar-game/
REPO_DIR = WW_DIR.parent                # ریشهٔ پروژه
for _p in (str(WW_DIR), str(REPO_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ─── پروکسی حساب رایگان PythonAnywhere (باید قبل از هر تماس شبکه‌ای ست شود) ───
PROXY_URL = "http://proxy.server:3128"


def _env_flag(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).strip().lower() in ("1", "true", "yes", "on")


def configure_environment() -> None:
    """تنظیم پروکسی، مسیر دیتابیس و آدرس عمومی (ایمن برای فراخوانی مکرر)."""
    if _env_flag("PAW_PROXY", "1" if "pythonanywhere" in os.getenv("PYTHONANYWHERE_DOMAIN", "")
                 else "0"):
        os.environ.setdefault("HTTP_PROXY", PROXY_URL)
        os.environ.setdefault("HTTPS_PROXY", PROXY_URL)
        os.environ.setdefault("http_proxy", PROXY_URL)
        os.environ.setdefault("https_proxy", PROXY_URL)
    os.environ.setdefault("DB_PATH", str(WW_DIR / "wwgame.db"))
    os.environ.setdefault("AUTOSTART_BOTS", "0")
    os.environ.setdefault("BOT_PROCESS_DISABLED", "1")
    # آدرس عمومی برای ثبت وبهوک و بازسازی آدرس‌ها
    if not os.getenv("PUBLIC_BASE_URL") and os.getenv("PYTHONANYWHERE_DOMAIN"):
        os.environ["PUBLIC_BASE_URL"] = f"https://{os.environ['PYTHONANYWHERE_DOMAIN']}"


configure_environment()

# ─── اگر pythonanywhere هستیم و aiogram از پروکسی استفاده نمی‌کند، پچ می‌کنیم ───
def _patch_aiohttp_proxy() -> None:
    if not os.getenv("HTTPS_PROXY"):
        return
    try:
        from aiohttp import ClientSession as _ClientSession
    except Exception:  # noqa: BLE001
        return
    if getattr(_ClientSession, "_paw_proxy_patched", False):
        return
    original_init = _ClientSession.__init__

    def _init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("trust_env") is None:
            kwargs["trust_env"] = True
        return original_init(self, *args, **kwargs)

    _ClientSession.__init__ = _init  # type: ignore[method-assign]
    _ClientSession._paw_proxy_patched = True  # type: ignore[attr-defined]


_patch_aiohttp_proxy()

import asyncio  # noqa: E402
import threading  # noqa: E402

log = logging.getLogger("paw")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


# ─────────────────────────── حلقهٔ asyncio دائمی ───────────────────────────
# WSGI سنکرون است؛ برای هر درخواست با run_coroutine_threadsafe روی یک loop
# دائمی اجرا می‌کنیم تا Bot/Dispatcher بین درخواست‌ها پایدار بمانند.

class LoopRunner:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self.loop and self.loop.is_running():
                return self.loop
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self._run, name="paw-loop", daemon=True)
            self.thread.start()
            return self.loop

    def _run(self) -> None:
        assert self.loop is not None
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro, timeout: float = 55.0) -> Any:
        loop = self.start()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)


runner = LoopRunner()


# ─────────────────────────── ساخت بات‌ها و دیسپچرها ───────────────────────────

class BotRegistry:
    """نگهداری Bot/Dispatcher زنده بین درخواست‌های WSGI."""

    def __init__(self) -> None:
        self.game_bot = None
        self.game_dp = None
        self.admin_bot = None
        self.admin_dp = None
        self._ready = False

    async def _build(self) -> None:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from core import config as cfg
        from core.db import init_db

        await init_db()
        if cfg.GAME_BOT_TOKEN:
            from gamebot.main import create_dispatcher as create_game_dp
            self.game_bot = Bot(cfg.GAME_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            self.game_dp = create_game_dp()
        if cfg.ADMIN_BOT_TOKEN:
            from adminbot.main import create_dispatcher as create_admin_dp
            self.admin_bot = Bot(cfg.ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            self.admin_dp = create_admin_dp()
        self._ready = True
        log.info("✅ ربات‌ها آماده‌اند (game=%s, admin=%s)",
                 bool(self.game_bot), bool(self.admin_bot))

    async def ensure(self) -> None:
        if not self._ready:
            await self._build()

    @property
    def ready(self) -> bool:
        return self._ready


registry = BotRegistry()


async def feed(kind: str, payload: dict[str, Any]) -> bool:
    """تحویل یک آپدیت تلگرام به دیسپچر مربوطه."""
    from aiogram.types import Update

    await registry.ensure()
    if kind == "game":
        bot, dp = registry.game_bot, registry.game_dp
    else:
        bot, dp = registry.admin_bot, registry.admin_dp
    if bot is None or dp is None:
        log.warning("آپدیت %s رسید اما رباتش تنظیم نشده است", kind)
        return False
    update = Update.model_validate(payload, context={"bot": bot})
    await dp.feed_update(bot, update)
    return True


async def deliver(kind: str, updates: list[dict[str, Any]]) -> int:
    done = 0
    for payload in updates:
        try:
            if await feed(kind, payload):
                done += 1
        except Exception:  # noqa: BLE001
            log.exception("خطا در پردازش آپدیت %s", kind)
    return done


# ─────────────────────────── کارهای دوره‌ای (بدون پس‌زمینه) ───────────────────────────
# روی هاست‌های WSGI نمی‌توان ترد/پروسهٔ دائمی داشت؛ بنابراین زمان‌بندها را در هر
# درخواست، حداکثر یک‌بار در بازهٔ مشخص، اجرا می‌کنیم.

async def run_due_tasks() -> dict[str, Any]:
    # اتصال دیتابیس و ساخت ربات‌ها باید اول انجام شود
    await registry.ensure()
    from core.db import db

    row = await db.fetchone("SELECT value FROM settings WHERE key='paw_last_tick'")
    last = float((row or {}).get("value") or 0)
    now = time.time()
    result = {"ran": False, "secondsSinceLast": int(now - last) if last else None}
    if last and now - last < 55:
        return result

    await db.execute(
        "INSERT INTO settings(key, value) VALUES('paw_last_tick', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(now),))
    result["ran"] = True

    from core.db import get_setting
    from core.scheduler import (enrich_settle_task, income_tick, main_currency_recompute,
                                rescue_task, season_votes_task)

    tasks: list[str] = []
    bot = registry.game_bot

    # درآمد دوره‌ای هر `income_interval_minutes` دقیقه
    interval = max(5, int(float(await get_setting("income_interval_minutes", "30") or 30)))
    row = await db.fetchone("SELECT value FROM settings WHERE key='paw_last_income'")
    last_income = float((row or {}).get("value") or 0)
    if not last_income or now - last_income >= interval * 60:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES('paw_last_income', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(now),))
        if bot is not None:
            try:
                await income_tick(bot)
                tasks.append("income")
            except Exception:  # noqa: BLE001
                log.exception("income tick failed")

    if bot is not None:
        for name, fn in (("settle_votes", _settle_votes), ("seasons", season_votes_task),
                         ("rescue", rescue_task), ("currency", main_currency_recompute),
                         ("oil", _oil_tick), ("revolution", _revolution_tick),
                         ("enrichment", enrich_settle_task), ("nuke", _nuke_settle)):
            try:
                await fn(bot)
                tasks.append(name)
            except Exception:  # noqa: BLE001
                log.exception("%s failed", name)
    result["tasks"] = tasks
    return result


async def _nuke_settle(bot) -> None:
    """☢️ تحویل کلاهک‌های هسته‌ای آماده (روی PythonAnywhere زمان‌بند دائمی نداریم)."""
    from core import nuke as nuke_mod
    await nuke_mod.settle_all(bot)


async def _settle_votes(bot) -> None:  # type: ignore[no-untyped-def]
    from gamebot.handlers.war import settle_votes
    await settle_votes(bot)


async def _oil_tick(bot) -> None:  # type: ignore[no-untyped-def]
    from core import oil as oil_mod
    await oil_mod.auto_sell_tick(bot)


async def _revolution_tick(bot) -> None:  # type: ignore[no-untyped-def]
    from core.politics import revolution_tick
    await revolution_tick(bot)


# ─────────────────────────── امنیت و ابزار آپدیت ───────────────────────────

def _secret_ok(environ: dict[str, Any], expected: str | None = None) -> bool:
    """بررسی هدر X-Telegram-Bot-Api-Secret-Token.

    ⛔️ اگر کلیدی تنظیم نشده باشد، **هیچ** آپدیتی پذیرفته نمی‌شود؛ پیش‌تر در این
    حالت بررسی انجام نمی‌شد و هر کسی می‌توانست آپدیت جعلی بفرستد.
    """
    from core.security import secret_matches

    if expected is None:
        from core import config as cfg
        expected = os.getenv("WEBHOOK_SECRET") or cfg.WEBHOOK_SECRET
    key = "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"
    got = environ.get(key) or environ.get(key.lower()) or ""
    return secret_matches(expected or "", str(got))


_SECRET_CACHE: dict[str, str] = {}


def _ensure_secret() -> str:
    """کلید وبهوک را (از .env یا دیتابیس) تضمین می‌کند؛ اگر نبود می‌سازد."""
    from core import security as sec
    cached = _SECRET_CACHE.get("value")
    if cached:
        return cached
    try:
        secret, _fresh = runner.run(sec.ensure_webhook_secret(), timeout=30)
        _SECRET_CACHE["value"] = secret
        return secret
    except Exception:
        log.exception("آماده‌سازی کلید وبهوک ناموفق بود")
        from core import config as cfg
        return os.getenv("WEBHOOK_SECRET") or cfg.WEBHOOK_SECRET


def _json(environ: dict[str, Any]) -> dict[str, Any]:
    length = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ["wsgi.input"].read(length) if length else b""
    if not body:
        return {}
    try:
        data = json.loads(body.decode("utf-8"))
        return data if isinstance(data, dict) else {"value": data}
    except Exception:  # noqa: BLE001
        return {}


def _base_url(environ: dict[str, Any]) -> str:
    explicit = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    domain = os.getenv("PYTHONANYWHERE_DOMAIN")
    if domain:
        return f"https://{domain}"
    host = environ.get("HTTP_HOST") or "localhost"
    return f"https://{host}"


def _set_webhooks(base: str) -> dict[str, Any]:
    from core import config as cfg

    secret = _ensure_secret()
    allowed = ["message", "callback_query", "inline_query", "channel_post",
               "chat_member", "my_chat_member"]
    out: dict[str, Any] = {}
    for kind, token in (("game", cfg.GAME_BOT_TOKEN), ("admin", cfg.ADMIN_BOT_TOKEN)):
        if not token:
            out[kind] = {"ok": False, "error": "توکن تنظیم نشده"}
            continue
        url = f"{base}/webhook/{kind}"
        payload: dict[str, Any] = {"url": url, "drop_pending_updates": False,
                                   "allowed_updates": allowed}
        if secret:
            payload["secret_token"] = secret
        out[kind] = {"ok": token.startswith(tuple("0123456789")), "url": url}
        try:
            from webapp.config_service import telegram_api
            res = telegram_api(token, "setWebhook", payload)
            out[kind] = {"ok": bool(res.get("ok")), "url": url,
                         "description": res.get("description")}
        except Exception as exc:  # noqa: BLE001
            out[kind] = {"ok": False, "url": url, "error": str(exc)}
    return out


# ─────────────────────────── اپلیکیشن WSGI ───────────────────────────

def application(environ: dict[str, Any], start_response):  # noqa: ANN001
    """WSGI app: مسیرهای سلامت، وبهوک، تنظیم وبهوک و پنل خواندنی."""
    path = (environ.get("PATH_INFO") or "/").rstrip("/") or "/"
    method = (environ.get("REQUEST_METHOD") or "GET").upper()

    def respond(status: str, body: Any, ctype: str = "application/json; charset=utf-8"):
        data = (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).encode("utf-8")
        start_response(status, [("Content-Type", ctype), ("Content-Length", str(len(data)))])
        return [data]

    try:
        # ── سلامت سرویس ──
        if path in ("/", "/health", "/api/health"):
            if path != "/" or not registry.ready:
                try:
                    runner.run(registry.ensure(), timeout=40)
                except Exception:  # noqa: BLE001
                    log.exception("آماده‌سازی ربات‌ها ناموفق بود")
            info = {
                "status": "ok",
                "service": "worldwar-bots-paw",
                "mode": "webhook",
                "runtime": "python",
                "proxy": bool(os.getenv("HTTPS_PROXY")),
                "publicBaseUrl": _base_url(environ),
                "botsReady": registry.ready,
                "bots": {"game": registry.game_bot is not None,
                         "admin": registry.admin_bot is not None},
                "webhookPaths": {"game": "/webhook/game", "admin": "/webhook/admin"},
                "setupPaths": ["/setup", "/info"],
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if path != "/":
                # درخواست سلامت، کارهای دوره‌ای را هم اجرا می‌کند (به‌جای زمان‌بند)
                info["tasks"] = runner.run(run_due_tasks())
            return respond("200 OK", info)

        # ── ثبت وبهوک (فقط با کلید معتبر، تا کسی وبهوک را به سرور خودش نبرد) ──
        if path in ("/setup", "/api/webhook/set"):
            secret_now = _ensure_secret()
            if not _secret_ok(environ, secret_now):
                return respond("403 Forbidden", {"ok": False, "error": "invalid secret token"})
            base = _base_url(environ)
            result = _set_webhooks(base)
            return respond("200 OK", {"success": any(v.get("ok") for v in result.values()),
                                      "baseUrl": base, "results": result})

        # ── اطلاعات وبهوک ──
        if path in ("/info", "/api/webhook/status"):
            from core import config as cfg
            from webapp.config_service import telegram_api
            out: dict[str, Any] = {}
            for kind, token in (("game", cfg.GAME_BOT_TOKEN), ("admin", cfg.ADMIN_BOT_TOKEN)):
                if not token:
                    out[kind] = {"configured": False}
                    continue
                res = telegram_api(token, "getWebhookInfo")
                r = res.get("result") or {}
                out[kind] = {"configured": True, "ok": bool(res.get("ok")), "url": r.get("url", ""),
                             "pendingUpdates": r.get("pending_update_count"),
                             "lastError": r.get("last_error_message")}
            return respond("200 OK", out)

        # ── تنظیم دستورهای منو (اختیاری) ──
        if path == "/setcommands":
            from core import config as cfg
            from webapp.config_service import telegram_api
            commands = [{"command": "start", "description": "🚀 شروع بازی"},
                        {"command": "cancel", "description": "❌ انصراف"},
                        {"command": "panel", "description": "🎛 پنل ادمین"}]
            res = {k: telegram_api(t, "setMyCommands", {"commands": commands}).get("ok")
                   for k, t in (("game", cfg.GAME_BOT_TOKEN), ("admin", cfg.ADMIN_BOT_TOKEN)) if t}
            return respond("200 OK", {"success": True, "results": res})

        # ── دریافت آپدیت‌های تلگرام ──
        if path in ("/webhook/game", "/webhook/admin") or path.startswith("/webhook/"):
            if method != "POST":
                return respond("200 OK", {"ok": True, "hint": "این مسیر فقط POST می‌پذیرد"})
            if not _secret_ok(environ, _ensure_secret()):
                return respond("403 Forbidden", {"ok": False, "error": "invalid secret token"})
            kind = "admin" if path.endswith("admin") else "game"
            payload = _json(environ)
            if not payload:
                return respond("200 OK", {"ok": True, "empty": True})
            ok = runner.run(feed(kind, payload))
            # کارهای دوره‌ای را در فرصت مناسب هم اجرا می‌کنیم (سبک و با محدودیت زمانی)
            try:
                runner.run(run_due_tasks(), timeout=20)
            except Exception:  # noqa: BLE001
                log.exception("due tasks failed")
            return respond("200 OK", {"ok": True, "handled": ok})

        # ── پنل وب فقط‌خواندنی (اختیاری) ──
        if path in ("/panel", "/dashboard"):
            html = _panel_html()
            return respond("200 OK", html, "text/html; charset=utf-8")

        return respond("404 Not Found", {"ok": False, "error": "not found", "path": path})
    except Exception as exc:  # noqa: BLE001
        log.error("خطای WSGI: %s\n%s", exc, traceback.format_exc())
        # همیشه ۲۰۰ برمی‌گردانیم تا تلگرام آپدیت را بی‌پایان دوباره نفرستد
        return respond("200 OK", {"ok": False, "error": str(exc)})


def _panel_html() -> str:
    """یک صفحهٔ وضعیت سبک (روی PythonAnywhere سرور وب دائمی نداریم)."""
    return """<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>پنل فرماندهی — وضعیت ربات‌ها</title>
<style>body{font-family:system-ui,Tahoma,sans-serif;background:#020617;color:#e2e8f0;padding:32px;line-height:2}
a{color:#38bdf8} .box{background:#0f172a;border:1px solid #1e293b;border-radius:14px;padding:20px;max-width:760px}
h1{font-size:20px}</style></head><body><div class="box">
<h1>⚔️ پنل فرماندهی — حالت Webhook روی PythonAnywhere</h1>
<p>این سرویس با Webhook کار می‌کند و ربات‌ها فعال هستند. وضعیت زنده:</p>
<ul>
  <li><a href="/health">/health</a> — وضعیت سرویس، آمادگی ربات‌ها و اجرای کارهای دوره‌ای</li>
  <li><a href="/info">/info</a> — اطلاعات وبهوک هر دو ربات از تلگرام</li>
  <li><a href="/setup">/setup</a> — ثبت/به‌روزرسانی وبهوک روی همین دامنه</li>
  <li><a href="/setcommands">/setcommands</a> — ساخت منوی دستورهای تلگرام</li>
</ul>
<p>برای پنل کامل مدیریت (React) سرور پایتونی <code>web.py</code> را روی یک VPS اجرا کنید؛
روی پلن رایگان PythonAnywhere سرور همیشه‌روشن مجاز نیست.</p>
</div></body></html>"""

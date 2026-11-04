"""اجرای ربات‌ها در حالت Webhook + سرور سلامت (/health) و پینگ خودکار.

چرا وبهوک؟
  در حالت polling، ربات باید همیشه به تلگرام وصل باشد و اگر سرویس خواب برود پیام‌ها
  گم می‌شوند. با وبهوک، خودِ تلگرام هر پیام را به این آدرس POST می‌کند و سرویس با
  یک پینگ داخلی هر ۱۰ دقیقه بیدار می‌ماند.

مسیرهای سرویس:
  GET  /health                 وضعیت سرویس، ربات‌ها و زمان آخرین به‌روزرسانی
  POST /webhook/game           دریافت آپدیت‌های ربات بازی از تلگرام
  POST /webhook/admin          دریافت آپدیت‌های ربات ادمین از تلگرام
  GET  /webhook/info           اطلاعات وبهوک هر دو ربات از تلگرام
  POST /webhook/set            ثبت وبهوک هر دو ربات روی آدرس عمومی
  POST /webhook/delete         حذف وبهوک (بازگشت به polling)

دستورهای خط فرمان:
  python3 run_webhook.py                          # اجرای سرویس وبهوک
  python3 run_webhook.py --set-webhook https://my.app
  python3 run_webhook.py --info
  python3 run_webhook.py --delete-webhook
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from typing import Any

from aiohttp import ClientSession, web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update

from core.config import (ADMIN_BOT_TOKEN, GAME_BOT_TOKEN, KEEPALIVE_MINUTES,
                         PUBLIC_BASE_URL, WEBHOOK_HOST, WEBHOOK_PORT,
                         WEBHOOK_SECRET, check_tokens)
from core.db import db, init_db

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("webhook")

STARTED_AT = time.time()
STATS = {
    "game": {"updates": 0, "last_update": None, "errors": 0},
    "admin": {"updates": 0, "last_update": None, "errors": 0},
    "keepalive": {"count": 0, "last_ping": None, "last_ok": None},
}


# ─────────────────────────── ساخت برنامه ───────────────────────────


def create_app(game_dp: Dispatcher | None = None, game_bot: Bot | None = None,
               admin_dp: Dispatcher | None = None, admin_bot: Bot | None = None,
               secret: str = "", base_url: str = "") -> web.Application:
    """برنامه aiohttp سرویس وبهوک (قابل تست با aiohttp.test_utils)."""
    app = web.Application(client_max_size=8 * 1024 * 1024)
    app["bots"] = {"game": game_bot, "admin": admin_bot}
    app["dps"] = {"game": game_dp, "admin": admin_dp}
    app["secret"] = secret if secret is not None else WEBHOOK_SECRET
    app["base_url"] = (base_url or PUBLIC_BASE_URL).rstrip("/")

    app.router.add_route("GET", "/health", handle_health)
    app.router.add_route("HEAD", "/health", handle_health)
    app.router.add_route("GET", "/api/health", handle_health)
    app.router.add_route("POST", "/webhook/game", make_update_handler("game"))
    app.router.add_route("POST", "/webhook/admin", make_update_handler("admin"))
    app.router.add_route("GET", "/webhook/info", handle_webhook_info)
    app.router.add_route("POST", "/webhook/set", handle_webhook_set)
    app.router.add_route("POST", "/webhook/delete", handle_webhook_delete)
    app.router.add_route("GET", "/", handle_root)
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app


async def _on_startup(app: web.Application) -> None:
    # اجرای هوک‌های startup هر دیسپچر (زمان‌بند درآمد/رأی‌گیری، ثبت دستورات تلگرام و ...)
    for kind, dp in app["dps"].items():
        bot = app["bots"].get(kind)
        if dp is None or bot is None:
            continue
        try:
            await dp.emit_startup(bot=bot)
            log.info("✅ هوک‌های شروع %s اجرا شد", kind)
        except Exception as exc:
            log.exception("خطا در startup %s: %s", kind, exc)
    app["start_keepalive"] = asyncio.create_task(keepalive_loop(app))


async def _on_cleanup(app: web.Application) -> None:
    task = app.get("start_keepalive")
    if task:
        task.cancel()
    for kind, dp in app["dps"].items():
        bot = app["bots"].get(kind)
        if dp is None or bot is None:
            continue
        try:
            await dp.emit_shutdown(bot=bot)
        except Exception:
            pass
    for bot in app["bots"].values():
        if bot is not None:
            try:
                await bot.session.close()
            except Exception:
                pass
    try:
        await db.close()
    except Exception:
        pass


# ─────────────────────────── مسیرها ───────────────────────────


async def handle_root(request: web.Request) -> web.Response:
    return web.json_response({
        "service": "World War Telegram bots (webhook mode)",
        "health": "/health",
        "webhooks": ["/webhook/game", "/webhook/admin"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


async def handle_health(request: web.Request) -> web.Response:
    """وضعیت سلامت سرویس — هم برای مانیتورینگ و هم برای پینگ بیدارباش."""
    bots = request.app["bots"]
    body = {
        "status": "ok",
        "service": "worldwar-bots",
        "mode": "webhook",
        "uptime": int(time.time() - STARTED_AT),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bots": {
            "game": {"configured": bots.get("game") is not None, **STATS["game"]},
            "admin": {"configured": bots.get("admin") is not None, **STATS["admin"]},
        },
        "webhook": {
            "base_url": request.app["base_url"] or None,
            "paths": {"game": "/webhook/game", "admin": "/webhook/admin"},
            "secret_set": bool(request.app["secret"]),
        },
        "keepalive": {"interval_minutes": KEEPALIVE_MINUTES, **STATS["keepalive"]},
        "db": _db_file_info(),
    }
    return web.json_response(body)


def make_update_handler(kind: str):
    """سازنده هندلر POST وبهوک برای هر ربات."""

    async def handler(request: web.Request) -> web.Response:
        secret = request.app["secret"]
        if secret:
            got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if got != secret:
                log.warning("وبهوک %s با کلید نامعتبر رد شد", kind)
                return web.json_response({"ok": False, "error": "invalid secret"}, status=403)
        dp = request.app["dps"].get(kind)
        bot = request.app["bots"].get(kind)
        if dp is None or bot is None:
            return web.json_response({"ok": False, "error": f"{kind} bot is not configured"}, status=503)
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)
        try:
            update = Update.model_validate(payload, context={"bot": bot})
        except Exception as exc:
            STATS[kind]["errors"] += 1
            log.warning("آپدیت نامعتبر برای %s: %s", kind, exc)
            return web.json_response({"ok": False, "error": "invalid update"}, status=400)
        try:
            await dp.feed_update(bot, update)
            STATS[kind]["updates"] += 1
            STATS[kind]["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        except Exception as exc:  # همیشه 200 بده تا تلگرام دوباره تلاش نکند
            STATS[kind]["errors"] += 1
            log.exception("خطا در پردازش آپدیت %s: %s", kind, exc)
        return web.json_response({"ok": True})

    return handler


async def handle_webhook_info(request: web.Request) -> web.Response:
    out: dict[str, Any] = {}
    for kind, bot in request.app["bots"].items():
        if bot is None:
            out[kind] = {"configured": False}
            continue
        try:
            info = await bot.get_webhook_info()
            out[kind] = {
                "configured": True,
                "url": info.url,
                "pending_updates": info.pending_update_count,
                "last_error": info.last_error_message,
                "last_error_at": info.last_error_date.isoformat() if info.last_error_date else None,
            }
        except Exception as exc:
            out[kind] = {"configured": True, "error": str(exc)}
    return web.json_response(out)


def _expected_base(request: web.Request) -> str:
    base = request.app["base_url"]
    if base:
        return base
    proto = request.headers.get("X-Forwarded-Proto") or request.scheme
    host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host")
    return f"{proto}://{host}".rstrip("/") if host else ""


async def handle_webhook_set(request: web.Request) -> web.Response:
    base = _expected_base(request)
    if not base:
        return web.json_response(
            {"ok": False, "error": "WEBHOOK_BASE_URL تنظیم نشده و آدرس عمومی مشخص نیست"}, status=400)
    results = {}
    for kind, bot in request.app["bots"].items():
        if bot is None:
            results[kind] = {"ok": False, "error": "not configured"}
            continue
        url = f"{base}/webhook/{kind}"
        try:
            await bot.set_webhook(
                url,
                secret_token=request.app["secret"] or None,
                drop_pending_updates=False,
                allowed_updates=["message", "callback_query", "inline_query",
                                 "channel_post", "chat_member", "my_chat_member"],
            )
            results[kind] = {"ok": True, "url": url}
        except Exception as exc:
            results[kind] = {"ok": False, "error": str(exc)}
    request.app["base_url"] = base
    return web.json_response({"ok": all(r.get("ok") for r in results.values()), "results": results})


async def handle_webhook_delete(request: web.Request) -> web.Response:
    results = {}
    for kind, bot in request.app["bots"].items():
        if bot is None:
            results[kind] = {"ok": False, "error": "not configured"}
            continue
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            results[kind] = {"ok": True}
        except Exception as exc:
            results[kind] = {"ok": False, "error": str(exc)}
    return web.json_response({"ok": all(r.get("ok") for r in results.values()), "results": results})


# ─────────────────────────── پینگ بیدارباش ───────────────────────────


async def ping_once(base: str) -> bool:
    """یک درخواست فیک به /health سرویس → True اگر پاسخ ۲۰۰ باشد."""
    ok = False
    try:
        async with ClientSession() as session:
            async with session.get(f"{base.rstrip('/')}/health?ping=1",
                                   headers={"X-Keepalive": "1"},
                                   timeout=aiohttp_timeout()) as resp:
                ok = resp.status == 200
    except Exception as exc:
        log.warning("پینگ سلامت ناموفق (%s): %s", base, exc)
        ok = False
    STATS["keepalive"]["count"] += 1
    STATS["keepalive"]["last_ping"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    STATS["keepalive"]["last_ok"] = ok
    return ok


def aiohttp_timeout():
    from aiohttp import ClientTimeout
    return ClientTimeout(total=15)


def keepalive_base(app: web.Application) -> str:
    return app.get("base_url") or f"http://127.0.0.1:{os.getenv('PORT', WEBHOOK_PORT)}"


async def keepalive_loop(app: web.Application) -> None:
    """هر KEEPALIVE_MINUTES دقیقه یک درخواست فیک به /health می‌زند تا سرویس خواب نرود."""
    interval = max(1, KEEPALIVE_MINUTES) * 60
    await asyncio.sleep(min(30, interval))  # شروع آرام
    while True:
        await ping_once(keepalive_base(app))
        await asyncio.sleep(interval)


# ─────────────────────────── اجرای واقعی ───────────────────────────


def _db_file_info() -> dict:
    try:
        from core.config import DB_PATH
        size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        return {"path": DB_PATH, "size": size}
    except Exception:
        return {}


def build_bots() -> tuple[Bot | None, Dispatcher | None, Bot | None, Dispatcher | None]:
    """ساخت بات‌ها و دیسپچرها برای حالت وبهوک."""
    from adminbot.main import create_dispatcher as create_admin_dp
    from gamebot.main import create_dispatcher as create_game_dp

    game_bot = game_dp = admin_bot = admin_dp = None
    if GAME_BOT_TOKEN:
        game_bot = Bot(GAME_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        game_dp = create_game_dp()
    else:
        log.warning("توکن GAME_BOT_TOKEN تنظیم نشده است.")
    if ADMIN_BOT_TOKEN:
        admin_bot = Bot(ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        admin_dp = create_admin_dp()
    else:
        log.warning("توکن ADMIN_BOT_TOKEN تنظیم نشده است.")
    return game_bot, game_dp, admin_bot, admin_dp


async def set_webhook_cli(base_url: str, delete: bool = False) -> None:
    await init_db()
    game_bot, _game_dp, admin_bot, _admin_dp = build_bots()
    base = base_url.rstrip("/")
    for kind, bot in (("game", game_bot), ("admin", admin_bot)):
        if bot is None:
            print(f"⚠️ ربات {kind} توکن ندارد — رد شد")
            continue
        try:
            if delete:
                await bot.delete_webhook(drop_pending_updates=False)
                print(f"🗑 وبهوک ربات {kind} حذف شد")
            else:
                await bot.set_webhook(f"{base}/webhook/{kind}",
                                      secret_token=WEBHOOK_SECRET or None,
                                      drop_pending_updates=False,
                                      allowed_updates=["message", "callback_query", "inline_query",
                                                       "channel_post", "chat_member", "my_chat_member"])
                print(f"✅ وبهوک ربات {kind}: {base}/webhook/{kind}")
        except Exception as exc:
            print(f"❌ خطا در ربات {kind}: {exc}")
        finally:
            try:
                await bot.session.close()
            except Exception:
                pass
    await db.close()


async def main_async(host: str, port: int) -> None:
    check_tokens(admin=False)
    await init_db()
    game_bot, game_dp, admin_bot, admin_dp = build_bots()
    app = create_app(game_dp, game_bot, admin_dp, admin_bot,
                     secret=WEBHOOK_SECRET, base_url=PUBLIC_BASE_URL)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("🌐 سرویس وبهوک روی http://%s:%s — سلامت: /health", host, port)
    if PUBLIC_BASE_URL:
        log.info("🔗 آدرس عمومی: %s/webhook/game و %s/webhook/admin", PUBLIC_BASE_URL, PUBLIC_BASE_URL)
    else:
        log.warning("WEBHOOK_BASE_URL تنظیم نشده — برای ثبت وبهوک، POST /webhook/set یا --set-webhook")
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description="اجرای ربات‌های جنگ جهانی در حالت Webhook")
    parser.add_argument("--set-webhook", metavar="BASE_URL",
                        help="ثبت وبهوک روی این آدرس عمومی و خروج")
    parser.add_argument("--delete-webhook", action="store_true", help="حذف وبهوک و بازگشت به polling")
    parser.add_argument("--host", default=WEBHOOK_HOST)
    parser.add_argument("--port", type=int, default=WEBHOOK_PORT)
    args = parser.parse_args()

    if args.set_webhook:
        asyncio.run(set_webhook_cli(args.set_webhook))
        return
    if args.delete_webhook:
        asyncio.run(set_webhook_cli("", delete=True))
        return

    try:
        asyncio.run(main_async(args.host, args.port))
    except KeyboardInterrupt:
        log.info("سرویس وبهوک متوقف شد.")


if __name__ == "__main__":
    main()

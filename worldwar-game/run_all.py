"""اجرای هم‌زمان پنل فرماندهی وب (پایتون) و ربات‌های تلگرام.

حالت‌های اجرا:
    python3 run_all.py                # پنل وب + ربات‌ها (ربات‌ها به‌صورت پروسهٔ فرزند)
    python3 run_all.py --no-web       # فقط ربات‌ها در همین پروسه (بدون پنل وب)
    python3 run_all.py --web-only     # فقط پنل وب (بدون اجرای خودکار ربات‌ها)
    python3 run_all.py --no-autostart # پنل وب، اما ربات‌ها خودکار اجرا نشوند

ربات‌ها در یک پروسهٔ جدا (همان `run_all.py --no-web` یا `run_webhook.py`) اجرا
می‌شوند تا توقف/ری‌استارت آن‌ها از پنل وب، خود سرور وب را از کار نیندازد.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from adminbot.main import create_dispatcher as create_admin_dp
from core import config as cfg
from core.config import ADMIN_BOT_TOKEN, GAME_BOT_TOKEN
from core.db import init_db
from gamebot.main import create_dispatcher as create_game_dp
from webapp.process_manager import process_manager

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("main")

stop_event = asyncio.Event()


async def poll_with_retry(dp: Dispatcher, bot: Bot, name: str) -> None:
    while not stop_event.is_set():
        try:
            me = await bot.get_me()
            log.info("🤖 %s آنلاین شد: @%s", name, me.username)
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except Exception as we:  # noqa: BLE001
                log.warning("عدم امکان بررسی وبهوک %s: %s", name, we)
            await dp.start_polling(bot, handle_signals=False)
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            if stop_event.is_set():
                break
            log.error("خطا در %s: %s — تلاش مجدد تا ۵ ثانیه دیگر...", name, e)
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break


async def run_bots_in_process() -> None:
    """اجرای ربات بازی و ربات ادمین در همین پروسه (حالت polling)."""
    await init_db()
    from core.keepalive import start_keepalive
    start_keepalive()

    bots: list[Bot] = []
    dps: list[Dispatcher] = []
    tasks: list[asyncio.Task] = []

    if GAME_BOT_TOKEN:
        game_bot = Bot(GAME_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        game_dp = create_game_dp()
        bots.append(game_bot)
        dps.append(game_dp)
        tasks.append(asyncio.create_task(poll_with_retry(game_dp, game_bot, "ربات بازی")))
    else:
        log.warning("توکن GAME_BOT_TOKEN تنظیم نشده است.")

    if ADMIN_BOT_TOKEN:
        admin_bot = Bot(ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        admin_dp = create_admin_dp()
        bots.append(admin_bot)
        dps.append(admin_dp)
        tasks.append(asyncio.create_task(poll_with_retry(admin_dp, admin_bot, "ربات ادمین")))
    else:
        log.warning("توکن ADMIN_BOT_TOKEN تنظیم نشده است.")

    async def graceful_shutdown() -> None:
        log.info("سیگنال توقف دریافت شد — در حال بستن امن اتصالات...")
        stop_event.set()
        for dp in dps:
            try:
                await dp.stop_polling()
            except Exception:  # noqa: BLE001
                pass
        for t in tasks:
            t.cancel()
        for b in bots:
            try:
                await b.session.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            from core.db import db
            await db.close()
        except Exception:  # noqa: BLE001
            pass
        log.info("پایان امن فرآیند بدون آسیب به داده‌های بازیکنان.")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(graceful_shutdown()))
        except (NotImplementedError, RuntimeError):
            pass

    if not tasks:
        log.error("هیچ توکنی برای راه‌اندازی ربات‌ها تنظیم نشده است.")
        return
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


async def run_panel(autostart: bool = True) -> None:
    """اجرای سرور وب پنل فرماندهی (و در صورت autostart، اجرای ربات‌ها به‌صورت فرزند)."""
    await init_db()
    from aiohttp import web
    from webapp.server import create_app

    app = create_app(autostart=autostart)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, cfg.WEB_HOST, cfg.WEB_PORT)
    await site.start()
    log.info("🌐 پنل فرماندهی روی http://%s:%s (پایتون/aiohttp)", cfg.WEB_HOST, cfg.WEB_PORT)
    log.info("   سلامت سرویس: /health  |  توکن‌ها و آیدی ادمین: /api/secrets")

    if autostart:
        await asyncio.get_running_loop().run_in_executor(None, process_manager.autostart)

    stop = asyncio.Event()

    def _shutdown() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        await stop.wait()
    finally:
        log.info("در حال بستن پنل و پروسهٔ ربات‌ها...")
        await asyncio.get_running_loop().run_in_executor(None, process_manager.stop)
        await runner.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description="اجرای ربات‌ها و پنل وب بازی جنگ جهانی (پایتون)")
    parser.add_argument("--no-web", action="store_true", help="بدون پنل وب؛ فقط ربات‌ها در همین پروسه")
    parser.add_argument("--web-only", action="store_true", help="فقط پنل وب؛ ربات‌ها خودکار اجرا نشوند")
    parser.add_argument("--no-autostart", action="store_true", help="ربات‌ها خودکار اجرا نشوند")
    parser.add_argument("--host", default=None, help="آدرس اتصال سرور وب (پیش‌فرض 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="پورت سرور وب (پیش‌فرض 3000)")
    args = parser.parse_args()

    if args.host:
        cfg.WEB_HOST = args.host
    if args.port:
        cfg.WEB_PORT = args.port

    if args.no_web:
        asyncio.run(run_bots_in_process())
        return
    autostart = not (args.web_only or args.no_autostart)
    if args.no_autostart:
        cfg.BOTS_AUTOSTART = False
        import os
        os.environ["AUTOSTART_BOTS"] = "0"
    asyncio.run(run_panel(autostart=autostart))


if __name__ == "__main__":
    sys.exit(main())

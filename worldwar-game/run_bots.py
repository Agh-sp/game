#!/usr/bin/env python3
"""اجرای فقط ربات‌های تلگرام (بدون سرور وب) — همان پروسه‌ای که پنل وب مدیریتش می‌کند.

این فایل عمداً هیچ سرور وبی بالا نمی‌آورد و هیچ پروسهٔ فرزندی نمی‌سازد، تا اگر پنل
وب آن را اجرا/ری‌استارت کند، هرگز روی پورت پنل با هم تداخل نکنند.

اجرا:
    python3 run_bots.py     # ربات بازی + ربات ادمین در حالت polling
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys


def _purge_stale_bytecode() -> int:
    """حذف فایل‌های .pyc کهنه تا کد قدیمی کش نشود (باگ «هنوز worldwarFIRE می‌بینم»)."""
    import pathlib
    import shutil
    removed = 0
    root = pathlib.Path(__file__).resolve().parent
    for cache in root.rglob("__pycache__"):
        if any(part in {".venv", "venv", "site-packages"} for part in cache.parts):
            continue
        shutil.rmtree(cache, ignore_errors=True)
        removed += 1
    return removed


_PURGED = _purge_stale_bytecode()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from core import config as cfg
from core.config import ADMIN_BOT_TOKEN, GAME_BOT_TOKEN
from core.db import init_db

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("bots")

PID_FILE = os.getenv("BOT_PID_FILE", "/tmp/wwgame_bots.pid")
stop_event = asyncio.Event()
FAILS: dict[str, int] = {}


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
            FAILS[name] = FAILS.get(name, 0) + 1
            log.error("خطا در %s: %s — تلاش مجدد تا ۵ ثانیه دیگر...", name, e)
            if FAILS[name] == 3:
                log.error(
                    "🚫 %s سه بار نتوانست به api.telegram.org وصل شود.\n"
                    "   اگر «urllib» وصل می‌شود ولی این خطا تکرار می‌شود، فایروال یا "
                    "پروکسی شبکه جلوی TLS را گرفته است.\n"
                    "   راه‌حل:  python3 run_webhook.py  یا  python3 paw_start.py  "
                    "(حالت وبهوک، بدون اتصال خروجی)", name)
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break


def _write_pid() -> None:
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass


def _remove_pid() -> None:
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except OSError:
        pass


async def run() -> None:
    log.info("🧹 %d پوشهٔ بایت‌کد کهنه پاک شد (اجرای کد تازه)", _PURGED)

    # 🌐 عیب‌یابی خودکار مسیر شبکه (پروکسی/مستقیم/SSL) پیش از ساخت ربات‌ها
    if (os.getenv("NET_AUTOFIX", "1") or "1").strip() not in ("0", "false", "off"):
        try:
            from core import netdiag
            await netdiag.setup()
        except Exception as exc:  # noqa: BLE001
            log.warning("عیب‌یابی شبکه انجام نشد: %s", exc)

    await init_db()
    _write_pid()
    from core.keepalive import start_keepalive
    start_keepalive()

    bots: list[Bot] = []
    dps: list[Dispatcher] = []
    tasks: list[asyncio.Task] = []

    if GAME_BOT_TOKEN:
        from gamebot.main import create_dispatcher as create_game_dp
        from core.netdiag import make_bot
        game_bot = make_bot(GAME_BOT_TOKEN)
        game_dp = create_game_dp()
        bots.append(game_bot)
        dps.append(game_dp)
        tasks.append(asyncio.create_task(poll_with_retry(game_dp, game_bot, "ربات بازی")))
    else:
        log.warning("توکن GAME_BOT_TOKEN تنظیم نشده است.")

    if ADMIN_BOT_TOKEN:
        from adminbot.main import create_dispatcher as create_admin_dp
        from core.netdiag import make_bot
        admin_bot = make_bot(ADMIN_BOT_TOKEN)
        admin_dp = create_admin_dp()
        bots.append(admin_bot)
        dps.append(admin_dp)
        tasks.append(asyncio.create_task(poll_with_retry(admin_dp, admin_bot, "ربات ادمین")))
    else:
        log.warning("توکن ADMIN_BOT_TOKEN تنظیم نشده است.")

    async def graceful_shutdown() -> None:
        log.info("سیگنال توقف دریافت شد — بستن امن اتصالات ربات‌ها...")
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
        _remove_pid()
        log.info("ربات‌ها امن متوقف شدند.")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(graceful_shutdown()))
        except (NotImplementedError, RuntimeError):
            pass

    if not tasks:
        log.error("هیچ توکنی تنظیم نشده است — چیزی برای اجرا نیست.")
        _remove_pid()
        return
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        _remove_pid()


if __name__ == "__main__":
    cfg.BOTS_AUTOSTART = False  # این پروسه هرگز خودش ربات جدید اجرا نکند
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    sys.exit(0)

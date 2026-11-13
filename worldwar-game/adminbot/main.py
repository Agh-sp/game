"""ربات ادمین — ساخت Dispatcher و اجرا."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from adminbot.auth import AdminGate
from core.config import ADMIN_BOT_TOKEN, check_tokens
from core.db import init_db

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("adminbot")


async def _on_startup(bot: Bot) -> None:
    """زمان‌بند ربات ادمین و ثبت دستورات منوی تلگرام."""
    from aiogram.types import BotCommand
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🛡 ورود به پنل ادمین"),
            BotCommand(command="panel", description="📊 منوی اصلی مدیریت"),
            BotCommand(command="stats", description="📈 آمار کلی بازی"),
            BotCommand(command="u", description="👤 جستجو و مدیریت کاربر"),
            BotCommand(command="reset_wealth", description="🪙 ریست پول و سکه شاهی همه کاربران"),
            BotCommand(command="reset_players", description="🧨 ریست کل بازی (پاک‌سازی ۱۰۰٪ پیشرفت همه)"),
            BotCommand(command="bc", description="📢 ارسال همگانی"),
            BotCommand(command="receipts", description="🧾 بررسی فیش‌ها"),
            BotCommand(command="tickets", description="🎫 تیکت‌های پشتیبانی"),
            BotCommand(command="settings", description="⚙️ تنظیمات متغیرهای بازی"),
            BotCommand(command="channels", description="📡 کانال و گپ رسمی بازی"),
            BotCommand(command="testchannel", description="🧪 تست ارسال خبر به کانال"),
            BotCommand(command="cancel", description="❌ انصراف از عملیات"),
        ])
    except Exception as e:
        log.warning("تنظیم دستورات ادمین انجام نشد: %s", e)
    from core.scheduler import start_admin_scheduler
    start_admin_scheduler(bot)


async def _global_error_handler(event) -> bool:
    from aiogram.exceptions import TelegramBadRequest
    if isinstance(event.exception, TelegramBadRequest):
        msg = str(event.exception).lower()
        if "query is too old" in msg or "query id is invalid" in msg or "message is not modified" in msg:
            return True
    return False


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.errors.register(_global_error_handler)
    dp.update.outer_middleware(AdminGate())
    dp.startup.register(_on_startup)
    from adminbot.handlers import (admins, broadcast, logs, panel, receipts, security,
                                   settings, tickets, users, media, seasons,
                                   sections, prices, equipment_bulk, currency, channel,
                                   reset)
    from adminbot import crud
    for r in (panel, channel, users, receipts, tickets, broadcast, security, admins, settings,
              logs, media, seasons, sections, prices, equipment_bulk, currency, reset, crud):
        dp.include_router(r.router)
    return dp


async def run() -> None:
    check_tokens(admin=True)
    await init_db()
    bot = Bot(ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = create_dispatcher()
    me = await bot.get_me()
    log.info("🛡 ربات ادمین: @%s", me.username)
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    asyncio.run(run())

"""ربات اصلی بازی — ساخت Dispatcher و اجرا."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from core.config import GAME_BOT_TOKEN, check_tokens
from core.db import init_db, db

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("gamebot")


async def _on_startup(bot: Bot) -> None:
    """راه‌اندازی زمان‌بند پس‌زمینه و ثبت دکمه منوی دستورات تلگرام (/start و /cancel)."""
    from aiogram.types import BotCommand
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🚀 شروع بازی و ورود به امپراطوری"),
            BotCommand(command="cancel", description="❌ انصراف و بازگشت به منو"),
            BotCommand(command="admin", description="🛡 پنل مدیریت و ادمین"),
        ])
    except Exception as e:
        log.warning("تنظیم دستورات تلگرام انجام نشد: %s", e)
    from core.scheduler import start_game_scheduler
    start_game_scheduler(bot)


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
    dp.startup.register(_on_startup)
    from gamebot.handlers import (start, menu, people, projects, army, gov, war,
                                  un, misc, trade, oil, rescue)
    for r in (start, menu, people, projects, army, gov, war, un, misc, trade, oil, rescue):
        dp.include_router(r.router)
    # روتر گفتگوی مذاکره باید آخرین باشد تا FSMهای دیگر اولویت داشته باشند
    dp.include_router(trade.neg_router)
    return dp


async def run() -> None:
    check_tokens(admin=False)
    await init_db()
    bot = Bot(GAME_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = create_dispatcher()
    me = await bot.get_me()
    log.info("🎮 ربات اصلی بازی: @%s", me.username)
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    asyncio.run(run())

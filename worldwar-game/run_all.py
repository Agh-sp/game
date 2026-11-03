"""اجرای هر دو ربات در یک پروسه (ربات اصلی بازی + ربات ادمین)."""
import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from adminbot.main import create_dispatcher as create_admin_dp
from core.config import ADMIN_BOT_TOKEN, GAME_BOT_TOKEN
from core.db import init_db
from gamebot.main import create_dispatcher as create_game_dp

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("main")


async def poll_with_retry(dp, bot, name: str):
    while True:
        try:
            me = await bot.get_me()
            log.info("🤖 %s آنلاین شد: @%s", name, me.username)
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except Exception as we:
                log.warning("عدم امکان بررسی وبهوک %s: %s", name, we)
            await dp.start_polling(bot, handle_signals=False)
        except Exception as e:
            log.error("خطا در %s: %s — تلاش مجدد تا ۵ ثانیه دیگر...", name, e)
            await asyncio.sleep(5)


async def run_all() -> None:
    await init_db()
    tasks = []
    if GAME_BOT_TOKEN:
        game_bot = Bot(GAME_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        game_dp = create_game_dp()
        tasks.append(poll_with_retry(game_dp, game_bot, "ربات بازی"))
    else:
        log.warning("توکن GAME_BOT_TOKEN هنوز وارد نشده است.")

    if ADMIN_BOT_TOKEN:
        admin_bot = Bot(ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        admin_dp = create_admin_dp()
        tasks.append(poll_with_retry(admin_dp, admin_bot, "ربات ادمین"))
    else:
        log.warning("توکن ADMIN_BOT_TOKEN هنوز وارد نشده است.")

    if tasks:
        await asyncio.gather(*tasks)
    else:
        log.error("هیچ توکنی برای راه‌اندازی ربات‌ها در .env تعریف نشده است.")


if __name__ == "__main__":
    asyncio.run(run_all())

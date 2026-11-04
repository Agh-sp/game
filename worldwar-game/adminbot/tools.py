"""ابزارهای ربات ادمین: اطلاع‌رسانی به بازیکن (با توکن ربات اصلی) و لاگ ادمین."""
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from core.config import GAME_BOT_TOKEN
from core.db import db
from core.utils import iso

_game_bot: Bot | None = None


async def game_bot() -> Bot:
    """نمونه ربات اصلی برای ارسال پیام به بازیکنان."""
    global _game_bot
    if _game_bot is None:
        _game_bot = Bot(GAME_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    return _game_bot


async def notify_user(user_id: int, text: str) -> bool:
    """ارسال پیام به بازیکن از طریق ربات اصلی."""
    try:
        bot = await game_bot()
        await bot.send_message(user_id, text)
        return True
    except Exception:
        return False


async def safe_edit(target, text: str, reply_markup=None) -> bool:
    """ویرایش امن پیام در ربات ادمین (تحمل خطای «تغییر نکرده»/HTML)."""
    msg = getattr(target, "message", target)
    try:
        await msg.edit_text(text, reply_markup=reply_markup)
        return True
    except Exception as e:
        if "message is not modified" in str(e).lower():
            return True
        try:
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode=None)
            return True
        except Exception:
            pass
        try:
            await msg.answer(text, reply_markup=reply_markup)
            return True
        except Exception:
            try:
                await msg.answer(text, reply_markup=reply_markup, parse_mode=None)
                return True
            except Exception:
                return False


async def log_action(admin_id: int, action: str, detail: str = "") -> None:
    await db.execute(
        "INSERT INTO admin_logs(admin_id, action, detail) VALUES(?,?,?)",
        (admin_id, action, detail[:500]))

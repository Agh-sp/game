"""دروازه احراز هویت ربات ادمین + سطح‌بندی دسترسی."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from core.db import db
from core.utils import jloads

ALL_PERMS = [
    "users", "economy", "countries", "military", "world", "projects",
    "un", "missions", "tickets", "settings", "broadcast", "logs", "admins",
    "trade", "media", "seasons",
]

PERM_TITLES = {
    "users": "👥 کاربران", "economy": "🪙 اقتصاد و پرداخت", "countries": "🏳 کشورها",
    "military": "🪖 نظامی", "world": "🌍 دنیا و قوانین", "projects": "🏢 شرکت‌ها و پروژه‌ها",
    "un": "🗳 سازمان ملل و جنگ‌ها", "missions": "🎯 ماموریت‌ها", "tickets": "🎫 پشتیبانی",
    "settings": "⚙️ تنظیمات", "broadcast": "📣 پیام همگانی", "logs": "📜 لاگ‌ها",
    "admins": "🛡 مدیریت ادمین‌ها", "trade": "🤝 تجارت و پیمان‌ها",
    "media": "🖼 کتابخانه تصاویر", "seasons": "🎬 سیزن‌ها",
}


class AdminGate(BaseMiddleware):
    """فقط ادمین‌های ثبت‌شده اجازه استفاده از ربات ادمین را دارند."""

    async def __call__(self, handler, event, data):
        # در aiogram 3 اگر میدلور روی update باشد event از نوع Update است
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if user is None and hasattr(event, "message") and event.message:
            user = event.message.from_user
        if user is None and hasattr(event, "callback_query") and event.callback_query:
            user = event.callback_query.from_user

        if user is None or getattr(user, "is_bot", False):
            return

        from core.config import SUPER_ADMIN_ID
        admin = await db.fetchone("SELECT * FROM admins WHERE id=?", (user.id,))

        # شناسایی آبجکت پیام و کال‌بک واقعی
        msg_obj = event if isinstance(event, Message) else getattr(event, "message", None)
        call_obj = event if isinstance(event, CallbackQuery) else getattr(event, "callback_query", None)

        # اگر آیدی با SUPER_ADMIN_ID یکی بود خودکار ثبت و تایید شود
        if not admin and SUPER_ADMIN_ID and user.id == SUPER_ADMIN_ID:
            await db.execute(
                "INSERT INTO admins(id, name, is_super, perms) VALUES(?, 'سوپرادمین', 1, '[]') "
                "ON CONFLICT(id) DO UPDATE SET is_super=1",
                (user.id,),
            )
            admin = await db.fetchone("SELECT * FROM admins WHERE id=?", (user.id,))

        # اگر هیچ ادمینی در جدول نباشد، اولین استارت سوپرادمین می‌شود
        if not admin:
            row = await db.fetchone("SELECT COUNT(*) AS c FROM admins WHERE is_super=1")
            super_count = row["c"] if row else 0
            if super_count == 0:
                await db.execute(
                    "INSERT INTO admins(id, name, is_super, perms) VALUES(?, ?, 1, '[]')",
                    (user.id, user.full_name or "سوپرادمین"),
                )
                admin = await db.fetchone("SELECT * FROM admins WHERE id=?", (user.id,))

        # اگر هنوز ادمین نیست، امکان فعال‌سازی با دکمه برای مالک ربات
        if not admin:
            if call_obj and getattr(call_obj, "data", "") == "claim_admin_access":
                await db.execute(
                    "INSERT INTO admins(id, name, is_super, perms) VALUES(?, ?, 1, '[]') ON CONFLICT(id) DO UPDATE SET is_super=1",
                    (user.id, user.full_name or "سوپرادمین"),
                )
                admin = await db.fetchone("SELECT * FROM admins WHERE id=?", (user.id,))
                await call_obj.answer("✅ دسترسی سوپرادمین برای شما فعال شد! لطفا دوباره /start را ارسال کنید.", show_alert=True)
            elif msg_obj:
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                claim_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👑 فعال‌سازی فوری دسترسی سوپرادمین", callback_data="claim_admin_access")]
                ])
                await msg_obj.answer(
                    "⛔️ <b>شما هنوز ادمین ثبت نشده‌اید.</b>\n\n"
                    f"🆔 آیدی عددی شما: <code>{user.id}</code>\n"
                    f"نام کاربری: @{user.username or 'ندارد'}\n\n"
                    "💡 برای دسترسی به پنل مدیریت، روی دکمه زیر بزنید یا این آیدی را در فیلد <b>SUPER_ADMIN_ID</b> وارد کنید:",
                    reply_markup=claim_kb,
                )
                return
            elif call_obj:
                await call_obj.answer(f"⛔️ شما ادمین نیستید (آیدی: {user.id})", show_alert=True)
                return
            else:
                return

        perms = set(jloads(admin["perms"], []))
        if admin["is_super"]:
            perms = set(ALL_PERMS) | {"*"}
        data["admin"] = admin
        data["perms"] = perms
        return await handler(event, data)


def has(perms: set, perm: str) -> bool:
    return "*" in perms or perm in perms

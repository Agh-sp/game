"""دروازه احراز هویت ربات ادمین + سطح‌بندی دسترسی."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from core.db import db
from core.utils import jloads

from core.admins import ALL_PERMS as _CORE_PERMS  # مرجع واحد دسترسی‌ها (۱۰۰٪)

ALL_PERMS = list(_CORE_PERMS)

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
        from core.admins import is_config_super
        admin = await db.fetchone("SELECT * FROM admins WHERE id=?", (user.id,))

        # سوپرادمین‌های ثابت بازی (DEFAULT_SUPER_ADMIN_IDS / SUPER_ADMIN_IDS) همیشه راه دارند
        if not admin and is_config_super(user.id):
            await db.execute(
                "INSERT INTO admins(id, name, is_super, perms) VALUES(?, ?, 1, '[]') "
                "ON CONFLICT(id) DO UPDATE SET is_super=1",
                (user.id, user.full_name or "سوپرادمین"),
            )
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

        # هیچ‌کس نمی‌تواند خودش را ادمین کند — فقط سوپرادمینِ ثبت‌شده در core/config.py
        if not admin:
            if call_obj:
                await call_obj.answer(f"⛔️ این ربات فقط برای ادمین است (آیدی شما: {user.id})",
                                      show_alert=True)
                return
            if msg_obj:
                await msg_obj.answer(
                    "⛔️ <b>این ربات مدیریتی است.</b>\n\n"
                    f"🆔 آیدی عددی شما: <code>{user.id}</code>\n\n"
                    "برای بازی از ربات اصلی زیر استفاده کنید:\n"
                    "🎮 @WorldWarWordbot"
                )
            return

        perms = set(jloads(admin["perms"], []))
        if admin["is_super"]:
            perms = set(ALL_PERMS) | {"*"}
        data["admin"] = admin
        data["perms"] = perms
        return await handler(event, data)


def has(perms: set, perm: str) -> bool:
    return "*" in perms or perm in perms

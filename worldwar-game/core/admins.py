"""شناسایی ادمین‌ها در ربات بازی — سوپرادمین‌های ثابت + جدول admins.

سوپرادمین‌های پیش‌فرض (نوشته‌شده در `core.config.DEFAULT_SUPER_ADMIN_IDS`) بدون
نیاز به هیچ تنظیمی در `.env`، هم در ربات بازی و هم در ربات ادمین، دسترسی کامل
دارند. با `SUPER_ADMIN_IDS` در `.env` می‌توان آیدی‌های بیشتری اضافه کرد.
"""
from __future__ import annotations

from core.config import DEFAULT_SUPER_ADMIN_IDS, SUPER_ADMIN_ID, SUPER_ADMIN_IDS
from core.db import db


async def ensure_super_admins() -> list[int]:
    """ثبت همهٔ سوپرادمین‌های کانفیگ در جدول admins (idempotent)."""
    ids = list(dict.fromkeys([*SUPER_ADMIN_IDS, *([SUPER_ADMIN_ID] if SUPER_ADMIN_ID else [])]))
    for uid in ids:
        if not uid:
            continue
        await db.execute(
            "INSERT INTO admins(id, name, is_super, perms) VALUES(?, 'سوپرادمین', 1, '[]') "
            "ON CONFLICT(id) DO UPDATE SET is_super=1",
            (int(uid),),
        )
    return ids


def is_config_super(user_id: int) -> bool:
    """آیا این آیدی جزو سوپرادمین‌های کانفیگ است؟ (بدون پرس‌وجوی دیتابیس)"""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    return uid in set(SUPER_ADMIN_IDS) or (bool(SUPER_ADMIN_ID) and uid == SUPER_ADMIN_ID)


async def admin_row(user_id: int) -> dict | None:
    return await db.fetchone("SELECT * FROM admins WHERE id=?", (int(user_id),))


async def is_admin(user_id: int) -> bool:
    """ادمین بودن (سوپرادمین‌های کانفیگ همیشه ادمین‌اند)."""
    if is_config_super(user_id):
        return True
    return bool(await admin_row(user_id))


async def is_super_admin(user_id: int) -> bool:
    if is_config_super(user_id):
        return True
    row = await admin_row(user_id)
    return bool(row and row.get("is_super"))


def default_super_ids() -> tuple[int, ...]:
    return tuple(DEFAULT_SUPER_ADMIN_IDS)

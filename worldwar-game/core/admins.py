"""شناسایی ادمین‌ها در ربات بازی — سوپرادمین‌های ثابت + جدول admins.

سوپرادمین‌های پیش‌فرض (نوشته‌شده در `core.config.DEFAULT_SUPER_ADMIN_IDS`) بدون
نیاز به هیچ تنظیمی در `.env`، هم در ربات بازی و هم در ربات ادمین، دسترسی کامل
دارند. با `SUPER_ADMIN_IDS` در `.env` می‌توان آیدی‌های بیشتری اضافه کرد.
"""
from __future__ import annotations

import json

from core.config import (DEFAULT_SUPER_ADMIN_IDS, LEGACY_ADMIN_IDS, STRICT_SINGLE_ADMIN,
                         SUPER_ADMIN_ID, SUPER_ADMIN_IDS)
from core.db import db

# همهٔ دسترسی‌های ربات ادمین (۱۰۰٪) — مرجع واحد برای هر دو ربات
ALL_PERMS: tuple[str, ...] = (
    "users", "economy", "countries", "military", "world", "projects",
    "un", "missions", "tickets", "settings", "broadcast", "logs", "admins",
    "trade", "media", "seasons",
)


async def ensure_super_admins() -> list[int]:
    """ثبت همهٔ سوپرادمین‌های کانفیگ در جدول admins (idempotent)."""
    ids = list(dict.fromkeys([*SUPER_ADMIN_IDS, *([SUPER_ADMIN_ID] if SUPER_ADMIN_ID else [])]))
    perms = json.dumps(list(ALL_PERMS))
    for uid in ids:
        if not uid:
            continue
        # دسترسی ۱۰۰٪: هم is_super=1 و هم همهٔ perms (برای نمایش در پنل ادمین)
        await db.execute(
            "INSERT INTO admins(id, name, is_super, perms) VALUES(?, 'سوپرادمین ۱۰۰٪', 1, ?) "
            "ON CONFLICT(id) DO UPDATE SET is_super=1, perms=excluded.perms",
            (int(uid), perms),
        )
    # آیدی‌های قدیمی که دیگر نباید ادمین باشند حذف می‌شوند
    for legacy in LEGACY_ADMIN_IDS:
        if int(legacy) not in {int(i) for i in ids}:
            await db.execute("DELETE FROM admins WHERE id=?", (int(legacy),))
    # حالت تک‌ادمین: هر ادمینِ دیگر (که در کانفیگ نیست) هم حذف می‌شود
    if STRICT_SINGLE_ADMIN:
        allowed = [int(i) for i in ids if i]
        if allowed:
            marks = ",".join("?" for _ in allowed)
            await db.execute(f"DELETE FROM admins WHERE id NOT IN ({marks})", tuple(allowed))
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


async def grant_admin(user_id: int, name: str = "", is_super: bool = True) -> None:
    """دادن دسترسی کامل (۱۰۰٪) به یک آیدی."""
    await db.execute(
        "INSERT INTO admins(id, name, is_super, perms) VALUES(?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET is_super=excluded.is_super, perms=excluded.perms",
        (int(user_id), name or "ادمین", 1 if is_super else 0, json.dumps(list(ALL_PERMS))),
    )


async def revoke_admin(user_id: int) -> bool:
    """گرفتن دسترسی ادمین؛ سوپرادمین‌های ثابت کانفیگ حذف‌شدنی نیستند."""
    if is_config_super(user_id):
        return False
    await db.execute("DELETE FROM admins WHERE id=?", (int(user_id),))
    return True


async def list_admins() -> list[dict]:
    return await db.fetchall("SELECT * FROM admins ORDER BY is_super DESC, id")

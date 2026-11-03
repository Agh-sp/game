"""روشن/خاموش کردن بخش‌های بازی + تنگه‌های تکی.

ادمین می‌تواند: کل بخش تنگه‌ها، یک تنگه خاص، و هر بخش دیگر
(مذاکره/تجارت مستقیم/فروش انرژی/نفت/سازمان نجات) را خاموش و روشن کند.
"""
from aiogram import F, Router

from aiogram.types import CallbackQuery

from adminbot.auth import has
from adminbot.crud import kb
from adminbot.tools import log_action
from core.db import db, get_setting, set_setting

router = Router()

SECTION_KEYS = [
    ("sec_negotiation", "🕊 مذاکره"),
    ("sec_direct_trade", "🔁 تجارت مستقیم"),
    ("sec_rescue_sale", "🏥 فروش انرژی به سازمان نجات"),
    ("sec_straits", "⚓ کل بخش تنگه‌ها"),
    ("sec_oil", "🛢 نفت"),
    ("sec_rescue_org", "🛟 سازمان نجات"),
]


@router.callback_query(F.data == "a|sections")
async def sections_menu(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    lines = ["🔘 <b>بخش‌های بازی (روشن/خاموش)</b>\n"]
    buttons = []
    for key, title in SECTION_KEYS:
        on = await get_setting(key, "1") == "1"
        lines.append(f"{'🟢' if on else '🔴'} {title}")
        buttons.append([(f"{'🔴 خاموش' if on else '🟢 روشن'} — {title}",
                         f"a|sect|{key}")])
    lines.append("\n⚓ <b>تنگه‌های تکی:</b>")
    straits = await db.fetchall("SELECT * FROM straits ORDER BY id")
    for s in straits:
        state = "🟢" if s["is_active"] else "🔴"
        lines.append(f"{state} {s['emoji']} {s['name']}")
        buttons.append([(f"{'🔴 خاموش' if s['is_active'] else '🟢 روشن'} — {s['name']}",
                         f"a|strtg|{s['id']}")])
    buttons.append([("◀️ بازگشت", "a|root")])
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("a|sect|"))
async def section_toggle(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    key = call.data.split("|")[2]
    on = await get_setting(key, "1") == "1"
    await set_setting(key, "0" if on else "1")
    await log_action(call.from_user.id, "بخش‌ها", f"{key} → {'خاموش' if on else 'روشن'}")
    await call.answer("✅ تغییر کرد")
    await sections_menu(call, perms)


@router.callback_query(F.data.startswith("a|strtg|"))
async def strait_toggle(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    sid = int(call.data.split("|")[2])
    s = await db.fetchone("SELECT * FROM straits WHERE id=?", (sid,))
    if not s:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("UPDATE straits SET is_active=? WHERE id=?",
                     (0 if s["is_active"] else 1, sid))
    await log_action(call.from_user.id, "بخش‌ها", f"تنگه {s['name']} → {'خاموش' if s['is_active'] else 'روشن'}")
    await call.answer("✅ تغییر کرد")
    await sections_menu(call, perms)

"""🔐 پنل امنیت در ربات ادمین — وضعیت، قفل همگانی، چرخش کلیدها، تنظیمات.

هر تغییری اینجا ثبت می‌شود و پنل وب هم از همان جدول `security_events` می‌خواند.
"""
from __future__ import annotations

import os
import secrets

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import kb
from adminbot.tools import log_action
from core import config as cfg
from core import security as sec
from core.admins import is_super_admin
from core.db import get_setting, set_setting
from core.utils import is_past

router = Router()


class SecFSM(StatesGroup):
    value = State()


SEC_LABELS = {
    "broadcast_require_code": "🔐 کد تأیید برای پیام همگانی (۱=بله)",
    "broadcast_max_per_hour": "⏳ سقف ارسال همگانی در ساعت (۰=بی‌سقف)",
    "broadcast_max_recipients": "👥 سقف گیرنده در هر ارسال (۰=همه)",
    "broadcast_delay_ms": "🐢 فاصلهٔ ارسال هر پیام (میلی‌ثانیه)",
    "security_notify_fail_auth": "🔔 هشدار ورود ناموفق (۱=بله)",
    "security_auto_lock_on_spam": "🔒 قفل خودکار هنگام اسپم (۱=بله)",
    "security_alert_to": "📮 آیدی‌های هشدار (با کاما)",
}


async def security_text() -> str:
    counts = await sec.counts_since(24)
    lock_until = await get_setting("broadcast_lock_until", "")
    locked = bool(lock_until) and not is_past(lock_until)
    events = await sec.recent(limit=8)
    lines = [
        "🔐 <b>امنیت ربات</b>",
        "",
        f"📣 ارسال همگانی: {'🔒 قفل تا ' + lock_until if locked else '✅ باز'}",
        f"🧩 کلید وبهوک: {'✅ تنظیم است' if (os.getenv('WEBHOOK_SECRET') or cfg.WEBHOOK_SECRET) else '⚠️ تنظیم نشده'}",
        f"🔑 گذرواژهٔ پنل وب: {'✅ فعال' if os.getenv('PANEL_PASSWORD') else '⏳ هنگام اجرا ساخته می‌شود'}",
        "",
        "<b>۲۴ ساعت اخیر:</b>",
        sec.security_summary(counts),
        "",
        "<b>آخرین رخدادها:</b>",
    ]
    if not events:
        lines.append("  —")
    for e in events:
        lines.append(f"  • {sec.KIND_TITLES.get(e['kind'], e['kind'])} — "
                     f"{(e['detail'] or '')[:60]} <i>({e['created_at']})</i>")
    lines.append("")
    lines.append("💡 اگر پیام مشکوکی برای بازیکنان رفت: اول «قفل ارسال همگانی»، بعد "
                 "«چرخاندن کلید وبهوک» و «گذرواژهٔ تازهٔ پنل» را بزنید و ادمین‌ها را بررسی کنید.")
    return "\n".join(lines)


def security_kb() -> object:
    return kb([
        [("🔒 قفل ارسال همگانی (۱ ساعت)", "a|sec|lock"), ("🔓 بازکردن قفل", "a|sec|open")],
        [("🧩 چرخاندن کلید وبهوک", "a|sec|rot"), ("🔑 گذرواژهٔ تازهٔ پنل", "a|sec|pwd")],
        [("🔔 تست هشدار", "a|sec|alert")],
        [("🗂 رخدادهای امنیتی", "a|sec|log")],
        [("⚙️ تنظیمات امنیتی", "a|sec|set")],
        [("🔄 بروزرسانی", "a|sec|home")],
        [("◀️ بازگشت", "a|root")],
    ])


@router.callback_query(F.data == "a|sec")
@router.callback_query(F.data == "a|sec|home")
async def security_home(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.clear()
    await call.answer()
    await call.message.edit_text(await security_text(), reply_markup=security_kb())


@router.callback_query(F.data == "a|sec|lock")
async def security_lock(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    until = await sec.lock_broadcast(60, f"قفل دستی توسط {call.from_user.id}")
    await log_action(call.from_user.id, "امنیت", "قفل ارسال همگانی")
    await call.answer(f"🔒 تا {until} قفل شد", show_alert=True)
    await call.message.edit_text(await security_text(), reply_markup=security_kb())


@router.callback_query(F.data == "a|sec|open")
async def security_open(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await sec.unlock_broadcast()
    await log_action(call.from_user.id, "امنیت", "بازکردن قفل ارسال همگانی")
    await call.answer("🔓 قفل برداشته شد", show_alert=True)
    await call.message.edit_text(await security_text(), reply_markup=security_kb())


@router.callback_query(F.data == "a|sec|rot")
async def security_rotate(call: CallbackQuery, perms: set):
    if not await is_super_admin(call.from_user.id):
        return await call.answer("⛔️ فقط سوپرادمین", show_alert=True)
    fresh = secrets.token_urlsafe(32)
    await set_setting("webhook_secret", fresh)
    cfg.WEBHOOK_SECRET = fresh
    os.environ["WEBHOOK_SECRET"] = fresh
    await sec.record("lock", call.from_user.id, "کلید وبهوک چرخانده شد (ربات ادمین)")
    await log_action(call.from_user.id, "امنیت", "چرخش کلید وبهوک")
    await call.answer("✅ کلید تازه ساخته شد — وبهوک را دوباره ثبت کنید", show_alert=True)
    await call.message.edit_text(await security_text(), reply_markup=security_kb())


@router.callback_query(F.data == "a|sec|pwd")
async def security_password(call: CallbackQuery, perms: set):
    if not await is_super_admin(call.from_user.id):
        return await call.answer("⛔️ فقط سوپرادمین", show_alert=True)
    pwd = await sec.set_panel_password("")
    await sec.record("lock", call.from_user.id, "گذرواژهٔ پنل وب بازسازی شد (ربات ادمین)")
    await log_action(call.from_user.id, "امنیت", "گذرواژهٔ پنل وب بازسازی شد")
    await call.answer()
    await call.message.edit_text(
        "🔑 <b>گذرواژهٔ تازهٔ پنل وب</b>\n\n"
        f"<code>{pwd}</code>\n\n"
        "این پیام را بعد از ذخیره پاک کنید. آدرس ورود: <code>/login</code>",
        reply_markup=security_kb())


@router.callback_query(F.data == "a|sec|alert")
async def security_alert_test(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await sec.alert(call.bot, f"تست هشدار — {call.from_user.full_name} "
                              f"(<code>{call.from_user.id}</code>)")
    await call.answer("🔔 هشدار برای سوپرادمین‌ها ارسال شد", show_alert=True)


@router.callback_query(F.data == "a|sec|log")
async def security_log(call: CallbackQuery, perms: set):
    if not has(perms, "logs"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    rows = await sec.recent(limit=25)
    lines = ["🗂 <b>رخدادهای امنیتی</b>", ""]
    if not rows:
        lines.append("— هیچ رخدادی ثبت نشده —")
    for e in rows:
        lines.append(f"• {sec.KIND_TITLES.get(e['kind'], e['kind'])} — "
                     f"<code>{e['user_id']}</code> — {(e['detail'] or '')[:70]}\n"
                     f"  <i>{e['created_at']}</i>")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=security_kb())


@router.callback_query(F.data == "a|sec|set")
async def security_settings(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    rows = [[(f"{title} — {await get_setting(key, '')}", f"a|secv|{key}")]
            for key, title in SEC_LABELS.items()]
    rows.append([("◀️ بازگشت", "a|sec|home")])
    await call.answer()
    await call.message.edit_text(
        "⚙️ <b>تنظیمات امنیتی</b>\n\n"
        "• <code>۱</code> = روشن / <code>۰</code> = خاموش\n"
        "• فاصلهٔ ارسال همگانی: زیر ۳۰ میلی‌ثانیه = خطر محدودیت تلگرام\n"
        "• سقف گیرنده: برای تست، مثلاً ۲ بگذارید\n"
        "• آیدی‌های هشدار را با کاما جدا کنید.",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("a|secv|"))
async def security_setting_pick(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    key = call.data.split("|")[2]
    if key not in SEC_LABELS:
        return await call.answer("تنظیم نامعتبر", show_alert=True)
    await state.set_state(SecFSM.value)
    await state.update_data(sec_key=key)
    await call.answer()
    await call.message.edit_text(
        f"⚙️ مقدار جدید برای «{SEC_LABELS[key]}»:\n"
        f"مقدار فعلی: <b>{await get_setting(key, '—')}</b>\nبرای انصراف /cancel")


@router.message(SecFSM.value)
async def security_setting_save(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("sec_key", "")
    raw = (message.text or "").strip()
    if key not in SEC_LABELS or not raw:
        await state.clear()
        return await message.answer("❌ مقدار نامعتبر است.", reply_markup=security_kb())
    before = await get_setting(key, "—")
    await set_setting(key, raw)
    await sec.record("settings", message.from_user.id, f"{key}: {before} → {raw}")
    await state.clear()
    await message.answer(f"✅ «{SEC_LABELS[key]}» به <b>{raw}</b> تغییر کرد.",
                         reply_markup=security_kb())

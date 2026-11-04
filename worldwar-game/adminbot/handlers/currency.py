"""درخواست‌های ارز کشورها — تأیید/رد تغییر ارز و ساخت ارز جدید.

پس از تأیید ادمین: ارز کشور بازیکن تغییر می‌کند و خبر آن
با عکس (کتابخانه تصاویر، بخش currency) در کانال اعلام می‌شود.
"""
from aiogram import F, Router
from aiogram.filters import Command

from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import kb
from adminbot.tools import log_action
from core.db import db, get_setting
from core.economy import get_country
from core.events import log_event
from core.images import announce_img

router = Router()


async def _requests_payload() -> dict:
    rows = await db.fetchall(
        "SELECT cr.*, c.name, c.flag FROM currency_requests cr "
        "LEFT JOIN users u ON u.id=cr.user_id LEFT JOIN countries c ON c.id=u.country_id "
        "ORDER BY CASE cr.status WHEN 'pending' THEN 0 ELSE 1 END, cr.id DESC LIMIT 20")
    lines = ["💵 <b>درخواست‌های ارز</b>\n"]
    buttons = []
    if not rows:
        lines.append("— درخواستی نیست —")
    for r in rows:
        who = f"{r['flag']} {r['name']}" if r["name"] else f"کاربر {r['user_id']}"
        kind = "استفاده از ارز کشور دیگر" if r["req_type"] == "adopt" else "ساخت ارز جدید"
        status = {"pending": "⏳ در انتظار", "approved": "✅ تأیید شده",
                  "rejected": "❌ رد شده"}.get(r["status"], r["status"])
        lines.append(f"• <b>{who}</b> — {kind}: «{r['value']}» — {status} <code>#{r['id']}</code>")
        if r["status"] == "pending":
            buttons.append([
                (f"✅ تأیید #{r['id']}", f"a|curok|{r['id']}"),
                (f"❌ رد #{r['id']}", f"a|curno|{r['id']}"),
            ])
    buttons.append([("◀️ بازگشت", "a|root")])
    return {"text": "\n".join(lines), "reply_markup": kb(buttons)}


@router.message(Command("currency"))
async def cmd_currency(message: Message, perms: set):
    if not has(perms, "economy"):
        return await message.answer("⛔️ دسترسی ندارید")
    await message.answer(**await _requests_payload())


@router.callback_query(F.data == "a|cur")
async def currency_requests_menu(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    payload = await _requests_payload()
    await call.answer()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data.startswith("a|curok|"))
async def currency_approve(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    rid = int(call.data.split("|")[2])
    r = await db.fetchone("SELECT * FROM currency_requests WHERE id=? AND status='pending'", (rid,))
    if not r:
        return await call.answer("درخواست یافت نشد", show_alert=True)
    # اعمال ارز جدید
    if r["req_type"] == "create":
        new_cur = r["value"]
    else:
        new_cur = r["value"]  # نام ارز کشور دیگر
    await db.execute("UPDATE states SET currency_name=? WHERE user_id=?", (new_cur, r["user_id"]))
    await db.execute("UPDATE currency_requests SET status='approved', reviewed_by=? WHERE id=?",
                     (call.from_user.id, rid))
    c = await get_country(r["user_id"])
    await log_action(call.from_user.id, "ارز", f"تأیید #{rid}: {new_cur}")
    await log_event("currency", f"ارز کشور {c['name'] if c else r['user_id']} به «{new_cur}» تغییر کرد")
    # اعلام در کانال با عکس
    if c:
        await announce_img(call.bot,
                           f"💵 ارز کشور {c['flag']} {c['name']} با تأیید ادمین به "
                           f"«<b>{new_cur}</b>» تغییر کرد.",
                           "currency")
    try:
        await call.bot.send_message(r["user_id"],
                                    f"✅ درخواست ارز شما تأیید شد! ارز کشور شما حالا «{new_cur}» است.")
    except Exception:
        pass
    await call.answer("✅ تأیید شد")
    payload = await _requests_payload()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data.startswith("a|curno|"))
async def currency_reject(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    rid = int(call.data.split("|")[2])
    r = await db.fetchone("SELECT * FROM currency_requests WHERE id=? AND status='pending'", (rid,))
    if not r:
        return await call.answer("درخواست یافت نشد", show_alert=True)
    await db.execute("UPDATE currency_requests SET status='rejected', reviewed_by=? WHERE id=?",
                     (call.from_user.id, rid))
    await log_action(call.from_user.id, "ارز", f"رد #{rid}")
    try:
        await call.bot.send_message(r["user_id"], "❌ درخواست ارز شما رد شد.")
    except Exception:
        pass
    await call.answer("رد شد")
    payload = await _requests_payload()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])

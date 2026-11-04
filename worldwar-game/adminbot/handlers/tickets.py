"""تیکت‌های پشتیبانی: مشاهده، پاسخ و بستن."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import cd, kb
from adminbot.tools import log_action, notify_user
from core.db import db
from core.utils import fmt, tehran, iso

router = Router()
PAGE = 6

KIND_FA = {"complaint": "😠 شکایت", "idea": "💡 ایده", "bug": "🐞 باگ"}
STATUS_FA = {"open": "⏳ باز", "answered": "✅ پاسخ‌داده", "closed": "🔒 بسته"}


class TicketFSM(StatesGroup):
    reply = State()


@router.message(Command("tickets"))
async def cmd_tickets(message: Message, perms: set):
    if not has(perms, "tickets"):
        return await message.answer("⛔️ دسترسی ندارید")
    await message.answer(**await tickets_page("open", 0))


async def tickets_page(status: str, page: int) -> dict:
    total = (await db.fetchone("SELECT COUNT(*) c FROM tickets WHERE status=?", (status,)))["c"]
    rows = await db.fetchall(
        "SELECT t.*, u.full_name FROM tickets t LEFT JOIN users u ON u.id=t.user_id "
        "WHERE t.status=? ORDER BY t.id DESC LIMIT ? OFFSET ?",
        (status, PAGE, page * PAGE))
    lines = [f"🎫 <b>تیکت‌ها — {STATUS_FA.get(status, status)}</b> ({fmt(total)})\n"]
    buttons = []
    for t in rows:
        lines.append(f"#{t['id']} {KIND_FA.get(t['kind'], t['kind'])} — {t['full_name'] or t['user_id']}"
                     f" — {tehran(t['created_at'])}")
        buttons.append([(f"🎫 #{t['id']} {KIND_FA.get(t['kind'], '')} {(t['text'] or '')[:25]}", 
                         f"a|tiko|{t['id']}")])
    if not rows:
        lines.append("<i>— خالی —</i>")
    tabs = [("⏳ باز", "a|tik|open|0"), ("✅ پاسخ‌داده", "a|tik|answered|0"),
            ("🔒 بسته", "a|tik|closed|0")]
    nav = list(tabs)
    if page > 0:
        nav.append(("‹ قبلی", f"a|tik|{status}|{page - 1}"))
    if (page + 1) * PAGE < total:
        nav.append(("بعدی ›", f"a|tik|{status}|{page + 1}"))
    all_rows = [[b] for b in buttons] + [nav, [("◀️ بازگشت", "a|root")]]
    return {"text": "\n".join(lines), "reply_markup": kb(all_rows)}


@router.callback_query(F.data.startswith("a|tik|"))
async def tickets_list(call: CallbackQuery, perms: set):
    if not has(perms, "tickets"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    _, _, status, page = call.data.split("|")
    payload = await tickets_page(status, int(page))
    await call.answer()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data.startswith("a|tiko|"))
async def ticket_open(call: CallbackQuery, perms: set):
    if not has(perms, "tickets"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    tid = int(call.data.split("|")[2])
    t = await db.fetchone(
        "SELECT t.*, u.full_name, u.username FROM tickets t "
        "LEFT JOIN users u ON u.id=t.user_id WHERE t.id=?", (tid,))
    if not t:
        return await call.answer("یافت نشد", show_alert=True)
    if t["photo_file_id"]:
        try:
            await call.message.answer_photo(t["photo_file_id"], caption=f"📎 عکس تیکت #{tid}")
        except Exception:
            pass
    text = (
        f"🎫 <b>تیکت #{t['id']}</b>\n\n"
        f"👤 کاربر: {t['full_name'] or '—'} <code>{t['user_id']}</code>"
        + (f" (@{t['username']})" if t["username"] else "") + "\n"
        f"📋 نوع: {KIND_FA.get(t['kind'], t['kind'])}\n"
        f"📅 زمان: {tehran(t['created_at'])}\n"
        f"📌 وضعیت: {STATUS_FA.get(t['status'], t['status'])}\n\n"
        f"💬 <b>متن:</b>\n{t['text']}")
    if t["reply"]:
        text += f"\n\n📨 <b>پاسخ قبلی:</b>\n{t['reply']}"
    buttons = []
    if t["status"] != "closed":
        buttons.append([("📨 پاسخ به کاربر", f"a|tikr|{tid}")])
    if t["status"] != "closed":
        buttons.append([("🔒 بستن تیکت", f"a|tikc|{tid}")])
    buttons.append([("✏️ ویرایش خام", cd("tik", "r", tid))])
    buttons.append([("◀️ بازگشت", f"a|tik|{t['status']}|0")])
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("a|tikr|"))
async def ticket_reply(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "tickets"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    tid = int(call.data.split("|")[2])
    await state.set_state(TicketFSM.reply)
    await state.update_data(tid=tid)
    await call.answer()
    await call.message.edit_text("📨 متن پاسخ را برای کاربر بفرستید:\n برای انصراف /cancel")


@router.message(TicketFSM.reply)
async def ticket_reply_input(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    reply = (message.text or "").strip()
    if not reply or len(reply) > 3000:
        return await message.answer("❌ متن باید بین ۱ تا ۳۰۰۰ حرف باشد.")
    t = await db.fetchone("SELECT * FROM tickets WHERE id=?", (data["tid"],))
    if not t:
        return await message.answer("❌ تیکت یافت نشد.")
    await db.execute(
        "UPDATE tickets SET status='answered', reply=?, replied_at=?, replied_by=? WHERE id=?",
        (reply, iso(), message.from_user.id, data["tid"]))
    ok = await notify_user(
        t["user_id"],
        f"📨 پاسخ پشتیبانی به تیکت #{t['id']} شما:\n\n{reply}")
    await log_action(message.from_user.id, "تیکت", f"پاسخ تیکت #{data['tid']}")
    await message.answer("✅ پاسخ ارسال شد." if ok else
                         "⚠️ ارسال به کاربر ممکن نشد (ربات را بلاک کرده؟) — پاسخ ذخیره شد.")


@router.callback_query(F.data.startswith("a|tikc|"))
async def ticket_close(call: CallbackQuery, perms: set):
    if not has(perms, "tickets"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    tid = int(call.data.split("|")[2])
    await db.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
    await log_action(call.from_user.id, "تیکت", f"بستن تیکت #{tid}")
    await call.answer("🔒 بسته شد")
    await tickets_list(call, perms)

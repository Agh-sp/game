"""لاگ عملیات ادمین‌ها."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import kb
from core.db import db
from core.utils import fmt, tehran

router = Router()
PAGE = 10


async def logs_payload(page: int) -> dict:
    total = (await db.fetchone("SELECT COUNT(*) c FROM admin_logs"))["c"]
    rows = await db.fetchall(
        "SELECT l.*, a.name FROM admin_logs l LEFT JOIN admins a ON a.id=l.admin_id "
        "ORDER BY l.id DESC LIMIT ? OFFSET ?", (PAGE, page * PAGE))
    lines = [f"📜 <b>لاگ عملیات ادمین‌ها</b> ({fmt(total)})\n"]
    for r in rows:
        who = r["name"] or r["admin_id"]
        detail = f" — {r['detail'][:80]}" if r["detail"] else ""
        lines.append(f"#{r['id']} [{tehran(r['created_at'])}] {who}: {r['action']}{detail}")
    if not rows:
        lines.append("<i>— خالی —</i>")
    buttons = []
    nav = []
    if page > 0:
        nav.append(("‹ قبلی", f"a|log|{page - 1}"))
    if (page + 1) * PAGE < total:
        nav.append(("بعدی ›", f"a|log|{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([("◀️ بازگشت", "a|root")])
    return {"text": "\n".join(lines), "reply_markup": kb(buttons)}


@router.callback_query(F.data.startswith("a|log|"))
async def logs_menu(call: CallbackQuery, perms: set):
    if not has(perms, "logs"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    page = int(call.data.split("|")[2]) if len(call.data.split("|")) > 2 else 0
    payload = await logs_payload(page)
    await call.answer()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])


@router.message(Command("logs"))
async def cmd_logs(message: Message, perms: set):
    if not has(perms, "logs"):
        return await message.answer("⛔️ دسترسی ندارید")
    payload = await logs_payload(0)
    await message.answer(payload["text"], reply_markup=payload["reply_markup"])

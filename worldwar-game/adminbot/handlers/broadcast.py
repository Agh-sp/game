"""پیام همگانی به همه بازیکنان (ارسال از طریق ربات اصلی)."""
import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import kb
from adminbot.tools import game_bot, log_action
from core.db import db
from core.utils import fmt

router = Router()


class BroadcastFSM(StatesGroup):
    text = State()
    confirm = State()


@router.message(Command("bc"))
async def cmd_broadcast(message: Message, state: FSMContext, perms: set):
    if not has(perms, "broadcast"):
        return await message.answer("⛔️ دسترسی ندارید")
    await state.set_state(BroadcastFSM.text)
    await message.answer(
        "📣 <b>پیام همگانی</b>\n\nمتن پیام را بفرستید (برای همه بازیکنان ارسال می‌شود):\n"
        " برای انصراف /cancel")


@router.callback_query(F.data == "a|bc")
async def broadcast_start(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "broadcast"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.set_state(BroadcastFSM.text)
    await call.answer()
    await call.message.edit_text(
        "📣 <b>پیام همگانی</b>\n\nمتن پیام را بفرستید (برای همه بازیکنان ارسال می‌شود):\n"
        " برای انصراف /cancel")


@router.message(BroadcastFSM.text)
async def broadcast_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 3500:
        return await message.answer("❌ متن باید بین ۱ تا ۳۵۰۰ حرف باشد.")
    await state.set_state(BroadcastFSM.confirm)
    await state.update_data(bc_text=text)
    users = (await db.fetchone("SELECT COUNT(*) c FROM users WHERE banned=0"))["c"]
    await message.answer(
        f"👁 <b>پیش‌نمایش پیام همگانی</b> برای {fmt(users)} بازیکن:\n\n{'─' * 24}\n{text}\n{'─' * 24}\n\n"
        "ارسال شود؟",
        reply_markup=kb([
            [("✅ ارسال به همه", "a|bcgo")],
            [("✏️ متن جدید", "a|bc")],
            [("❌ انصراف", "a|root")],
        ]))


@router.callback_query(F.data == "a|bcgo")
async def broadcast_go(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "broadcast"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    data = await state.get_data()
    text = data.get("bc_text")
    await state.clear()
    if not text:
        return await call.answer("متنی ثبت نشده", show_alert=True)
    await call.answer()
    progress = await call.message.edit_text("📣 در حال ارسال...\n0 ارسال شده")
    users = await db.fetchall("SELECT id FROM users WHERE banned=0")
    bot = await game_bot()
    sent, failed = 0, 0
    for i, u in enumerate(users, 1):
        try:
            await bot.send_message(u["id"], text)
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            try:
                await progress.edit_text(f"📣 در حال ارسال...\n{fmt(i)} ارسال شده")
            except Exception:
                pass
        await asyncio.sleep(0.05)
    try:
        await progress.edit_text(
            f"📣 <b>ارسال همگانی تمام شد!</b>\n\n✅ موفق: {fmt(sent)}\n❌ ناموفق: {fmt(failed)}")
    except Exception:
        await call.message.answer(f"📣 تمام شد: {fmt(sent)} موفق / {fmt(failed)} ناموفق")
    await log_action(call.from_user.id, "همگانی", f"ارسال به {sent} بازیکن")

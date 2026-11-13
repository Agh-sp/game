"""پیام همگانی به همه بازیکنان (ارسال از طریق ربات اصلی).

🛡 امنیت: ارسال همگانی حساس‌ترین عمل ربات است — همان کاری که یک بار با نفوذ
به حساب ادمین برای همهٔ بازیکنان انجام شد. از این پس:

  • فقط **سوپرادمین** (نه هر ادمین با دسترسی broadcast) می‌تواند ارسال کند؛
  • متن قبل از ارسال **پاک‌سازی** می‌شود (حذف تگ‌های HTML غیرمجاز و نویسه‌های
    کنترلی دوطرفه که برای جعل ظاهر پیام به کار می‌روند)؛
  • یک **کد تأیید ۴رقمی** لازم است (قابل خاموش‌کردن از تنظیمات)؛
  • سقف تعداد ارسال در ساعت + قفل اضطراری (`broadcast_lock_until`)؛
  • هر ارسال/رد در `security_events` و `admin_logs` ثبت می‌شود؛
  • فاصلهٔ ارسال هر پیام قابل تنظیم است تا به محدودیت تلگرام نخوریم.
"""
import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import kb
from adminbot.tools import game_bot, log_action
from core import security as sec
from core.db import db, get_setting
from core.utils import fmt

router = Router()


class BroadcastFSM(StatesGroup):
    text = State()
    confirm = State()


async def _is_super(user_id: int) -> bool:
    """آیا این کاربر سوپرادمین است؟"""
    from core.admins import is_super_admin
    return await is_super_admin(int(user_id))


async def broadcast_guard(user_id: int) -> tuple[bool, str]:
    """نگهبان مشترک ارسال همگانی (ربات ادمین و ربات بازی از همین استفاده می‌کنند)."""
    if not await _is_super(user_id):
        return False, "⛔️ ارسال همگانی فقط برای سوپرادمین مجاز است."
    if await sec.broadcast_lock_active():
        return False, "🔒 ارسال همگانی موقتاً قفل شده است (از پنل ادمین → 🔐 امنیت باز کنید)."
    try:
        per_hour = int(float(await get_setting("broadcast_max_per_hour", "1")))
    except (TypeError, ValueError):
        per_hour = 1
    if per_hour > 0:
        ok, wait = sec.rate_ok("broadcast", user_id, limit=per_hour,
                               window_seconds=3600, consume=False)
        if not ok:
            await sec.record("broadcast_denied", user_id,
                             f"سقف ارسال در ساعت ({per_hour}) — {wait}s")
            return False, f"⏳ سقف ارسال همگانی در ساعت پر شده — {wait} ثانیه دیگر."
    return True, ""


async def broadcast_targets(limit: int = 0) -> list[int]:
    """گیرندگان پیام همگانی (کاربران غیرمسدود)."""
    users = await db.fetchall("SELECT id FROM users WHERE banned=0 ORDER BY id")
    ids = [int(u["id"]) for u in users]
    return ids[:limit] if limit and limit > 0 else ids


async def send_broadcast(bot, sender_id: int, text: str,
                         progress=None, delay_ms: int = 60) -> tuple[int, int]:
    """ارسال واقعی پیام به همه + ثبت لاگ امنیتی. خروجی: (موفق, ناموفق)."""
    try:
        limit = int(float(await get_setting("broadcast_max_recipients", "0")))
    except (TypeError, ValueError):
        limit = 0
    # مصرف واقعی سقف نرخ فقط هنگام ارسال (نه در مراحل میانی جریان)
    try:
        per_hour = int(float(await get_setting("broadcast_max_per_hour", "1")))
    except (TypeError, ValueError):
        per_hour = 1
    if per_hour > 0:
        allowed, wait = sec.rate_ok("broadcast", sender_id, limit=per_hour,
                                    window_seconds=3600)
        if not allowed:
            await sec.record("broadcast_denied", sender_id,
                             f"سقف ارسال در ساعت هنگام ارسال ({wait}s)")
            return 0, 0
    ids = await broadcast_targets(limit)
    sent = failed = 0
    for i, uid in enumerate(ids, 1):
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        if progress is not None and i % 25 == 0:
            try:
                await progress(i)
            except Exception:
                pass
        await asyncio.sleep(max(0, delay_ms) / 1000)
    await sec.record("broadcast", sender_id,
                     f"ارسال به {sent} از {len(ids)} گیرنده — «{text[:80]}»")
    return sent, failed


def _preview(text: str) -> str:
    return f"👁 <b>پیش‌نمایش پیام همگانی</b>:\n\n{'─' * 24}\n{text}\n{'─' * 24}\n\n"


@router.message(Command("bc"))
async def cmd_broadcast(message: Message, state: FSMContext, perms: set):
    if not has(perms, "broadcast"):
        return await message.answer("⛔️ دسترسی ندارید")
    ok, why = await broadcast_guard(message.from_user.id)
    if not ok:
        return await message.answer(why)
    await state.set_state(BroadcastFSM.text)
    await message.answer(
        "📣 <b>پیام همگانی</b>\n\nمتن پیام را بفرستید (برای همه بازیکنان ارسال می‌شود):\n"
        " برای انصراف /cancel")


@router.callback_query(F.data == "a|bc")
async def broadcast_start(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "broadcast"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    ok, why = await broadcast_guard(call.from_user.id)
    if not ok:
        await sec.record("broadcast_denied", call.from_user.id, why)
        return await call.answer(why, show_alert=True)
    await state.set_state(BroadcastFSM.text)
    await call.answer()
    await call.message.edit_text(
        "📣 <b>پیام همگانی</b>\n\nمتن پیام را بفرستید (برای همه بازیکنان ارسال می‌شود):\n"
        " برای انصراف /cancel")


@router.message(BroadcastFSM.text)
async def broadcast_text(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw:
        return await message.answer("❌ متن باید بین ۱ تا ۳۵۰۰ حرف باشد.")
    text, warnings = sec.sanitize_text(raw)
    if not text.strip():
        return await message.answer("❌ متن پس از پاک‌سازی خالی شد — دوباره بفرستید.")
    users = (await db.fetchone("SELECT COUNT(*) c FROM users WHERE banned=0"))["c"]
    need_code = (await get_setting("broadcast_require_code", "1")).strip() in ("1", "true", "yes")
    if warnings:
        await sec.record("weird_text", message.from_user.id, "; ".join(warnings))

    if need_code:
        code = sec.make_code(message.from_user.id, text)
        await state.set_state(BroadcastFSM.confirm)
        await message.answer(
            _preview(text) +
            f"برای {fmt(users)} بازیکن ارسال شود؟\n\n"
            f"🔐 <b>کد تأیید شما: <code>{code}</code></b>\n"
            "کد را در پیام بعدی بفرستید (۱۰ دقیقه اعتبار، یک‌بار مصرف).\n"
            "برای انصراف /cancel",
            reply_markup=kb([[("❌ انصراف", "a|root")]]))
        return

    await state.set_state(BroadcastFSM.confirm)
    await state.update_data(bc_text=text)
    await message.answer(_preview(text) + "ارسال شود؟", reply_markup=kb([
        [("✅ ارسال به همه", "a|bcgo")],
        [("✏️ متن جدید", "a|bc")],
        [("❌ انصراف", "a|root")],
    ]))


@router.message(BroadcastFSM.confirm)
async def broadcast_code(message: Message, state: FSMContext):
    """بررسی کد تأیید و ارسال."""
    ok, why = await broadcast_guard(message.from_user.id)
    if not ok:
        await state.clear()
        return await message.answer(why)
    good, text_or_err = sec.check_code(message.from_user.id, (message.text or "").strip())
    if not good:
        await sec.record("broadcast_denied", message.from_user.id, f"کد تأیید: {text_or_err}")
        return await message.answer(f"❌ {text_or_err}\nدوباره کد را بفرستید یا /cancel")
    await state.clear()
    text = text_or_err
    await sec.record("broadcast", message.from_user.id, f"شروع ارسال همگانی «{text[:80]}»")
    progress = await message.answer("📣 در حال ارسال...\n0 ارسال شده")
    bot = await game_bot()
    try:
        delay = int(float(await get_setting("broadcast_delay_ms", "60")))
    except (TypeError, ValueError):
        delay = 60

    async def _tick(i: int) -> None:
        try:
            await progress.edit_text(f"📣 در حال ارسال...\n{fmt(i)} ارسال شده")
        except Exception:
            pass

    sent, failed = await send_broadcast(bot, message.from_user.id, text, progress=_tick, delay_ms=delay)
    await message.answer(f"📣 <b>ارسال همگانی تمام شد!</b>\n\n✅ موفق: {fmt(sent)}\n❌ ناموفق: {fmt(failed)}")
    await log_action(message.from_user.id, "همگانی", f"ارسال به {sent} بازیکن")


@router.callback_query(F.data == "a|bcgo")
async def broadcast_go(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "broadcast"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    ok, why = await broadcast_guard(call.from_user.id)
    if not ok:
        await sec.record("broadcast_denied", call.from_user.id, why)
        return await call.answer(why, show_alert=True)
    data = await state.get_data()
    text = data.get("bc_text")
    await state.clear()
    if not text:
        return await call.answer("متنی ثبت نشده", show_alert=True)
    await call.answer()
    progress = await call.message.edit_text("📣 در حال ارسال...\n0 ارسال شده")
    bot = await game_bot()
    try:
        delay = int(float(await get_setting("broadcast_delay_ms", "60")))
    except (TypeError, ValueError):
        delay = 60

    async def _tick(i: int) -> None:
        try:
            await progress.edit_text(f"📣 در حال ارسال...\n{fmt(i)} ارسال شده")
        except Exception:
            pass

    sent, failed = await send_broadcast(bot, call.from_user.id, text, progress=_tick, delay_ms=delay)
    try:
        await progress.edit_text(
            f"📣 <b>ارسال همگانی تمام شد!</b>\n\n✅ موفق: {fmt(sent)}\n❌ ناموفق: {fmt(failed)}")
    except Exception:
        await call.message.answer(f"📣 تمام شد: {fmt(sent)} موفق / {fmt(failed)} ناموفق")
    await log_action(call.from_user.id, "همگانی", f"ارسال به {sent} بازیکن")

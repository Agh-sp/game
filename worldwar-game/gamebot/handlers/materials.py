"""🧱 خرید مصالح ساختمانی — دقیقاً مثل خرید تجهیزات نظامی.

مصالح (`states.materials`) در ساخت پادگان، پروژه‌ها، نیروگاه و مراحل غنی‌سازی
مصرف می‌شود. این بخش امکان خرید مستقیم مصالح با پول یا سکه شاهی را می‌دهد.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.utils import fmt, fmt_money
from gamebot.common import back_row, kb, send_home

router = Router()


class MaterialFSM(StatesGroup):
    qty = State()


# (کلید, تعداد واحد, قیمت پول, قیمت سکه, برچسب تخفیف)
PACKAGES = [
    ("m1", 1_000, 20_000_000, 0, ""),
    ("m2", 10_000, 180_000_000, 0, "۱۰٪ تخفیف"),
    ("m3", 50_000, 800_000_000, 0, "۲۰٪ تخفیف"),
    ("m4", 100_000, 0, 90, "با سکه شاهی"),
]


async def _materials(user_id: int) -> int:
    row = await db.fetchone("SELECT materials FROM states WHERE user_id=?", (user_id,))
    return int((row or {}).get("materials") or 0)


async def _unit_price() -> tuple[int, int]:
    """(قیمت هر واحد با پول، هر واحد با سکه)"""
    try:
        money = int(float(await get_setting("material_unit_price", "20000")))
    except (TypeError, ValueError):
        money = 20000
    try:
        coins = int(float(await get_setting("material_unit_coins", "1")))
    except (TypeError, ValueError):
        coins = 1
    return max(1, money), max(1, coins)


async def materials_shop_text(user_id: int) -> str:
    money_per, coins_per = await _unit_price()
    have = await _materials(user_id)
    user = await db.fetchone("SELECT money, royal_coins FROM users WHERE id=?", (user_id,)) or {}
    lines = [
        "🧱 <b>خرید مصالح ساختمانی</b>\n",
        f"📦 موجودی فعلی شما: <b>{fmt(have)}</b> واحد",
        f"💰 خزانه: <b>{fmt_money(int(user.get('money') or 0))}</b> | "
        f"🪙 سکه: <b>{fmt(int(user.get('royal_coins') or 0))}</b>\n",
        f"💵 قیمت هر واحد: <b>{fmt_money(money_per)}</b> • "
        f"🪙 یا <b>{fmt(coins_per)}</b> سکه شاهی\n",
        "<b>پکیج‌های آماده:</b>",
    ]
    for _key, units, price, coins, note in PACKAGES:
        if coins:
            cost = f"🪙 {fmt(coins)} سکه"
        else:
            cost = f"💰 {fmt_money(price)}"
        suffix = f" <i>({note})</i>" if note else ""
        lines.append(f"📦 {fmt(units)} واحد — {cost}{suffix}")
    lines.append("\n💡 مصالح در ساخت پادگان، پروژه‌ها، نیروگاه و "
                 "مراحل غنی‌سازی مصرف می‌شود.")
    return "\n".join(lines)


def _shop_rows() -> list:
    rows = [[("📦 ۱٬۰۰۰ واحد — ۲۰ میلیون", "g|matb|m1")],
            [("📦 ۱۰٬۰۰۰ واحد — ۱۸۰ میلیون (۱۰٪)", "g|matb|m2")],
            [("📦 ۵۰٬۰۰۰ واحد — ۸۰۰ میلیون (۲۰٪)", "g|matb|m3")],
            [("🪙 ۱۰۰٬۰۰۰ واحد — ۹۰ سکه", "g|matb|m4")],
            [("✍️ خرید مقدار دلخواه", "g|matq")],
            [("🏛 بازگشت به مدیریت کشور", "g|mg"), ("🎖 پادگان", "g|bar")]]
    return rows


@router.callback_query(F.data == "g|matshop")
async def materials_shop(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        await materials_shop_text(call.from_user.id), reply_markup=kb(_shop_rows()))


@router.callback_query(F.data.startswith("g|matb|"))
async def buy_package(call: CallbackQuery):
    key = call.data.split("|")[2]
    pkg = next((p for p in PACKAGES if p[0] == key), None)
    if not pkg:
        return await call.answer("یافت نشد", show_alert=True)
    _k, units, price, coins, _note = pkg
    user = await db.fetchone("SELECT money, royal_coins FROM users WHERE id=?",
                             (call.from_user.id,))
    if not user:
        return await call.answer("کاربر یافت نشد", show_alert=True)
    if coins:
        if int(user["royal_coins"] or 0) < coins:
            return await call.answer(
                f"❌ سکه شاهی کافی نیست — نیاز: {fmt(coins)}", show_alert=True)
        await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?",
                         (coins, call.from_user.id))
    else:
        if int(user["money"] or 0) < price:
            return await call.answer(
                f"❌ بودجه کافی نیست — نیاز: {fmt_money(price)}", show_alert=True)
        await db.execute("UPDATE users SET money=money-? WHERE id=?",
                         (price, call.from_user.id))
    await db.execute("UPDATE states SET materials=COALESCE(materials,0)+? WHERE user_id=?",
                     (units, call.from_user.id))
    have = await _materials(call.from_user.id)
    await call.answer(f"✅ {fmt(units)} واحد مصالح اضافه شد", show_alert=True)
    await call.message.edit_text(
        f"✅ <b>خرید انجام شد!</b>\n\n"
        f"📦 اضافه شد: <b>{fmt(units)}</b> واحد مصالح\n"
        f"📦 موجودی جدید: <b>{fmt(have)}</b> واحد\n\n"
        + await materials_shop_text(call.from_user.id),
        reply_markup=kb(_shop_rows()))


@router.callback_query(F.data == "g|matq")
async def ask_qty(call: CallbackQuery, state: FSMContext):
    money_per, coins_per = await _unit_price()
    have = await _materials(call.from_user.id)
    await state.set_state(MaterialFSM.qty)
    await call.answer()
    await call.message.edit_text(
        f"✍️ <b>خرید مقدار دلخواه مصالح</b>\n\n"
        f"📦 موجودی فعلی: <b>{fmt(have)}</b> واحد\n"
        f"💵 هر واحد: <b>{fmt_money(money_per)}</b> پول\n\n"
        "تعداد واحد مورد نیاز را بنویسید (مثلاً 25000):\n"
        "برای انصراف /cancel",
        reply_markup=kb([back_row("g|matshop")]))


@router.message(MaterialFSM.qty)
async def buy_qty(message: Message, state: FSMContext):
    try:
        qty = int((message.text or "").strip().replace(",", "").replace("٬", ""))
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    if qty <= 0 or qty > 10_000_000:
        return await send_home(message, "❌ عدد باید بین ۱ تا ۱۰ میلیون باشد.")
    money_per, _coins_per = await _unit_price()
    total = money_per * qty
    user = await db.fetchone("SELECT money FROM users WHERE id=?",
                            (message.from_user.id,))
    if int((user or {}).get("money") or 0) < total:
        await state.clear()
        return await send_home(
            message,
            f"❌ بودجه کافی نیست.\n💰 نیاز: <b>{fmt_money(total)}</b>\n"
            f"💰 خزانه: <b>{fmt_money(int((user or {}).get('money') or 0))}</b>")
    await state.clear()
    await db.execute("UPDATE users SET money=money-? WHERE id=?",
                     (total, message.from_user.id))
    await db.execute("UPDATE states SET materials=COALESCE(materials,0)+? WHERE user_id=?",
                     (qty, message.from_user.id))
    have = await _materials(message.from_user.id)
    await send_home(
        message,
        f"✅ <b>خرید مصالح انجام شد!</b>\n\n"
        f"📦 اضافه شد: <b>{fmt(qty)}</b> واحد\n"
        f"💰 هزینه: <b>{fmt_money(total)}</b>\n"
        f"📦 موجودی جدید: <b>{fmt(have)}</b> واحد",
        reply_markup=kb(_shop_rows()))

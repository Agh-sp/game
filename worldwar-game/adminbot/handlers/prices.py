"""قیمت‌ها — تغییر سریع قیمت کشورها، قیمت سکه شاهی و نرخ تبدیل."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import kb
from adminbot.tools import log_action
from core.db import db, get_setting, set_setting
from core.utils import fmt

router = Router()


class PriceFSM(StatesGroup):
    country_price = State()
    coin_price = State()
    coin_rate = State()


async def _prices_payload() -> dict:
    coin_price = await get_setting("coin_price_toman", "1000")
    coin_rate = await get_setting("coins_to_money_rate", "5000000")
    countries = await db.fetchall(
        "SELECT * FROM countries WHERE is_active=1 ORDER BY is_special DESC, name LIMIT 50")
    lines = ["💵 <b>مدیریت قیمت‌ها</b>\n",
             f"🪙 قیمت هر سکه شاهی: <b>{fmt(coin_price)}</b> تومان",
             f"🔄 نرخ تبدیل هر سکه به پول بازی: <b>{fmt(coin_rate)}</b>\n",
             "🏳 <b>قیمت کشورهای ویژه (سکه شاهی):</b>"]
    buttons = [
        [("🪙 قیمت سکه شاهی", "a|prcoin")],
        [("🔄 نرخ تبدیل سکه", "a|prrate")],
    ]
    for c in countries:
        if c["is_special"]:
            lines.append(f"• {c['flag']} {c['name']}: {fmt(c['coin_price'])} سکه "
                         f"({fmt(c['toman_price'])} تومان)")
            buttons.append([(f"{c['flag']} {c['name']} — {fmt(c['coin_price'])} سکه",
                             f"a|prcnt|{c['id']}")])
    buttons.append([("◀️ بازگشت", "a|root")])
    return {"text": "\n".join(lines), "reply_markup": kb(buttons)}


@router.message(Command("prices"))
async def cmd_prices(message: Message, perms: set):
    if not has(perms, "economy"):
        return await message.answer("⛔️ دسترسی ندارید")
    await message.answer(**await _prices_payload())


@router.callback_query(F.data == "a|prices")
async def prices_menu(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    payload = await _prices_payload()
    await call.answer()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data.startswith("a|prcnt|"))
async def country_price_edit(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "countries"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    cid = int(call.data.split("|")[2])
    c = await db.fetchone("SELECT * FROM countries WHERE id=?", (cid,))
    if not c:
        return await call.answer("یافت نشد", show_alert=True)
    await state.set_state(PriceFSM.country_price)
    await state.update_data(country_id=cid)
    await call.answer()
    await call.message.edit_text(
        f"🏳 قیمت «{c['flag']} {c['name']}»:\n"
        f"🪙 فعلی: {fmt(c['coin_price'])} سکه | 💳 {fmt(c['toman_price'])} تومان\n\n"
        "قیمت جدید به <b>سکه شاهی</b> را بنویسید (قیمت تومان خودکار ×۱۰۰٬۰۰۰ می‌شود):\n"
        " برای انصراف /cancel")


@router.message(PriceFSM.country_price)
async def country_price_input(message: Message, state: FSMContext):
    try:
        price = int((message.text or "").replace(",", "").strip())
    except ValueError:
        return await message.answer("❌ فقط عدد بفرستید.")
    if price < 0:
        return await message.answer("❌ عدد نمی‌تواند منفی باشد.")
    data = await state.get_data()
    await state.clear()
    mult = int(await get_setting("special_toman_multiplier", "100000"))
    await db.execute("UPDATE countries SET coin_price=?, toman_price=? WHERE id=?",
                     (price, price * mult, data["country_id"]))
    await log_action(message.from_user.id, "قیمت‌ها", f"کشور#{data['country_id']} → {price} سکه")
    await message.answer(f"✅ قیمت کشور به <b>{fmt(price)} سکه</b> تغییر کرد.")
    payload = await _prices_payload()
    await message.answer(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data == "a|prcoin")
async def coin_price_edit(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.set_state(PriceFSM.coin_price)
    await call.answer()
    await call.message.edit_text(
        f"🪙 قیمت فروش هر سکه شاهی فعلی: <b>{fmt(await get_setting('coin_price_toman', '1000'))}</b> تومان\n\n"
        "قیمت جدید (تومان) را بنویسید:\n برای انصراف /cancel")


@router.message(PriceFSM.coin_price)
async def coin_price_input(message: Message, state: FSMContext):
    try:
        price = int((message.text or "").replace(",", "").strip())
    except ValueError:
        return await message.answer("❌ فقط عدد بفرستید.")
    if price <= 0:
        return await message.answer("❌ عدد باید مثبت باشد.")
    await state.clear()
    await set_setting("coin_price_toman", str(price))
    await log_action(message.from_user.id, "قیمت‌ها", f"سکه شاهی → {price} تومان")
    await message.answer(f"✅ قیمت هر سکه شاهی به <b>{fmt(price)} تومان</b> تغییر کرد.")
    payload = await _prices_payload()
    await message.answer(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data == "a|prrate")
async def coin_rate_edit(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.set_state(PriceFSM.coin_rate)
    await call.answer()
    await call.message.edit_text(
        f"🔄 نرخ تبدیل فعلی: هر سکه = <b>{fmt(await get_setting('coins_to_money_rate', '5000000'))}</b> پول بازی\n\n"
        "نرخ جدید را بنویسید:\n برای انصراف /cancel")


@router.message(PriceFSM.coin_rate)
async def coin_rate_input(message: Message, state: FSMContext):
    try:
        rate = int((message.text or "").replace(",", "").strip())
    except ValueError:
        return await message.answer("❌ فقط عدد بفرستید.")
    if rate <= 0:
        return await message.answer("❌ عدد باید مثبت باشد.")
    await state.clear()
    await set_setting("coins_to_money_rate", str(rate))
    await log_action(message.from_user.id, "قیمت‌ها", f"نرخ تبدیل → {rate}")
    await message.answer(f"✅ نرخ تبدیل به <b>{fmt(rate)}</b> تغییر کرد.")
    payload = await _prices_payload()
    await message.answer(payload["text"], reply_markup=payload["reply_markup"])

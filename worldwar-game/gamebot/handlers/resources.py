"""♻️ فروش منابع — برق، آب، گاز، غذا و نفت به بازار جهانی و تبدیل به پول.

بازیکن می‌تواند موجودی انبار خود را (که از تیک درآمد و مازاد تولید پر می‌شود)
با نرخ بازار بفروشد و پول میلیونی بگیرد. نرخ‌ها از پنل ادمین قابل تغییرند
(`res_price_*`) و با ضریب ارتقای بازیکن رشد می‌کنند.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.income import growth_multiplier
from core.utils import fmt, fmt_money
from gamebot.common import back_row, kb, send_home

router = Router()


class ResFSM(StatesGroup):
    qty = State()


# کلید → (برچسب, ایموجی, ستون states, کلید تنظیم قیمت, قیمت پیش‌فرض هر واحد)
RESOURCES = {
    "power": ("برق", "⚡", "energy", "res_price_power", 60),
    "water": ("آب", "💧", "water", "res_price_water", 40),
    "gas": ("گاز", "🔥", "gas", "res_price_gas", 90),
    "food": ("غذا", "🍞", "food", "res_price_food", 120),
    "oil": ("نفت (بشکه)", "🛢", "oil_stock", "res_price_oil", 25_000),
    "materials": ("مصالح", "🧱", "materials", "res_price_materials", 9_000),
}


async def _stock(user_id: int, column: str) -> int:
    row = await db.fetchone(f"SELECT COALESCE({column},0) v FROM states WHERE user_id=?",
                            (user_id,))
    return int((row or {}).get("v") or 0)


async def _price(key: str) -> int:
    label, emoji, column, setting_key, default = RESOURCES[key]
    try:
        return max(1, int(float(await get_setting(setting_key, str(default)))))
    except (TypeError, ValueError):
        return default


async def resource_lines(user_id: int) -> list[str]:
    """خطوط وضعیت منابع و ارزش فروش آن‌ها."""
    growth = await growth_multiplier(user_id)
    mult = growth["mult"]
    lines = [f"📈 ضریب ارتقای شما: <b>×{mult}</b> (روی قیمت فروش اثر دارد)\n"]
    total = 0
    for key, (label, emoji, column, _sk, _d) in RESOURCES.items():
        have = await _stock(user_id, column)
        price = await _price(key)
        value = int(have * price * mult)
        total += value
        lines.append(f"{emoji} <b>{label}</b>: {fmt(have)} واحد — "
                     f"ارزش کل: <b>{fmt_money(value)}</b>")
    lines.append(f"\n💵 <b>ارزش کل منابع شما: {fmt_money(total)}</b>")
    return lines


def resource_rows() -> list:
    rows = []
    items = list(RESOURCES.items())
    for i in range(0, len(items), 2):
        pair = items[i:i + 2]
        rows.append([(f"{v[1]} فروش {v[0]}", f"g|ressell|{k}") for k, v in pair])
    rows.append(back_row("g|mg"))
    return rows


@router.callback_query(F.data == "g|res")
async def resource_shop(call: CallbackQuery):
    lines = ["♻️ <b>فروش منابع به بازار جهانی</b>\n"]
    lines += await resource_lines(call.from_user.id)
    lines.append("\n💡 منابع از تیک درآمد (هر ۵ دقیقه) و مازاد تولید ساختمان‌ها پر می‌شوند. "
                 "برای فروش، روی منبع بزنید.")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(resource_rows()))


@router.callback_query(F.data.startswith("g|ressell|"))
async def resource_sell_menu(call: CallbackQuery, state: FSMContext):
    key = call.data.split("|")[2]
    if key not in RESOURCES:
        return await call.answer("منبع یافت نشد", show_alert=True)
    label, emoji, column, _sk, _d = RESOURCES[key]
    have = await _stock(call.from_user.id, column)
    price = await _price(key)
    mult = (await growth_multiplier(call.from_user.id))["mult"]
    full = int(have * price * mult)
    if have <= 0:
        return await call.answer(f"❌ {label} در انبار ندارید", show_alert=True)
    await state.update_data(res_key=key)
    await state.set_state(ResFSM.qty)
    await call.answer()
    rows = [
        [(f"📦 فروش همه ({fmt(have)})", f"g|resgo|{key}|{have}")],
        [(f"½ فروش نصف ({fmt(have // 2)})", f"g|resgo|{key}|{max(1, have // 2)}")],
        [("✍️ تعداد دلخواه", f"g|resask|{key}")],
        back_row("g|res"),
    ]
    await call.message.edit_text(
        f"{emoji} <b>فروش {label}</b>\n\n"
        f"📦 موجودی انبار: <b>{fmt(have)}</b> واحد\n"
        f"💵 قیمت هر واحد: <b>{fmt_money(price)}</b>\n"
        f"📈 ضریب ارتقا: <b>×{mult}</b>\n"
        f"💰 ارزش کل موجودی: <b>{fmt_money(full)}</b>\n\n"
        "چقدر می‌فروشید؟",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|resask|"))
async def resource_ask_qty(call: CallbackQuery, state: FSMContext):
    key = call.data.split("|")[2]
    if key not in RESOURCES:
        return await call.answer("منبع یافت نشد", show_alert=True)
    label, emoji, column, _sk, _d = RESOURCES[key]
    have = await _stock(call.from_user.id, column)
    await state.update_data(res_key=key)
    await state.set_state(ResFSM.qty)
    await call.answer()
    await call.message.edit_text(
        f"{emoji} <b>فروش {label}</b>\n\n"
        f"📦 موجودی: <b>{fmt(have)}</b> واحد\n\n"
        "تعداد واحد برای فروش را بنویسید (مثلاً 50000):\n برای انصراف /cancel",
        reply_markup=kb([back_row("g|res")]))


async def _sell(user_id: int, key: str, qty: int) -> tuple[bool, str]:
    label, emoji, column, _sk, _d = RESOURCES[key]
    have = await _stock(user_id, column)
    if qty <= 0:
        return False, "❌ تعداد باید مثبت باشد."
    if qty > have:
        return False, f"❌ موجودی کافی نیست.\n📦 {label}: {fmt(have)} واحد"
    price = await _price(key)
    mult = (await growth_multiplier(user_id))["mult"]
    gain = int(qty * price * mult)
    await db.execute(f"UPDATE states SET {column}=MAX(0, COALESCE({column},0)-?) WHERE user_id=?",
                     (qty, user_id))
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (gain, user_id))
    row = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    return True, (
        f"✅ <b>{fmt(qty)} واحد {label} فروخته شد</b>\n\n"
        f"💵 دریافتی: <b>{fmt_money(gain)}</b>\n"
        f"💵 قیمت هر واحد: {fmt_money(price)} × ضریب {mult}\n"
        f"💰 خزانه شما: <b>{fmt_money(int((row or {}).get('money') or 0))}</b>")


@router.callback_query(F.data.startswith("g|resgo|"))
async def resource_sell_go(call: CallbackQuery, state: FSMContext):
    _, _, key, qty_s = call.data.split("|")
    try:
        qty = int(qty_s)
    except ValueError:
        return await call.answer("عدد نامعتبر", show_alert=True)
    ok, msg = await _sell(call.from_user.id, key, qty)
    await state.clear()
    if not ok:
        return await call.answer(msg[:190], show_alert=True)
    await call.answer("✅ فروش انجام شد")
    lines = [msg, "", "♻️ <b>فروش منابع به بازار جهانی</b>\n"]
    lines += await resource_lines(call.from_user.id)
    await call.message.edit_text("\n".join(lines), reply_markup=kb(resource_rows()))


@router.message(ResFSM.qty)
async def resource_sell_qty(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("res_key")
    if key not in RESOURCES:
        await state.clear()
        return await send_home(message, "❌ منبع نامعتبر است.")
    try:
        qty = int((message.text or "").strip().replace(",", "").replace("٬", ""))
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    ok, msg = await _sell(message.from_user.id, key, qty)
    if not ok:
        return await send_home(message, msg)
    await state.clear()
    lines = [msg, "", "♻️ <b>فروش منابع به بازار جهانی</b>\n"]
    lines += await resource_lines(message.from_user.id)
    await send_home(message, "\n".join(lines), reply_markup=kb(resource_rows()))

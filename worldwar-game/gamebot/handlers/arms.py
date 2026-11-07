"""🛒 بازار تسلیحات بین‌المللی — خرید و فروش تجهیزات بین کشورها.

کاربر از «🏛 مدیریت کشور» → «🛒 بازار تسلیحات» وارد می‌شود.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core import arms
from core.db import db
from core.utils import fmt, fmt_money
from gamebot.common import back_row, kb, send_home

router = Router()


class ArmsFSM(StatesGroup):
    quantity = State()
    price = State()


async def _market_rows(user_id: int) -> list:
    """دکمه‌های بازار: هر آگهی + آگهی‌های من."""
    rows = []
    for d in (await arms.market())[:8]:
        if int(d["seller_id"]) == int(user_id):
            continue
        total = int(d["quantity"]) * int(d["unit_price"])
        rows.append([(f"🛍 {d['emoji']} {d['name']} ×{fmt(d['quantity'])} — "
                      f"{fmt_money(total)}", f"g|armsbuy|{d['id']}")])
    mine = await arms.my_listings(user_id)
    for d in mine[:4]:
        rows.append([(f"↩️ لغو {d['emoji']} {d['name']} ×{fmt(d['quantity'])}",
                      f"g|armscancel|{d['id']}")])
    rows.append([("📤 گذاشتن تجهیزات برای فروش", "g|armssell")])
    rows.append(back_row("g|mg"))
    return rows


@router.callback_query(F.data == "g|arms")
async def arms_menu(call: CallbackQuery):
    await call.answer()
    text = await arms.market_text(call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb(await _market_rows(call.from_user.id)))


@router.callback_query(F.data == "g|armssell")
async def arms_sell_list(call: CallbackQuery):
    stock = await arms.my_stock(call.from_user.id)
    if not stock:
        return await call.answer("❌ هیچ تجهیزاتی برای فروش ندارید", show_alert=True)
    rows = []
    for it in stock[:12]:
        rows.append([(f"{it['emoji']} {it['name']} ×{fmt(it['quantity'])}",
                      f"g|armsitem|{it['id']}")])
    rows.append(back_row("g|arms"))
    await call.answer()
    await call.message.edit_text(
        "📤 <b>کدام تجهیزات را می‌فروشید؟</b>\n\n"
        "💡 تجهیزات تا زمان فروش در بازار بلوکه می‌شوند و از توان نظامی شما کم می‌شوند.",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|armsitem|"))
async def arms_pick_item(call: CallbackQuery, state: FSMContext):
    eid = int(call.data.split("|")[2])
    row = await db.fetchone(
        "SELECT a.quantity, e.name, e.emoji, e.price_money FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id WHERE a.user_id=? AND a.item_type='equipment' "
        "AND a.item_id=?", (call.from_user.id, eid))
    if not row:
        return await call.answer("تجهیزات یافت نشد", show_alert=True)
    await state.set_state(ArmsFSM.quantity)
    await state.update_data(arms_eid=eid)
    await call.answer()
    await call.message.edit_text(
        f"{row['emoji']} <b>{row['name']}</b>\n\n"
        f"📦 موجودی شما: <b>{fmt(row['quantity'])}</b> واحد\n"
        f"💵 قیمت پایهٔ خرید: {fmt_money(row['price_money'] or 0)}\n\n"
        "چند واحد برای فروش بگذارید؟ (یک عدد بفرستید)\n برای انصراف /cancel",
        reply_markup=kb([back_row("g|armssell")]))


@router.message(ArmsFSM.quantity)
async def arms_quantity(message: Message, state: FSMContext):
    try:
        qty = int((message.text or "").strip().replace(",", "").replace("٬", ""))
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    data = await state.get_data()
    eid = data.get("arms_eid")
    row = await db.fetchone(
        "SELECT a.quantity, e.name, e.emoji, e.price_money FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id WHERE a.user_id=? AND a.item_type='equipment' "
        "AND a.item_id=?", (message.from_user.id, eid))
    if not row:
        await state.clear()
        return await send_home(message, "❌ تجهیزات یافت نشد.")
    if qty <= 0 or qty > int(row["quantity"]):
        return await send_home(message, f"❌ تعداد باید بین ۱ تا {fmt(row['quantity'])} باشد.")
    await state.update_data(arms_qty=qty)
    await state.set_state(ArmsFSM.price)
    suggested = max(1, int((row["price_money"] or 0) * 0.9)) or 1_000_000
    await send_home(
        message,
        f"💰 <b>قیمت هر واحد</b> را به پول بازی بنویسید.\n\n"
        f"💡 قیمت پیشنهادی: <b>{fmt_money(suggested)}</b>\n"
        "(می‌توانید بالاتر یا پایین‌تر بگذارید — بازار آزاد است)\n"
        "برای انصراف /cancel")


@router.message(ArmsFSM.price)
async def arms_price(message: Message, state: FSMContext):
    try:
        price = int((message.text or "").strip().replace(",", "").replace("٬", ""))
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    data = await state.get_data()
    await state.clear()
    ok, msg = await arms.list_item(message.from_user.id, int(data.get("arms_eid") or 0),
                                   int(data.get("arms_qty") or 0), price)
    if not ok:
        return await send_home(message, msg)
    await send_home(message, msg,
                    reply_markup=kb([[("🛒 بازار تسلیحات", "g|arms")], back_row("g|mg")]))


@router.callback_query(F.data.startswith("g|armsbuy|"))
async def arms_buy(call: CallbackQuery):
    deal_id = int(call.data.split("|")[2])
    ok, msg = await arms.buy(call.from_user.id, deal_id)
    if not ok:
        return await call.answer(msg[:190], show_alert=True)
    await call.answer("✅ خرید انجام شد")
    await call.message.edit_text(msg + "\n\n" + await arms.market_text(call.from_user.id),
                                 reply_markup=kb(await _market_rows(call.from_user.id)))


@router.callback_query(F.data.startswith("g|armscancel|"))
async def arms_cancel(call: CallbackQuery):
    deal_id = int(call.data.split("|")[2])
    ok, msg = await arms.cancel(call.from_user.id, deal_id)
    if not ok:
        return await call.answer(msg[:190], show_alert=True)
    await call.answer("↩️ لغو شد")
    await call.message.edit_text(msg + "\n\n" + await arms.market_text(call.from_user.id),
                                 reply_markup=kb(await _market_rows(call.from_user.id)))

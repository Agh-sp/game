"""مدیریت کشور — بخش نفت: دکل، مخزن، اکتشاف و فروش."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import get_country
from core.oil import create_offer, explore, oil_menu_data, offers_text
from core.treaties import find_treaty
from core.utils import fmt
from gamebot.common import back_row, kb, send_home, dm

router = Router()


class OilFSM(StatesGroup):
    sell_barrels = State()
    sell_price = State()
    explore_confirm = State()


async def _oil_menu(call: CallbackQuery):
    if await get_setting("sec_oil", "1") != "1":
        await call.answer("بخش نفت توسط ادمین خاموش شده است", show_alert=True)
        return
    d = await oil_menu_data(call.from_user.id)
    text = (
        "🛢 <b>بخش نفت</b>\n\n"
        f"⛏ مخزن زیرزمینی کشور: <b>{fmt(d['reserve'])}</b> بشکه\n"
        f"🏭 انبار نفت شما: <b>{fmt(d['stock'])}</b> بشکه\n"
        f"🛢 دکل‌های نفتی: <b>{d['rigs']}</b> (هر دکل {fmt(d['per_rig'])} بشکه در هر تیک ۳۰ دقیقه‌ای)\n"
        f"🎲 نفت‌خیزی (شانس اکتشاف): <b>{round(d['richness'])}٪</b>\n\n"
        "💡 وقتی مخزن زیرزمینی تمام شد، با «اکتشاف نفتی» و بر اساس درصد نفت‌خیزی "
        "شانس پیدا کردن ذخیره جدید دارید. نفت را به کشورهای دیگر بفروشید."
    )
    rows = [
        [("🏗 ساخت دکل نفتی", "g|oilrig")],
        [("🔍 اکتشاف نفتی", "g|oilexp")],
        [("🛒 فروش نفت به کشورها", "g|oilsell")],
        [("📜 عرضه‌های نفت", "g|oillo")],
        back_row("g|ppl"),
    ]
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|oil")
async def oil_menu(call: CallbackQuery):
    await _oil_menu(call)


@router.callback_query(F.data == "g|oilrig")
async def oil_rig_build(call: CallbackQuery):
    """ساخت دکل نفتی از همان جریان خرید ساختمان مردم."""
    b = await db.fetchone("SELECT * FROM buildings WHERE name='دکل نفتی'")
    if not b:
        return await call.answer("ساختمان دکل نفتی یافت نشد", show_alert=True)
    call.data = f"g|buy|{b['id']}"
    from gamebot.handlers.people import buy_building
    await buy_building(call)


@router.callback_query(F.data == "g|oilexp")
async def oil_explore(call: CallbackQuery):
    cost = int(await get_setting("oil_exploration_cost", "50000000"))
    d = await oil_menu_data(call.from_user.id)
    await call.answer()
    await call.message.edit_text(
        f"🔍 <b>اکتشاف نفتی</b>\n\n"
        f"💰 هزینه: <b>{fmt(cost)}</b>\n"
        f"🎲 شانس موفقیت (نفت‌خیزی کشور): <b>{round(d['richness'])}٪</b>\n"
        f"🛢 در صورت موفقیت: <b>{fmt(int(await get_setting('oil_exploration_add', '2000000000')))}</b> "
        "بشکه به مخزن اضافه می‌شود.\n\nتأیید می‌کنید؟",
        reply_markup=kb([
            [("✅ پرداخت و اکتشاف", "g|oilexpok")],
            back_row("g|oil"),
        ]))


@router.callback_query(F.data == "g|oilexpok")
async def oil_explore_go(call: CallbackQuery):
    ok, msg = await explore(call.from_user.id)
    await call.answer("✅" if ok else "❌")
    await send_home(call.message, msg)
    await _oil_menu(call)


@router.callback_query(F.data == "g|oilsell")
async def oil_sell_start(call: CallbackQuery, state: FSMContext):
    d = await oil_menu_data(call.from_user.id)
    if d["stock"] <= 0:
        return await call.answer("انبار نفت شما خالی است!", show_alert=True)
    await state.set_state(OilFSM.sell_barrels)
    await call.answer()
    await call.message.edit_text(
        f"🛒 <b>فروش نفت</b>\nانبار شما: {fmt(d['stock'])} بشکه\n\n"
        "چند بشکه بفروشید؟\n برای انصراف /cancel")


@router.message(OilFSM.sell_barrels)
async def oil_sell_barrels(message: Message, state: FSMContext):
    try:
        barrels = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد بفرستید.")
    d = await oil_menu_data(message.from_user.id)
    if barrels <= 0 or barrels > d["stock"]:
        return await send_home(message, f"❌ عدد باید بین ۱ تا {fmt(d['stock'])} باشد.")
    await state.update_data(barrels=barrels)
    await state.set_state(OilFSM.sell_price)
    await send_home(message, 
        "قیمت فروش را بنویسید (پول یا سکه):\n"
        "• فقط عدد = قیمت به پول\n"
        "• عدد + حرف c = قیمت به سکه شاهی (مثل 5c)\n برای انصراف /cancel")


@router.message(OilFSM.sell_price)
async def oil_sell_price(message: Message, state: FSMContext):
    text = (message.text or "").strip().lower().replace("،", "")
    coins = text.endswith("c") or text.endswith("سکه")
    if coins:
        text = text[:-1].strip() or "0"
    try:
        price = int(text.replace(",", ""))
    except (ValueError, TypeError):
        return await send_home(message, "❌ فرمت مثال: 5000000 یا 5c")
    if price <= 0:
        return await send_home(message, "❌ قیمت باید مثبت باشد.")
    data = await state.get_data()
    await state.clear()
    from core.economy import sub_asset
    st = await db.fetchone("SELECT oil_stock FROM states WHERE user_id=?", (message.from_user.id,))
    if (st or {}).get("oil_stock", 0) < data["barrels"]:
        return await send_home(message, "❌ موجودی انبار کافی نیست.")
    await db.execute("UPDATE states SET oil_stock=oil_stock-? WHERE user_id=?",
                     (data["barrels"], message.from_user.id))
    oid = await create_offer(message.from_user.id, data["barrels"],
                             0 if coins else price, price if coins else 0)
    price_txt = f"🪙 {fmt(price)} سکه شاهی" if coins else f"💰 {fmt(price)}"
    await send_home(message, f"✅ عرضه #{oid} ثبت شد: {fmt(data['barrels'])} بشکه ← {price_txt}")
    text_out, rows = await offers_text(message.from_user.id)
    rows.append(back_row("g|oil"))
    await send_home(message, text_out, reply_markup=kb(rows))


@router.callback_query(F.data == "g|oillo")
async def oil_offers_menu(call: CallbackQuery):
    text, rows = await offers_text(call.from_user.id)
    rows.append([("🛒 فروش نفت", "g|oilsell")])
    rows.append(back_row("g|oil"))
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|oilbuy|"))
async def oil_buy(call: CallbackQuery):
    oid = int(call.data.split("|")[2])
    o = await db.fetchone("SELECT * FROM oil_offers WHERE id=? AND status='open'", (oid,))
    if not o or o["seller_id"] == call.from_user.id:
        return await call.answer("عرضه در دسترس نیست", show_alert=True)
    buyer = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if o["price_coins"]:
        if buyer["royal_coins"] < o["price_coins"]:
            return await call.answer("🪙 سکه شاهی کافی ندارید", show_alert=True)
        await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?",
                         (o["price_coins"], buyer["id"]))
    else:
        if buyer["money"] < o["price_money"]:
            return await call.answer("💰 پول کافی ندارید", show_alert=True)
        await db.execute("UPDATE users SET money=money-? WHERE id=?",
                         (o["price_money"], buyer["id"]))
    await db.execute("UPDATE states SET oil_stock=oil_stock+? WHERE user_id=?",
                     (o["barrels"], buyer["id"]))
    await db.execute("UPDATE oil_offers SET status='done', buyer_id=? WHERE id=?", (buyer["id"], oid))
    b_c, s_c = await get_country(buyer["id"]), await get_country(o["seller_id"])
    from core.events import log_event
    await log_event("oil", f"{b_c['name']} {fmt(o['barrels'])} بشکه نفت از {s_c['name']} خرید")
    try:
        await dm(call.bot, 
            o["seller_id"],
            f"🛢 عرضه نفت شما فروخته شد! {fmt(o['barrels'])} بشکه به {b_c['flag']} {b_c['name']} رفت.")
    except Exception:
        pass
    await call.answer("✅ خرید انجام شد")
    await oil_offers_menu(call)


@router.callback_query(F.data.startswith("g|oilcan|"))
async def oil_cancel(call: CallbackQuery):
    oid = int(call.data.split("|")[2])
    o = await db.fetchone(
        "SELECT * FROM oil_offers WHERE id=? AND seller_id=? AND status='open'",
        (oid, call.from_user.id))
    if not o:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("UPDATE oil_offers SET status='cancelled' WHERE id=?", (oid,))
    await db.execute("UPDATE states SET oil_stock=oil_stock+? WHERE user_id=?",
                     (o["barrels"], call.from_user.id))
    await call.answer("✅ عرضه لغو و نفت به انبار برگشت")
    await oil_offers_menu(call)

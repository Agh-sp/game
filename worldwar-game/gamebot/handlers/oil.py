"""مدیریت کشور — بخش نفت: دکل، مخزن، اکتشاف و فروش."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import get_country
from core.oil import create_offer, explore, oil_menu_data, offers_text
from core.treaties import find_treaty
from core.utils import fmt, fmt_money
from gamebot.common import back_row, kb, send_home, dm

router = Router()


class OilFSM(StatesGroup):
    sell_barrels = State()
    sell_price = State()
    explore_confirm = State()
    rig_qty = State()


async def _oil_menu(call: CallbackQuery):
    if await get_setting("sec_oil", "1") != "1":
        await call.answer("بخش نفت توسط ادمین خاموش شده است", show_alert=True)
        return
    from core.oil import (ensure_business, income_estimate, level_max, per_rig_barrels,
                          upgrade_cost)
    d = await oil_menu_data(call.from_user.id)
    biz = await ensure_business(call.from_user.id)
    level = int(biz.get("level") or 1)
    cap = await level_max()
    est = await income_estimate(call.from_user.id)
    nxt_cost = await upgrade_cost(level) if level < cap else 0
    per_rig = await per_rig_barrels(call.from_user.id)
    auto = int(biz.get("auto_sell") or 0)
    minutes = int(float(await get_setting("oil_auto_sell_minutes", "10")))
    text = (
        "🛢 <b>بخش نفت و تجارت خودکار</b>\n\n"
        f"⛏ مخزن زیرزمینی کشور: <b>{fmt(d['reserve'])}</b> بشکه\n"
        f"🏭 انبار نفت شما: <b>{fmt(d['stock'])}</b> بشکه\n"
        f"🛢 دکل‌های نفتی: <b>{d['rigs']}</b> (هر دکل {fmt(per_rig)} بشکه در هر تیک ۳۰ دقیقه‌ای)\n"
        f"🛠 سطح تجهیزات استخراج: <b>{level}</b>/{cap}\n"
        + (f"➡️ هزینهٔ ارتقای بعدی: <b>{fmt_money(nxt_cost)}</b>\n" if nxt_cost else "🏆 حداکثر سطح\n")
        + f"🤖 تجارت خودکار: <b>{'روشن ✅' if auto else 'خاموش ⏸'}</b>"
        f" — درآمد هر {minutes} دقیقه: <b>{est['income_millions']} میلیون تومان</b>\n"
        f"💵 پایهٔ نفتی کشور شما: <b>{est['base_millions']} میلیون</b> در هر فروش کامل\n"
        + (f"📊 مجموع درآمد نفت تاکنون: <b>{fmt_money(int(biz.get('total_income') or 0))}</b>"
           f" ({int(biz.get('sales') or 0)} فروش)\n" if int(biz.get("sales") or 0) else "")
        + f"🎲 نفت‌خیزی (شانس اکتشاف): <b>{round(d['richness'])}٪</b>\n\n"
        "💡 استخراج با دکل انجام می‌شود؛ با ارتقای تجهیزات، هم بشکهٔ بیشتری استخراج می‌شود "
        "و هم درآمد فروش بالاتر می‌رود (هر سطح گران‌تر از قبلی)."
    )
    rows = [
        [("🛠 ارتقای تجهیزات استخراج", "g|oilup")],
        [(("🤖 خاموش‌کردن تجارت خودکار" if auto else "🤖 روشن‌کردن تجارت خودکار"), "g|oilauto")],
        [("🏗 ساخت دکل نفتی", "g|oilrig")],
        [("🔍 اکتشاف نفتی", "g|oilexp")],
        [("🛒 فروش نفت به کشورها", "g|oilsell")],
        [("📜 عرضه‌های نفت", "g|oillo")],
        back_row("g|mg"),
    ]
    try:
        await call.answer()
    except Exception:
        pass
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|oil")
async def oil_menu(call: CallbackQuery):
    await _oil_menu(call)


@router.callback_query(F.data == "g|oilrig")
async def oil_rig_menu(call: CallbackQuery):
    """منوی اختصاصی و روان ساخت دکل نفتی با بررسی آنی بودجه و مصالح."""
    b = await db.fetchone("SELECT * FROM buildings WHERE name='دکل نفتی'")
    d = await oil_menu_data(call.from_user.id)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    state = await db.fetchone("SELECT * FROM states WHERE user_id=?", (call.from_user.id,))
    
    cost_per_unit = b.get("cost_money") or 12_000_000 if b else 12_000_000
    mat_per_unit = 10
    
    user_money = (user.get("money") if user else 0) or 0
    user_mat = (state.get("materials") if state else 0) or 0
    current_rigs = d.get("rigs", 0)
    per_rig = d.get("per_rig", 500)
    
    text = (
        "🏗 <b>ساخت دکل نفتی</b> 🛢\n\n"
        f"📦 تعداد دکل‌های فعلی شما: <b>{current_rigs}</b> عدد\n"
        f"⚡️ استخراج هر دکل: <b>+{fmt(per_rig)}</b> بشکه در هر دوره ۳۰ دقیقه‌ای\n\n"
        f"💰 هزینه هر دکل: <b>{fmt_money(cost_per_unit)}</b>\n"
        f"🧱 مصالح لازم هر دکل: <b>{mat_per_unit}</b> واحد\n\n"
        f"💳 بودجه فعلی شما: <b>{fmt_money(user_money)}</b>\n"
        f"🧱 مصالح آزاد شما: <b>{fmt(user_mat)}</b> واحد\n\n"
        "تعداد دکل مورد نظر برای ساخت را انتخاب کنید:"
    )
    rows = [
        [("🟢 ساخت ۱ دکل", "g|oilrigb|1"), ("🟢 ساخت ۵ دکل", "g|oilrigb|5")],
        [("🟢 ساخت ۱۰ دکل", "g|oilrigb|10"), ("✏️ تعداد دلخواه", "g|oilrigc")],
        back_row("g|oil"),
    ]
    try:
        await call.answer()
    except Exception:
        pass
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|oilrigb|"))
async def oil_rig_execute(call: CallbackQuery):
    qty = int(call.data.split("|")[2])
    await _do_build_rig(call, qty)


@router.callback_query(F.data == "g|oilrigc")
async def oil_rig_custom_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(OilFSM.rig_qty)
    try:
        await call.answer()
    except Exception:
        pass
    await call.message.edit_text(
        "🏗 <b>ساخت دکل نفتی (تعداد دلخواه)</b>\n\n"
        "تعداد دکل مورد نظر را به عدد بنویسید (مثلاً 3 یا 20):\n"
        "برای انصراف /cancel را ارسال کنید.",
        reply_markup=kb([back_row("g|oilrig")]),
    )


@router.message(OilFSM.rig_qty)
async def oil_rig_custom_input(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً فقط یک عدد معتبر ارسال کنید.")
    if qty <= 0 or qty > 500:
        return await send_home(message, "❌ تعداد باید بین ۱ تا ۵۰۰ باشد.")
    await state.clear()
    await _do_build_rig(message, qty)


async def _do_build_rig(target_event, qty: int):
    user_id = target_event.from_user.id
    b = await db.fetchone("SELECT * FROM buildings WHERE name='دکل نفتی'")
    cost_per_unit = b.get("cost_money") or 12_000_000 if b else 12_000_000
    bid = b["id"] if b else 9
    mat_per_unit = 10
    total_cost = cost_per_unit * qty
    total_mat = mat_per_unit * qty
    
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    state = await db.fetchone("SELECT materials FROM states WHERE user_id=?", (user_id,))
    
    user_money = (user.get("money") if user else 0) or 0
    user_mat = (state.get("materials") if state else 0) or 0
    
    is_call = isinstance(target_event, CallbackQuery)
    
    if user_mat < total_mat:
        msg = f"❌ <b>مصالح کافی ندارید!</b>\nبرای ساخت {qty} دکل به {total_mat} مصالح نیاز دارید (موجودی: {user_mat})."
        if is_call:
            await target_event.answer(f"❌ مصالح کافی نیست! نیاز: {total_mat} (موجودی: {user_mat})", show_alert=True)
            return
        return await send_home(target_event, msg)
        
    if user_money < total_cost:
        msg = f"❌ <b>بودجه کافی ندارید!</b>\nبرای ساخت {qty} دکل به {fmt_money(total_cost)} پول نیاز دارید (موجودی: {fmt_money(user_money)})."
        if is_call:
            await target_event.answer(f"❌ بودجه کافی نیست! نیاز: {fmt_money(total_cost)}", show_alert=True)
            return
        return await send_home(target_event, msg)
        
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (total_cost, user_id))
    await db.execute("UPDATE states SET materials=materials-? WHERE user_id=?", (total_mat, user_id))
    from core.economy import add_asset, bump_progress
    await add_asset(user_id, "building", bid, qty)
    await bump_progress(user_id, "built", qty)
    
    if is_call:
        await target_event.answer(f"✅ {qty} دکل نفتی ساخته شد!")
        await _oil_menu(target_event)
    else:
        await send_home(target_event, f"✅ تعداد <b>{qty} دکل نفتی</b> با موفقیت احداث شد!\n🧱 مصالح مصرفی: {total_mat} واحد\n💰 هزینه: {fmt_money(total_cost)}")



@router.callback_query(F.data == "g|oilexp")
async def oil_explore(call: CallbackQuery):
    cost = int(await get_setting("oil_exploration_cost", "50000000"))
    d = await oil_menu_data(call.from_user.id)
    await call.answer()
    await call.message.edit_text(
        f"🔍 <b>اکتشاف نفتی</b>\n\n"
        f"💰 هزینه: <b>{fmt_money(cost)}</b>\n"
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
    price_txt = f"🪙 {fmt(price)} سکه شاهی" if coins else f"💰 {fmt_money(price)}"
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


@router.callback_query(F.data == "g|oilup")
async def oil_upgrade(call: CallbackQuery):
    from core.oil import (ensure_business, level_max, per_rig_barrels, upgrade_cost,
                          level_income_mult)
    biz = await ensure_business(call.from_user.id)
    level = int(biz.get("level") or 1)
    cap = await level_max()
    if level >= cap:
        await call.answer(f"🏆 تجهیزات شما در بالاترین سطح ({cap}) است", show_alert=True)
        return
    cost = await upgrade_cost(level)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (call.from_user.id,))
    money = int((user or {}).get("money") or 0)
    nxt = await upgrade_cost(level + 1) if level + 1 < cap else 0
    text = (
        f"🛠 <b>ارتقای تجهیزات استخراج نفت</b>\n\n"
        f"📈 سطح فعلی: <b>{level}</b>/{cap}\n"
        f"🛢 استخراج هر دکل: <b>{fmt(await per_rig_barrels(call.from_user.id))}</b> بشکه در هر دوره\n"
        f"💰 ضریب درآمد فروش: <b>×{round(await level_income_mult(level), 2)}</b>\n\n"
        f"⬆️ هزینهٔ ارتقا به سطح {level + 1}: <b>{fmt_money(cost)}</b>\n"
        f"💳 خزانه شما: <b>{fmt_money(money)}</b>\n"
        + (f"🔺 هزینهٔ مرحلهٔ بعد از آن: {fmt_money(nxt)} (هر سطح گران‌تر)\n" if nxt else "")
        + "\nتأیید می‌کنید؟",
    )
    rows = [[("✅ پرداخت و ارتقا", "g|oilupgo")], back_row("g|oil")]
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|oilupgo")
async def oil_upgrade_go(call: CallbackQuery):
    from core.oil import upgrade_business
    ok, msg = await upgrade_business(call.from_user.id)
    await call.answer("🛠" if ok else "❌")
    await send_home(call.message, msg)
    await _oil_menu(call)


@router.callback_query(F.data == "g|oilauto")
async def oil_auto_toggle(call: CallbackQuery):
    from core.oil import toggle_auto_sell
    ok, msg = await toggle_auto_sell(call.from_user.id)
    await call.answer("🤖" if ok else "❌")
    await send_home(call.message, msg)
    await _oil_menu(call)

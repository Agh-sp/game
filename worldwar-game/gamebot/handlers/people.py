"""مدیریت کشور — مردم: برق/آب/گاز/غذا و بهداشت/رفاه/مسکن."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import (add_asset, bump_progress, consumption, get_country,
                          get_state, project_done, satisfaction_recompute,
                          sector_capacity, asset_qty)
from core.utils import fmt, jloads, jdumps, clamp, progress_bar
from gamebot.common import send_home

router = Router()

SECTORS = {
    "power": ("⚡️ برق شهری", "blackout_power"),
    "water": ("💧 آب شهری", "blackout_water"),
    "gas": ("🔥 گاز شهری", "blackout_gas"),
    "food": ("🍞 غذا و تغذیه", None),
    "health": ("🏥 بهداشت و درمان", None),
    "housing": ("🏘 مسکن و شهرسازی", None),
}


class PeopleFSM(StatesGroup):
    blackout = State()
    food_tons = State()
    subsidy = State()
    tax = State()
    currency_name = State()
    building_qty = State()


def people_kb() -> list:
    from gamebot.common import back_row
    return [
        [("⚡️ برق شهری", "g|sec|power"), ("💧 آب شهری", "g|sec|water")],
        [("🔥 گاز شهری", "g|sec|gas"), ("🍞 غذا و کشاورزی", "g|sec|food")],
        [("🏥 بهداشت و درمان", "g|sec|health"), ("🏘 مسکن", "g|sec|housing")],
        [("🎁 رفاه و قوانین", "g|sec|welfare"), ("🛢️ صنعت نفت", "g|oil")],
        back_row("g|mg"),
    ]


@router.callback_query(F.data == "g|ppl")
async def people_menu(call: CallbackQuery):
    state = await get_state(call.from_user.id)
    country = await get_country(call.from_user.id)
    pop = country["population"] if country else 0
    lines = [
        f"👥 <b>مدیریت امور مردم و زیرساخت‌ها</b>\n",
        f"😊 رضایت مردم: <b>{round(state['satisfaction'] or 0)}/100</b> {progress_bar(state['satisfaction'] or 0, 100)}",
        f"🧱 موجودی مصالح ساختمانی: <b>{fmt(state.get('materials') or 0)}</b> واحد",
        f"⚡️ برق ذخیره: <b>{fmt(state.get('energy') or 0)}</b> kWh | 💧 آب: <b>{fmt(state.get('water') or 0)}</b> | 🔥 گاز: <b>{fmt(state.get('gas') or 0)}</b>\n",
    ]
    for key, (title, _c) in SECTORS.items():
        cap = await sector_capacity(call.from_user.id, key)
        cons = consumption(pop, state.get(f"blackout_{key}") or 0) if key in ("power", "water", "gas") else pop // 10_000
        status = "✅" if cap >= cons else "⚠️"
        lines.append(f"{status} {title}: {fmt(cap)} / {fmt(cons)} واحد")
    lines += ["", "برای مدیریت هر بخش دکمه آن را انتخاب کنید:"]
    from gamebot.common import kb
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(people_kb()))


@router.callback_query(F.data.startswith("g|sec|"))
async def sector_page(call: CallbackQuery):
    key = call.data.split("|")[2]
    if key == "welfare":
        return await welfare_menu(call)
    state = await get_state(call.from_user.id)
    country = await get_country(call.from_user.id)
    pop = country["population"] if country else 0
    title, cut_key = SECTORS.get(key, (key, None))
    lines = [f"<b>{title}</b>\n"]
    if key in ("power", "water", "gas"):
        cap = await sector_capacity(call.from_user.id, key)
        cut = state.get(cut_key) or 0
        cons = consumption(pop, cut)
        lines += [
            f"🏭 ظرفیت تأمین: <b>{fmt(cap)}</b> واحد",
            f"🏠 نیاز مصرفی کشور: <b>{fmt(cons)}</b> واحد" + (f" (قطعی {cut} ساعته اعمال شده)" if cut else ""),
            f"📊 وضعیت تراز: {'✅ تراز مثبت و پوشش کامل' if cap >= cons else '⚠️ کمبود مصرف — کاهش تدریجی رضایت'}",
            f"🧱 مصالح آزاد شما: <b>{fmt(state.get('materials') or 0)}</b> واحد",
        ]
        if key == "gas":
            lines.append("🔥 گاز شهری برای مصارف گرمایشی و پتروشیمی شهری استفاده می‌شود.")
    elif key == "food":
        cap = await sector_capacity(call.from_user.id, "food") + await sector_capacity(call.from_user.id, "health")
        bought = await asset_qty(call.from_user.id, "food", 0)
        cap += bought
        cons = pop // 10_000
        hunger = clamp((cons - cap) / cons * 100, 0, 100) if cons else 0
        lines += [
            f"🌾 ظرفیت غذا و بهداشت: <b>{fmt(cap)}</b> واحد",
            f"🏠 نیاز جمعیت: <b>{fmt(cons)}</b> واحد",
            f"🍽 گرسنگی مردم: <b>{round(hunger)}%</b>",
        ]
    else:
        cap = await sector_capacity(call.from_user.id, key)
        cons = pop // 10_000
        lines += [
            f"🏗 ظرفیت: <b>{fmt(cap)}</b> واحد",
            f"🏠 نیاز: <b>{fmt(cons)}</b> واحد",
        ]
    buildings = await db.fetchall(
        "SELECT * FROM buildings WHERE sector=? AND is_active=1 ORDER BY cost_money", (key,))
    lines += ["", "🏗 <b>سازه یا تأسیسات برای ساخت:</b>"]
    rows = []
    for b in buildings:
        cost = f"🪙 {fmt(b['cost_coins'])}" if b["cost_coins"] else f"💰 {fmt(b['cost_money'])}"
        cap_txt = f" | +{fmt(b['capacity'])} واحد" if b["capacity"] else ""
        lines.append(f"{b['emoji']} {b['name']}: {cost}{cap_txt}")
        rows.append([(f"{b['emoji']} {b['name']}", f"g|buy|{b['id']}")])
    if key == "food":
        rows.append([("🛒 خرید غلات و غذا (تن)", "g|foodbuy")])
    if cut_key:
        label = 'برق' if key == 'power' else ('آب' if key == 'water' else 'گاز')
        rows.append([(f"⏸ قطعی برنامه‌ریزی‌شده {label} (۱-۲۴ ساعت)", f"g|cut|{key}")])
    from gamebot.common import kb, back_row
    rows.append(back_row("g|ppl"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


async def building_id(name: str) -> int:
    row = await db.fetchone("SELECT id FROM buildings WHERE name=?", (name,))
    return row["id"] if row else 0


async def check_building_requirements(user_id: int, b: dict) -> str | None:
    """برگرداندن پیام خطای پیش‌نیاز یا None."""
    if b["requires_project_id"]:
        if not await project_done(user_id, b["requires_project_id"]):
            prj = await db.fetchone("SELECT name FROM buildings WHERE id=?", (b["requires_project_id"],))
            return f"🔒 نیازمند پروژه «{prj['name'] if prj else '?'}»"
    if b["requires_building_id"] and b["requires_ratio"]:
        have = await asset_qty(user_id, "building", b["requires_building_id"])
        current = await asset_qty(user_id, "building", b["id"])
        need = (current + 1) * b["requires_ratio"]
        if have < need:
            req = await db.fetchone("SELECT name FROM buildings WHERE id=?", (b["requires_building_id"],))
            return f"🔒 برای ساخت بعدی {have}/{need} «{req['name'] if req else '?'}» لازم است"
    return None


@router.callback_query(F.data.startswith("g|buy|"))
async def buy_building(call: CallbackQuery):
    bid = int(call.data.split("|")[2])
    b = await db.fetchone("SELECT * FROM buildings WHERE id=?", (bid,))
    if not b:
        return await call.answer("یافت نشد", show_alert=True)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    state = await get_state(call.from_user.id)
    err = await check_building_requirements(call.from_user.id, b)
    cost = f"🪙 {fmt(b['cost_coins'])} سکه شاهی" if b["cost_coins"] else f"💰 {fmt(b['cost_money'])}"
    qty = await asset_qty(call.from_user.id, "building", bid)
    mat_per_unit = 10 if not b["cost_coins"] else 20
    text = (
        f"{b['emoji']} <b>{b['name']}</b>\n{b['description'] or ''}\n\n"
        f"💰 هزینه هر واحد: {cost}\n"
        f"🧱 مصالح لازم هر واحد: <b>{mat_per_unit}</b> واحد (موجودی شما: {fmt(state.get('materials') or 0)})\n"
        f"😊 رضایت: {'+' if (b['satisfaction'] or 0) >= 0 else ''}{b['satisfaction'] or 0}\n"
        + (f"🏭 ظرفیت تولید هر واحد: +{fmt(b['capacity'])}\n" if b["capacity"] else "")
        + f"📦 تعداد احداث شده فعلی: {qty}\n"
        + (f"\n⚠️ {err}" if err else "")
    )
    if err:
        return await call.message.edit_text(text, reply_markup=kb_([[("◀️ بازگشت", f"g|sec|{b['sector']}")]]))
    
    from gamebot.common import kb
    await call.answer()
    await call.message.edit_text(
        text + "\n\n<b>تعداد ساخت را انتخاب کنید:</b>",
        reply_markup=kb([
            [("🟢 ساخت ۱ عدد", f"g|bq|{bid}|1"), ("🟢 ساخت ۵ عدد", f"g|bq|{bid}|5")],
            [("🟢 ساخت ۱۰ عدد", f"g|bq|{bid}|10"), ("✏️ وارد کردن تعداد دلخواه", f"g|bqc|{bid}")],
            [("◀️ بازگشت", f"g|sec|{b['sector']}")],
        ])
    )


@router.callback_query(F.data.startswith("g|bqc|"))
async def buy_custom_qty(call: CallbackQuery, state: FSMContext):
    bid = int(call.data.split("|")[2])
    b = await db.fetchone("SELECT * FROM buildings WHERE id=?", (bid,))
    if not b:
        return await call.answer("یافت نشد", show_alert=True)
    await state.set_state(PeopleFSM.building_qty)
    await state.update_data(b_id=bid)
    await call.answer()
    await call.message.edit_text(
        f"🏗 <b>ساخت {b['name']}</b>\n\n"
        "تعداد مورد نظر برای ساخت را بنویسید (مثلاً 3 یا 25):\n"
        "برای انصراف /cancel را ارسال کنید."
    )


@router.message(PeopleFSM.building_qty)
async def buy_building_custom_input(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً یک عدد معتبر ارسال کنید.")
    if qty <= 0 or qty > 500:
        return await send_home(message, "❌ تعداد ساخت باید بین ۱ تا ۵۰۰ باشد.")
    data = await state.get_data()
    await state.clear()
    await execute_building_purchase(message, data["b_id"], qty)


@router.callback_query(F.data.startswith("g|bq|"))
async def buy_preset_qty(call: CallbackQuery):
    _, _, bid, count = call.data.split("|")
    await execute_building_purchase(call, int(bid), int(count))


async def execute_building_purchase(target_event, bid: int, qty: int):
    user_id = target_event.from_user.id
    b = await db.fetchone("SELECT * FROM buildings WHERE id=?", (bid,))
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (user_id,))
    state = await get_state(user_id)
    if not b or not user:
        if isinstance(target_event, CallbackQuery):
            return await target_event.answer("خطا در بارگذاری اطلاعات", show_alert=True)
        return await send_home(target_event, "خطا در بارگذاری.")

    total_coins = (b["cost_coins"] or 0) * qty
    total_money = (b["cost_money"] or 0) * qty
    mat_per_unit = 10 if not b["cost_coins"] else 20
    total_mat = mat_per_unit * qty

    if (state.get("materials") or 0) < total_mat:
        msg = f"❌ <b>مصالح کافی ندارید!</b>\nبرای ساخت {qty} عدد نیاز به <b>{total_mat}</b> واحد مصالح دارید (موجودی شما: {state.get('materials') or 0})."
        if isinstance(target_event, CallbackQuery):
            return await target_event.answer(msg, show_alert=True)
        return await send_home(target_event, msg)

    if total_coins and user["royal_coins"] < total_coins:
        msg = f"❌ سکه شاهی کافی نیست. نیاز: {fmt(total_coins)}"
        if isinstance(target_event, CallbackQuery):
            return await target_event.answer(msg, show_alert=True)
        return await send_home(target_event, msg)

    if total_money and user["money"] < total_money:
        msg = f"❌ بودجه کافی نیست. نیاز: {fmt(total_money)}"
        if isinstance(target_event, CallbackQuery):
            return await target_event.answer(msg, show_alert=True)
        return await send_home(target_event, msg)

    err = await check_building_requirements(user_id, b)
    if err:
        if isinstance(target_event, CallbackQuery):
            return await target_event.answer(err, show_alert=True)
        return await send_home(target_event, err)

    if total_coins:
        await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?", (total_coins, user_id))
    if total_money:
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (total_money, user_id))
    await db.execute("UPDATE states SET materials=materials-? WHERE user_id=?", (total_mat, user_id))
    await add_asset(user_id, "building", bid, qty)
    await bump_progress(user_id, "built", qty)
    await satisfaction_recompute(user_id)

    success_msg = f"✅ تعداد <b>{qty} عدد {b['name']}</b> با موفقیت ساخته شد!\n🧱 مصالح مصرفی: {total_mat} واحد"
    if isinstance(target_event, CallbackQuery):
        await target_event.answer("✅ ساخته شد")
        # بازگشت به صفحه بخش
        target_event.data = f"g|sec|{b['sector']}"
        await sector_page(target_event)
    else:
        await send_home(target_event, success_msg)


# ─── قطعی برق/آب/گاز ───


@router.callback_query(F.data.startswith("g|cut|"))
async def set_blackout(call: CallbackQuery, state: FSMContext):
    sector = call.data.split("|")[2]
    await state.set_state(PeopleFSM.blackout)
    await state.update_data(cut_sector=sector)
    await call.answer()
    await call.message.edit_text(
        "⏸ <b>قطعی برنامه‌ریزی‌شده</b>\n\n"
        "تعداد ساعت قطعی را بین <b>۱ تا ۲۴</b> بنویسید:\n"
        "هرچه ساعت قطعی بیشتر باشد مصرف کمتر اما رضایت مردم پایین‌تر می‌شود.\n\n"
        "💡 عدد 0 = لغو قطعی\n برای انصراف /cancel",
    )


@router.message(PeopleFSM.blackout)
async def blackout_input(message: Message, state: FSMContext):
    try:
        h = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً فقط عدد بین ۰ تا ۲۴ بفرستید.")
    if not 0 <= h <= 24:
        return await send_home(message, "❌ عدد باید بین ۰ تا ۲۴ باشد.")
    data = await state.get_data()
    sector = data.get("cut_sector", "power")
    await state.clear()
    col = {"power": "blackout_power", "water": "blackout_water", "gas": "blackout_gas"}[sector]
    await db.execute(f"UPDATE states SET {col}=? WHERE user_id=?", (h, message.from_user.id))
    await satisfaction_recompute(message.from_user.id)
    label = {"power": "برق", "water": "آب", "gas": "گاز"}[sector]
    if h == 0:
        await send_home(message, f"✅ قطعی {label} لغو شد.")
    else:
        await send_home(message, f"⏸ قطعی {label} برای <b>{h} ساعت</b> اعمال شد (مصرف کاهش، رضایت کاهش).")
    from gamebot.common import kb
    await send_home(message, "👥 بخش مردم:", reply_markup=kb(people_kb()))


# ─── خرید غذا ───


@router.callback_query(F.data == "g|foodbuy")
async def food_buy(call: CallbackQuery, state: FSMContext):
    price = int(await get_setting("food_price_per_ton", "50000"))
    await state.set_state(PeopleFSM.food_tons)
    await call.answer()
    await call.message.edit_text(
        f"🛒 <b>خرید غذا</b>\n\nقیمت هر تن: <b>{fmt(price)}</b>\n\n"
        "تعداد تن مورد نیاز را بنویسید (هر تن = ۱۰۰ واحد غذا):\n برای انصراف /cancel"
    )


@router.message(PeopleFSM.food_tons)
async def food_tons_input(message: Message, state: FSMContext):
    try:
        tons = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    if tons <= 0:
        return await send_home(message, "❌ عدد باید مثبت باشد.")
    price = int(await get_setting("food_price_per_ton", "50000"))
    total = tons * price
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (message.from_user.id,))
    if user["money"] < total:
        return await send_home(message, f"❌ بودجه کافی نیست. نیاز: {fmt(total)}")
    await state.clear()
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (total, user["id"]))
    await db.execute(
        "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?, 'food', 0, ?) "
        "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
        (user["id"], tons * 100, tons * 100),
    )
    await send_home(message, f"✅ <b>{fmt(tons)} تن غذا</b> خریداری شد ({fmt(tons * 100)} واحد غذا).")
    from gamebot.common import kb
    await send_home(message, "🍞 غذا و بهداشت:", reply_markup=kb([back_row("g|ppl")]))


# ─── رفاه ───


async def welfare_menu(call: CallbackQuery):
    state = await get_state(call.from_user.id)
    country = await get_country(call.from_user.id)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    from core.currency import my_currency_info
    info = await my_currency_info(call.from_user.id)
    threshold = max(1, int((country["population"] if country else 1) * 0.0004))
    text = (
        "🎁 <b>رفاه مردم</b>\n\n"
        f"💵 ارز کشور: <b>{info['name']}</b> — امتیاز: <b>{info['score']}</b> — رتبه جهانی: <b>{info['rank']}/{info['total']}</b>\n"
        + (f"👑 پول اصلی بازی: <b>{info['main']}</b> (مالکان: {info['main_owner']})\n" if info["main"] else "")
        + f"🎁 یارانه روزانه: <b>{fmt(state['subsidy_daily'] or 0)}</b> (سقف اثرگذار: {fmt(threshold)})\n"
        f"💰 نرخ مالیات: <b>{round((state['tax_rate'] or 0) * 100, 1)}%</b>\n"
        f"⚖️ قوانین انتخابی: <b>{len(jloads(state['chosen_laws'], {}))}</b>\n\n"
        "⚠️ یارانه از درآمد روزانه کسر می‌شود — هرچه از سقف بیشتر باشد رضایت بیشتر است.\n"
        "💡 امتیاز ارز = اقتصاد (تجارت ۲۴ ساعت اخیر + خزانه) + نظامی + رضایت مردمی.\n"
        "کشورهایی با ارز مشترک (مثل یورو) امتیاز جمعی÷تعداد دارند."
    )
    from gamebot.common import kb
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb([
        [("💵 ارز", "g|cur"), ("🎁 یارانه", "g|sub")],
        [("💰 مالیات", "g|tax"), ("⚖️ قوانین", "g|laws")],
        back_row("g|ppl"),
    ]))


@router.callback_query(F.data == "g|cur")
async def currency_menu(call: CallbackQuery):
    from core.currency import my_currency_info
    info = await my_currency_info(call.from_user.id)
    lines = ["💵 <b>ارز کشور</b>\n\n",
             f"ارز شما: <b>{info['name']}</b> — امتیاز: <b>{info['score']}</b> — رتبه: <b>{info['rank']}/{info['total']}</b>"]
    if info["main"]:
        lines.append(f"👑 پول اصلی بازی: <b>{info['main']}</b> (مالکان: {info['main_owner']})")
    lines.append("\n💡 قوی‌ترین ارز بازی «پول اصلی» می‌شود و تغییرش در کانال اعلام می‌شود.\n"
                 "می‌توانید ارز کشور دیگری را برگزینید یا ارز جدیدی با نام دلخواه بسازید "
                 "(هر دو نیازمند تأیید ادمین و اعلام در کانال است).")
    from gamebot.common import kb
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("🔄 استفاده از ارز کشور دیگر", "g|curadopt")],
        [("🆕 ساخت ارز جدید", "g|curnew")],
        back_row("g|sec|welfare"),
    ]))


@router.callback_query(F.data == "g|curadopt")
async def currency_adopt_list(call: CallbackQuery):
    state = await get_state(call.from_user.id)
    rows_db = await db.fetchall(
        "SELECT s.currency_name, c.name, c.flag FROM states s JOIN users u ON u.id=s.user_id "
        "JOIN countries c ON c.id=u.country_id WHERE u.country_id IS NOT NULL AND u.id!=? "
        "GROUP BY s.currency_name ORDER BY s.currency_name", (call.from_user.id,))
    rows = []
    for r in rows_db:
        cur = r["currency_name"] or "—"
        if cur == (state.get("currency_name") or ""):
            continue
        rows.append([(f"💵 {cur} ({r['flag']} {r['name']})", f"g|curadops|{cur}")])
    if not rows:
        return await call.answer("ارز دیگری موجود نیست", show_alert=True)
    rows.append(back_row("g|cur"))
    from gamebot.common import kb
    await call.answer()
    await call.message.edit_text(
        "🔄 <b>انتخاب ارز کشور دیگر</b>\nپس از تأیید ادمین، ارز کشور شما همین می‌شود:",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|curadops|"))
async def currency_adopt_send(call: CallbackQuery):
    cur = call.data.split("|", 2)[2]
    await db.execute(
        "INSERT INTO currency_requests(user_id, req_type, value) VALUES(?, 'adopt', ?)",
        (call.from_user.id, cur))
    await call.answer("📨 درخواست ثبت شد — پس از تأیید ادمین در کانال اعلام می‌شود")
    await currency_menu(call)


@router.callback_query(F.data == "g|curnew")
async def currency_new(call: CallbackQuery, state: FSMContext):
    await state.set_state(PeopleFSM.currency_name)
    await call.answer()
    await call.message.edit_text(
        "🆕 <b>ساخت ارز جدید</b>\n\nنام ارز جدید کشور را بنویسید (حداکثر ۲۰ حرف):\n"
        "پس از تأیید ادمین، ارز شما ساخته و در کانال اعلام می‌شود.\n برای انصراف /cancel")


@router.message(PeopleFSM.currency_name)
async def currency_name_input(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or len(name) > 20:
        return await send_home(message, "❌ نام باید بین ۱ تا ۲۰ حرف باشد.")
    await state.clear()
    await db.execute(
        "INSERT INTO currency_requests(user_id, req_type, value) VALUES(?, 'create', ?)",
        (message.from_user.id, name))
    c = await get_country(message.from_user.id)
    await send_home(message, 
        f"📨 درخواست ساخت ارز «<b>{name}</b>» برای کشور {c['flag']} {c['name']} ثبت شد.\n"
        "پس از تأیید ادمین اعمال و در کانال اعلام می‌شود.")
    await currency_menu(_fake_call(message))


class _fake_call:
    """شیء شبیه CallbackQuery برای بازتولید منو بعد از ورودی متنی."""

    def __init__(self, message: Message):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot

    async def answer(self, *_a, **_k):
        pass


@router.callback_query(F.data == "g|sub")
async def subsidy_menu(call: CallbackQuery, state: FSMContext):
    st = await get_state(call.from_user.id)
    country = await get_country(call.from_user.id)
    threshold = max(1, int((country["population"] if country else 1) * 0.0004))
    await call.answer()
    await call.message.edit_text(
        f"🎁 <b>یارانه روزانه</b>\n\n"
        f"یارانه فعلی: <b>{fmt(st['subsidy_daily'] or 0)}</b>\n"
        f"🎯 سقف اثرگذار برای جمعیت شما: <b>{fmt(threshold)}</b>\n\n"
        "مقدار یارانه روزانه را بنویسید (۰ = حذف یارانه).\n"
        "یارانه از درآمد روزانه کسر می‌شود.\n برای انصراف /cancel",
    )
    await state.set_state(PeopleFSM.subsidy)


@router.message(PeopleFSM.subsidy)
async def subsidy_input(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    if amount < 0:
        return await send_home(message, "❌ عدد نمی‌تواند منفی باشد.")
    await state.clear()
    await db.execute("UPDATE states SET subsidy_daily=? WHERE user_id=?", (amount, message.from_user.id))
    await satisfaction_recompute(message.from_user.id)
    await send_home(message, f"✅ یارانه روزانه روی <b>{fmt(amount)}</b> تنظیم شد.")
    from gamebot.common import kb
    await send_home(message, "🎁 رفاه:", reply_markup=kb([
        [("💵 پول", "g|cur"), ("🎁 یارانه", "g|sub")],
        [("💰 مالیات", "g|tax"), ("⚖️ قوانین", "g|laws")],
        back_row("g|ppl"),
    ]))


@router.callback_query(F.data == "g|tax")
async def tax_menu(call: CallbackQuery, state: FSMContext):
    st = await get_state(call.from_user.id)
    await call.answer()
    await call.message.edit_text(
        f"💰 <b>نرخ مالیات</b>\n\n"
        f"نرخ فعلی: <b>{round((st['tax_rate'] or 0) * 100, 1)}%</b>\n\n"
        "نرخ مالیات را به درصد بنویسید (۰ تا ۵۰):\n"
        "💡 مالیات درآمد روزانه را بیشتر می‌کند اما رضایت مردم را کم.\n برای انصراف /cancel",
    )
    await state.set_state(PeopleFSM.tax)


@router.message(PeopleFSM.tax)
async def tax_input(message: Message, state: FSMContext):
    try:
        rate = float(message.text.strip().replace("٪", "").replace("%", ""))
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً عدد (درصد) بفرستید.")
    if not 0 <= rate <= 50:
        return await send_home(message, "❌ نرخ باید بین ۰ تا ۵۰ باشد.")
    await state.clear()
    await db.execute("UPDATE states SET tax_rate=? WHERE user_id=?", (rate / 100, message.from_user.id))
    await satisfaction_recompute(message.from_user.id)
    await send_home(message, f"✅ نرخ مالیات روی <b>{round(rate, 1)}%</b> تنظیم شد.")
    from gamebot.common import kb
    await send_home(message, "🎁 رفاه:", reply_markup=kb([
        [("💵 پول", "g|cur"), ("🎁 یارانه", "g|sub")],
        [("💰 مالیات", "g|tax"), ("⚖️ قوانین", "g|laws")],
        back_row("g|ppl"),
    ]))


# ─── قوانین ───


@router.callback_query(F.data == "g|laws")
async def laws_menu(call: CallbackQuery):
    state = await get_state(call.from_user.id)
    chosen = jloads(state["chosen_laws"], {})
    laws = await db.fetchall("SELECT * FROM laws WHERE is_active=1 ORDER BY id")
    rows = []
    for law in laws:
        opts = jloads(law["options"], [])
        idx = int(chosen.get(str(law["id"]), -1))
        current = opts[idx]["label"] if 0 <= idx < len(opts) else "—"
        rows.append([(f"{law['title']}: {current}", f"g|law|{law['id']}")])
    from gamebot.common import kb
    await call.answer()
    await call.message.edit_text(
        "⚖️ <b>قوانین کشور</b>\n\nقانون را انتخاب و حالت آن را تعیین کنید. "
        "اثر قوانین به دین و حکومت شما هم بستگی دارد.",
        reply_markup=kb(rows + [back_row("g|sec|welfare")]),
    )


@router.callback_query(F.data.startswith("g|law|"))
async def law_options(call: CallbackQuery):
    lid = int(call.data.split("|")[2])
    law = await db.fetchone("SELECT * FROM laws WHERE id=?", (lid,))
    if not law:
        return await call.answer("یافت نشد", show_alert=True)
    opts = jloads(law["options"], [])
    rows = [[(f"{o['label']} ({'+' if o.get('satisfaction', 0) >= 0 else ''}{o.get('satisfaction', 0)})", 
              f"g|lawset|{lid}|{i}")] for i, o in enumerate(opts)]
    rows.append(back_row("g|laws"))
    from gamebot.common import kb
    await call.answer()
    await call.message.edit_text(
        f"⚖️ <b>{law['title']}</b>\n\nیکی از حالت‌ها را انتخاب کنید:",
        reply_markup=kb(rows),
    )


@router.callback_query(F.data.startswith("g|lawset|"))
async def law_set(call: CallbackQuery):
    _, _, lid, idx = call.data.split("|")
    law = await db.fetchone("SELECT * FROM laws WHERE id=?", (int(lid),))
    if not law:
        return await call.answer("یافت نشد", show_alert=True)
    state = await get_state(call.from_user.id)
    chosen = jloads(state["chosen_laws"], {})
    chosen[str(lid)] = int(idx)
    await db.execute("UPDATE states SET chosen_laws=? WHERE user_id=?",
                     (jdumps(chosen), call.from_user.id))
    await satisfaction_recompute(call.from_user.id)
    await call.answer("✅ قانون اعمال شد")
    await laws_menu(call)

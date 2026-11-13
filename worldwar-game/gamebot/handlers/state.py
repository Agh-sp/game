"""🧨 موتور واقع‌گرایی — منوهای کشور: تأمین، ناآرامی، اقتصاد، انتخابات،
اطلاعات، بازار نفت، پناهندگان، پایگاه خارجی، شبکهٔ برق و فصل‌ها.

همهٔ این بخش‌ها از «🛡 امنیت و کشور» در امپراطوری باز می‌شوند و هر تغییر
در پنل ادمین (تنظیمات با برچسب فارسی) روی همان عدد اعمال می‌شود.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.utils import fmt, fmt_money
from gamebot.common import back_row, kb, send_home

log = logging.getLogger(__name__)
router = Router()


class StateFSM(StatesGroup):
    ammo_qty = State()
    fuel_qty = State()
    loan_amount = State()
    print_amount = State()
    resettle_qty = State()
    campaign_votes = State()


async def _guard(user_id: int) -> str:
    row = await db.fetchone("SELECT country_id FROM users WHERE id=?", (user_id,))
    if not row or not row["country_id"]:
        return "🏳 ابتدا کشور خود را انتخاب کنید."
    return ""


# ═════════════ لوای اصلی ═════════════

@router.callback_query(F.data == "g|state")
async def hub(call: CallbackQuery, state: FSMContext):
    await state.clear()
    err = await _guard(call.from_user.id)
    if err:
        return await call.answer(err, show_alert=True)
    from core import elections, intel, market, refugees, supply, unrest
    from core import grid, weather, bases
    s = await supply.get(call.from_user.id)
    u = await unrest.get(call.from_user.id)
    inf = await market.inflation(call.from_user.id)
    oil = await market.oil_price()
    grd = await grid.hours_left(call.from_user.id)
    p = await elections.party_of(call.from_user.id)
    season = await weather.season_line()
    lines = [
        "🛡 <b>امنیت و کشور</b>",
        "",
        f"🚚 انبار تأمین: {fmt(s['ammo'])} مهمات | {fmt(s['fuel'])} سوخت",
        f"✊ ناآرامی: <b>{u['unrest']}٪</b>"
        + (" — ✊ اعتصاب فعال!" if u["strike_active"] else "")
        + (" — 🔥 جنگ داخلی!" if u["revolt_active"] else ""),
        f"💸 تورم: <b>{inf}٪</b> | 🛢 نفت جهانی: {oil:.1f} دلار",
        f"⚡ خاموشی شبکه: {grd} ساعت" if grd > 0 else "⚡ شبکهٔ برق: سالم ✅",
        f"🏆 حزب حاکم: {p['title']}",
        season,
        "",
        "بخش مورد نظر را انتخاب کنید:",
    ]
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("🚚 تأمین و مهمات", "g|sup"), ("✊ ناآرامی و اعتصاب", "g|unr")],
        [("💸 اقتصاد و بدهی", "g|econ"), ("🗳 انتخابات", "g|elec")],
        [("🕵 شبکهٔ اطلاعات", "g|intel"), ("🛢 بازار جهانی نفت", "g|mkt")],
        [("🏃 پناهندگان", "g|refu"), ("📡 پایگاه خارجی", "g|fbase")],
        [("⚡ شبکهٔ برق و خاموشی", "g|grid"), ("🍁 فصل و آب‌وهوا", "g|sea")],
        back_row("g|emp"),
    ]))


# ═════════════ ۱) تأمین ═════════════

def supply_kb(user_id: int) -> list:
    return [
        [("🛒 خرید مهمات", "g|supb|ammo"), ("🛒 خرید سوخت", "g|supb|fuel")],
        [("🔄 به‌روزرسانی", "g|sup")],
        back_row("g|state"),
    ]


@router.callback_query(F.data == "g|sup")
async def supply_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import supply
    text = await supply.status_text(call.from_user.id)
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(supply_kb(call.from_user.id)))


@router.callback_query(F.data.startswith("g|supb|"))
async def supply_buy_prompt(call: CallbackQuery, state: FSMContext):
    kind = call.data.split("|")[2]
    if kind not in ("ammo", "fuel"):
        return await call.answer("نوع نامعتبر", show_alert=True)
    from core import supply
    price_key = "supply_buy_price" if kind == "ammo" else "supply_fuel_price"
    unit = int(float(await get_setting(price_key, "60000") or 60000))
    await state.set_state(StateFSM.ammo_qty if kind == "ammo" else StateFSM.fuel_qty)
    await state.update_data(kind=kind)
    label = "مهمات" if kind == "ammo" else "سوخت"
    await call.answer()
    await call.message.edit_text(
        f"🛒 <b>خرید {label}</b>\n\n"
        f"قیمت هر واحد: <b>{fmt(unit)}</b> پول\n"
        f"چند {label} می‌خرید؟ (عدد بفرستید — برای انصراف /cancel)",
        reply_markup=kb([back_row("g|sup")]))


async def _supply_buy_message(message: Message, state: FSMContext):
    data = await state.get_data()
    kind = data.get("kind", "ammo")
    try:
        qty = int((message.text or "0").replace(",", "").replace("،", "").strip())
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً یک عدد بفرستید.")
    await state.clear()
    from core import supply
    ok, text = await supply.buy(message.from_user.id, kind, qty)
    await send_home(message, text, reply_markup=kb(supply_kb(message.from_user.id)))


@router.message(StateFSM.ammo_qty)
async def supply_buy_ammo(message: Message, state: FSMContext):
    await _supply_buy_message(message, state)


@router.message(StateFSM.fuel_qty)
async def supply_buy_fuel(message: Message, state: FSMContext):
    await _supply_buy_message(message, state)


# ═════════════ ۲) ناآرامی ═════════════

def unrest_kb(info: dict) -> list:
    rows = []
    if info.get("strike_active"):
        rows.append([("🤝 مذاکره و پذیرش خواسته‌ها", "g|unrp|neg")])
        rows.append([("🪖 شکستن اعتصاب", "g|unrp|break")])
    if info.get("revolt_active"):
        rows.append([("🤝 امتیازدهی به شورشی‌ها", "g|unrp|vneg"),
                     ("💼 خرید فرماندهان", "g|unrp|bribe")])
        rows.append([("🪖 سرکوب جنگ داخلی", "g|unrp|crush")])
    rows.append([("🎁 بستهٔ یارانه", "g|unrp|sub"), ("🪖 سرکوب اعتراض", "g|unrp|crk")])
    rows.append([("⏳ نادیده‌گرفتن", "g|unrp|ign")])
    rows.append([("🔄 به‌روزرسانی", "g|unr")])
    rows.append(back_row("g|state"))
    return rows


@router.callback_query(F.data == "g|unr")
async def unrest_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import unrest
    info = await unrest.get(call.from_user.id)
    text = await unrest.unrest_text(call.from_user.id)
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(unrest_kb(info)))


@router.callback_query(F.data.startswith("g|unrp|"))
async def unrest_action(call: CallbackQuery, state: FSMContext):
    action = call.data.split("|")[2]
    from core import unrest
    uid = call.from_user.id
    if action == "sub":
        ok, text = await unrest.pay_subsidy(uid)
    elif action == "crk":
        ok, text = await unrest.crackdown(uid)
    elif action == "ign":
        ok, text = await unrest.ignore(uid)
    elif action == "neg":
        ok, text = await unrest.negotiate_strike(uid)
    elif action == "break":
        ok, text = await unrest.break_strike(uid)
    elif action == "vneg":
        ok, text = await unrest.revolt_negotiate(uid)
    elif action == "bribe":
        ok, text = await unrest.revolt_bribe(uid)
    elif action == "crush":
        ok, text = await unrest.revolt_crush(uid)
    else:
        return await call.answer("گزینه نامعتبر", show_alert=True)
    info = await unrest.get(uid)
    await call.answer("✅ انجام شد" if ok else "❌ ناموفق", show_alert=not ok)
    await call.message.edit_text(
        text + "\n\n" + await unrest.unrest_text(uid),
        reply_markup=kb(unrest_kb(info)))


# ═════════════ ۳) اقتصاد، بدهی و تورم ═════════════

@router.callback_query(F.data == "g|econ")
async def economy_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import market
    text = await market.economy_text(call.from_user.id)
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb([
        [("🏦 گرفتن وام", "g|loan"), ("💳 پرداخت بدهی", "g|repay")],
        [("🏦 چاپ پول", "g|print")],
        [("🔄 به‌روزرسانی", "g|econ")],
        back_row("g|state"),
    ]))


@router.callback_query(F.data == "g|loan")
async def loan_prompt(call: CallbackQuery, state: FSMContext):
    from core import market
    limit = await market.loan_limit(call.from_user.id)
    await state.set_state(StateFSM.loan_amount)
    await call.answer()
    await call.message.edit_text(
        f"🏦 <b>وام بانک مرکزی</b>\n\n"
        f"سقف وام شما: <b>{fmt_money(limit)}</b>\n"
        f"بهرهٔ هر دوره: {float(await get_setting('loan_rate_percent', '2')):g}٪ "
        f"× {int(float(await get_setting('loan_periods', '10')))} دوره\n\n"
        "مبلغ درخواستی را بنویسید (برای گرفتن سقف کامل، عدد ۰ بفرستید — /cancel برای انصراف):",
        reply_markup=kb([back_row("g|econ")]))


@router.message(StateFSM.loan_amount)
async def loan_input(message: Message, state: FSMContext):
    try:
        amount = int((message.text or "0").replace(",", "").replace("،", "").strip())
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً یک عدد بفرستید.")
    if amount < 0:
        return await send_home(message, "❌ مبلغ نامعتبر است.")
    await state.clear()
    from core import market
    ok, text = await market.borrow(message.from_user.id, amount or None)
    await send_home(message, text, reply_markup=kb([
        [("🏦 بازگشت به اقتصاد", "g|econ")], back_row("g|state")]))


@router.callback_query(F.data == "g|repay")
async def repay_now(call: CallbackQuery):
    from core import market
    ok, text = await market.repay(call.from_user.id)
    await call.answer("✅ انجام شد" if ok else "❌ امکان‌پذیر نیست", show_alert=not ok)
    await call.message.edit_text(text, reply_markup=kb([
        [("🏦 بازگشت به اقتصاد", "g|econ")], back_row("g|state")]))


@router.callback_query(F.data == "g|print")
async def print_prompt(call: CallbackQuery, state: FSMContext):
    from core import market
    default_m = float(await get_setting("print_money_amount_m", "80"))
    inf = await market.inflation(call.from_user.id)
    await state.set_state(StateFSM.print_amount)
    await call.answer()
    await call.message.edit_text(
        "🏦 <b>چاپ پول</b>\n\n"
        f"💸 تورم فعلی: <b>{inf}٪</b>\n"
        f"مبلغ دلخواه را به <b>میلیون</b> بنویسید (پیشنهاد: {default_m:g}) — "
        "چاپ پول تورم و نارضایتی می‌آورد.\n/cancel برای انصراف",
        reply_markup=kb([back_row("g|econ")]))


@router.message(StateFSM.print_amount)
async def print_input(message: Message, state: FSMContext):
    try:
        millions = float((message.text or "0").replace(",", "").replace("،", "").strip())
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً یک عدد (میلیون) بفرستید.")
    if millions <= 0 or millions > 5_000:
        return await send_home(message, "❌ مبلغ باید بین ۱ تا ۵۰۰۰ میلیون باشد.")
    await state.clear()
    from core import market
    ok, text = await market.print_money(message.from_user.id, int(millions * 1_000_000))
    await send_home(message, text, reply_markup=kb([
        [("🏦 بازگشت به اقتصاد", "g|econ")], back_row("g|state")]))


# ═════════════ ۶) انتخابات ═════════════

@router.callback_query(F.data == "g|elec")
async def elections_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import elections
    text = await elections.elections_text(call.from_user.id)
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb([
        [("📣 خرید رأی تبلیغاتی", "g|elcamp")],
        [("🔄 به‌روزرسانی", "g|elec")],
        back_row("g|state"),
    ]))


@router.callback_query(F.data == "g|elcamp")
async def campaign_prompt(call: CallbackQuery, state: FSMContext):
    cost = int(float(await get_setting("election_campaign_cost_m", "25")) * 1_000_000)
    await state.set_state(StateFSM.campaign_votes)
    await call.answer()
    await call.message.edit_text(
        f"📣 <b>کمپین انتخاباتی</b>\n\nهزینهٔ هر رأی تبلیغاتی: <b>{fmt(cost)}</b>\n"
        "چند رأی تبلیغاتی می‌خرید؟ (۱ تا ۲۰ — /cancel برای انصراف)",
        reply_markup=kb([back_row("g|elec")]))


@router.message(StateFSM.campaign_votes)
async def campaign_input(message: Message, state: FSMContext):
    try:
        votes = int((message.text or "0").strip())
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً یک عدد بفرستید.")
    await state.clear()
    from core import elections
    ok, text = await elections.campaign(message.from_user.id, votes)
    await send_home(message, text, reply_markup=kb([
        [("🗳 بازگشت به انتخابات", "g|elec")], back_row("g|state")]))


# ═════════════ ۴) اطلاعات ═════════════

@router.callback_query(F.data == "g|intel")
async def intel_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import intel
    text = await intel.intel_text(call.from_user.id)
    await call.answer()
    rows = []
    targets = await db.fetchall(
        "SELECT u.id, c.name, c.flag FROM users u JOIN countries c ON c.id=u.country_id "
        "WHERE u.id!=? AND u.banned=0 AND c.is_active=1 ORDER BY c.population DESC LIMIT 12",
        (call.from_user.id,))
    for t in targets:
        rows.append([(f"🕵 {t['flag']} {t['name']}", f"g|spy|{t['id']}")])
    rows.append([("🔄 به‌روزرسانی", "g|intel")])
    rows.append(back_row("g|state"))
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|spy|"))
async def spy_run(call: CallbackQuery):
    target = int(call.data.split("|")[2])
    from core import intel
    ok, text = await intel.spy(call.from_user.id, target)
    await call.answer("✅ گزارش آماده شد" if ok else "❌ ناموفق", show_alert=not ok)
    await call.message.edit_text(text + "\n\n" + await intel.intel_text(call.from_user.id),
                                 reply_markup=kb([
                                     [("🕵 بازگشت به اطلاعات", "g|intel")],
                                     back_row("g|state")]))


# ═════════════ ۷) بازار نفت ═════════════

@router.callback_query(F.data == "g|mkt")
async def market_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import market, income, weather
    text = await market.oil_market_text()
    src = await income.income_sources(call.from_user.id)
    text += (f"\n\n💰 درآمد نفتی فعلی شما در هر دوره: "
             f"<b>{fmt_money(src['oil']['amount'])}</b>\n"
             f"   └ بازار ×{src['oil'].get('market_mult', 1)} | دکل‌ها {src['oil']['rigs']}")
    try:
        text += "\n\n" + await weather.season_line()
    except Exception:
        pass
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb([
        [("🛢 رفتن به صنعت نفت", "g|oil")],
        [("🔄 به‌روزرسانی", "g|mkt")],
        back_row("g|state"),
    ]))


# ═════════════ ۵) پناهندگان ═════════════

@router.callback_query(F.data == "g|refu")
async def refugees_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import refugees
    text = await refugees.refugees_text(call.from_user.id)
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb([
        [("🏠 اسکان پناهندگان", "g|refures")],
        [("🔄 به‌روزرسانی", "g|refu")],
        back_row("g|state"),
    ]))


@router.callback_query(F.data == "g|refures")
async def resettle_prompt(call: CallbackQuery, state: FSMContext):
    row = await db.fetchone(
        "SELECT COALESCE(SUM(count),0) c FROM refugee_flows WHERE to_user=?", (call.from_user.id,))
    hosted = int((row or {}).get("c") or 0)
    if hosted <= 0:
        return await call.answer("❌ پناهنده‌ای در کشور شما نیست", show_alert=True)
    unit = int(float(await get_setting("refugee_return_cost_m", "10")) * 1_000_000)
    await state.set_state(StateFSM.resettle_qty)
    await call.answer()
    await call.message.edit_text(
        f"🏠 <b>اسکان پناهندگان</b>\n\nپناهندگان فعلی: <b>{fmt(hosted)}</b> نفر\n"
        f"هزینهٔ اسکان هر ۱۰۰۰ نفر: <b>{fmt(unit)}</b>\n\n"
        "چند نفر را اسکان می‌دهید؟ (/cancel برای انصراف)",
        reply_markup=kb([back_row("g|refu")]))


@router.message(StateFSM.resettle_qty)
async def resettle_input(message: Message, state: FSMContext):
    try:
        count = int((message.text or "0").replace(",", "").replace("،", "").strip())
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً یک عدد بفرستید.")
    await state.clear()
    from core import refugees
    ok, text = await refugees.resettle(message.from_user.id, count)
    await send_home(message, text, reply_markup=kb([
        [("🏃 بازگشت به پناهندگان", "g|refu")], back_row("g|state")]))


# ═════════════ ۸) پایگاه خارجی ═════════════

@router.callback_query(F.data == "g|fbase")
async def foreign_base_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import bases
    text = await bases.bases_text(call.from_user.id)
    rows = []
    hosted = await db.fetchall(
        "SELECT b.guest_id, c.name, c.flag FROM bases b JOIN users u ON u.id=b.guest_id "
        "JOIN countries c ON c.id=u.country_id WHERE b.host_id=? AND b.status='active' "
        "AND COALESCE(b.kind,'land') NOT LIKE '%foreign%'", (call.from_user.id,))
    for h in hosted:
        rows.append([(f"📡 اعلام پایگاه خارجی — {h['flag']} {h['name']}",
                      f"g|fbmk|{h['guest_id']}")])
    foreign = await db.fetchall(
        "SELECT b.guest_id, c.name, c.flag FROM bases b JOIN users u ON u.id=b.guest_id "
        "JOIN countries c ON c.id=u.country_id WHERE b.host_id=? AND b.status='active' "
        "AND COALESCE(b.kind,'land') LIKE '%foreign%'", (call.from_user.id,))
    for h in foreign:
        rows.append([(f"✂️ لغو قرارداد — {h['flag']} {h['name']}", f"g|fbend|{h['guest_id']}")])
    rows.append([("🚚 مدیریت پایگاه‌ها", "g|base")])
    rows.append([("🔄 به‌روزرسانی", "g|fbase")])
    rows.append(back_row("g|state"))
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|fbmk|"))
async def foreign_base_make(call: CallbackQuery):
    guest = int(call.data.split("|")[2])
    from core import bases
    ok, text = await bases.declare_foreign(call.from_user.id, guest)
    await call.answer("✅ پایگاه خارجی ثبت شد" if ok else "❌ ناموفق", show_alert=not ok)
    await call.message.edit_text(text + "\n\n" + await bases.bases_text(call.from_user.id),
                                 reply_markup=kb([[("📡 بازگشت به پایگاه خارجی", "g|fbase")],
                                                  back_row("g|state")]))


@router.callback_query(F.data.startswith("g|fbend|"))
async def foreign_base_end(call: CallbackQuery):
    guest = int(call.data.split("|")[2])
    from core import bases
    ok, text = await bases.terminate(call.from_user.id, guest)
    await call.answer("✅ لغو شد" if ok else "❌ ناموفق", show_alert=not ok)
    await call.message.edit_text(text + "\n\n" + await bases.bases_text(call.from_user.id),
                                 reply_markup=kb([[("📡 بازگشت به پایگاه خارجی", "g|fbase")],
                                                  back_row("g|state")]))


# ═════════════ ۹) شبکهٔ برق ═════════════

@router.callback_query(F.data == "g|grid")
async def grid_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import grid
    hours = await grid.hours_left(call.from_user.id)
    mult = await grid.income_multiplier(call.from_user.id)
    if hours <= 0:
        text = ("⚡ <b>شبکهٔ برق</b>\n\n✅ شبکه سالم است و خاموشی فعالی ندارید.\n\n"
                "💡 هر حملهٔ موفق سایبری/خرابکاری روی «⚡ نیروگاه برق» خاموشی چندساعته "
                "می‌سازد که پمپ آب، صنعت و بیمارستان‌ها را هم می‌خواباند.")
        rows = [[("🔄 به‌روزرسانی", "g|grid")], back_row("g|state")]
    else:
        per_hour = int(float(await get_setting("grid_repair_cost_m", "12")) * 1_000_000)
        text = (f"⚡ <b>خاموشی شبکهٔ برق</b>\n\n"
                f"🔌 ساعت خاموشی باقی‌مانده: <b>{hours}</b>\n"
                f"💸 اثر روی درآمد: <b>×{mult}</b>\n"
                f"🚰 پمپ آب، صنعت و سردخانهٔ دارو مختل است.\n"
                f"🔧 هزینهٔ ترمیم اضطراری هر ساعت: {fmt(per_hour)} "
                f"(کل: {fmt(per_hour * hours)})")
        rows = [[("🔧 ترمیم اضطراری", "g|gridfix")],
                [("🔄 به‌روزرسانی", "g|grid")], back_row("g|state")]
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|gridfix")
async def grid_repair(call: CallbackQuery):
    from core import grid
    ok, text = await grid.repair(call.from_user.id)
    await call.answer("✅ ترمیم شد" if ok else "❌ ناموفق", show_alert=not ok)
    await call.message.edit_text(text, reply_markup=kb([
        [("⚡ بازگشت به شبکه", "g|grid")], back_row("g|state")]))


# ═════════════ ۱۰) فصل و آب‌وهوا ═════════════

@router.callback_query(F.data == "g|sea")
async def season_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from core import weather
    from core.db import get_setting as gs
    now = await weather.current()
    emoji, name, desc = weather.SEASON_INFO.get(now.get("season"), ("🍁", "—", ""))
    lines = [f"{emoji} <b>فصل {name}</b>", "", desc, "",
             await weather.season_line(), ""]
    lines.append(f"❄️ اثر زمستان روی حمله: "
                 f"−{round(float(await gs('weather_winter_attack_pct', '12')))}٪")
    lines.append(f"⚡ مصرف اضافهٔ انرژی در زمستان: "
                 f"+{round(float(await gs('weather_winter_energy_pct', '18')))}٪")
    lines.append(f"💧 افت آب در تابستان: "
                 f"−{round(float(await gs('weather_summer_water_pct', '15')))}٪")
    lines.append(f"☀️ شانس خشکسالی تابستان: "
                 f"{round(float(await gs('weather_drought_chance', '20')))}٪")
    lines.append(f"🌪 شانس طوفان پاییز: "
                 f"{round(float(await gs('weather_storm_chance', '15')))}٪")
    lines.append(f"🌾 بونوس برداشت پاییز: "
                 f"{fmt_money(int(float(await gs('weather_harvest_bonus_m', '25')) * 1_000_000))}")
    lines.append("\n💡 فصل‌ها خودکار عوض می‌شوند و روی حمله، آب، انرژی و درآمد اثر می‌گذارند.")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("🔄 به‌روزرسانی", "g|sea")], back_row("g|state")]))

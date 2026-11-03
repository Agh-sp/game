"""منو شروع، امپراطوری من، درآمد خودکار و پیمان اعتماد."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import (bump_progress, income_amount, satisfaction_recompute,
                          settle_projects, settle_trainings, get_state, assets_of)
from core.treaties import trust_partners
from core.utils import fmt, hours_left, fmt_hm, iso, split_text
from gamebot.common import (back_row, blocked_banner, country_display, empire_kb,
                            kb, main_menu_kb, manage_kb, server_line, home_row, send_home
)

router = Router()


@router.message(Command("cancel"))
async def game_cancel(message: Message, state: FSMContext):
    """لغو هر عملیات در جریان و بازگشت به منو شروع."""
    await state.clear()
    user = await db.fetchone("SELECT country_id FROM users WHERE id=?", (message.from_user.id,))
    if user and user["country_id"]:
        await send_home(message, "❌ عملیات لغو شد.", reply_markup=main_menu_kb())
    else:
        from gamebot.handlers.start import country_selection
        await send_home(message, "❌ عملیات لغو شد.")
        await country_selection(message)


@router.callback_query(F.data == "g|main")
async def main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if not user or not user["country_id"]:
        await call.answer()
        await call.message.edit_text("🌍 ابتدا کشور خود را انتخاب کنید:")
        return
    await bump_progress(call.from_user.id, "login")
    await call.answer()
    season = await get_setting("season_name", "")
    text = (f"🌍 <b>منو شروع</b>\n\n{await country_display(call.from_user.id)}\n\n"
            + (f"🎬 سیزن: {season}\n" if season else "")
            + server_line())
    is_admin = bool(await db.fetchone("SELECT id FROM admins WHERE id=?", (call.from_user.id,)))
    await call.message.edit_text(text, reply_markup=main_menu_kb(is_admin))


@router.callback_query(F.data == "g|emp")
async def empire(call: CallbackQuery):
    await settle_projects(call.from_user.id, call.bot)
    await settle_trainings(call.from_user.id)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    state = await get_state(call.from_user.id)
    minutes = int(float(await get_setting("income_interval_minutes", "30")))
    last = state.get("last_income")
    income_txt = (f"⏳ پرداخت بعدی: حداکثر {minutes} دقیقه دیگر"
                  if not last or hours_left(last) < minutes / 60 else
                  f"⏳ {fmt_hm(hours_left(last))} دیگر")
    # پروژه‌های در جریان
    projects = await db.fetchall(
        "SELECT p.name, p.completes_at, b.name AS bname, b.emoji AS bemoji "
        "FROM player_projects p JOIN buildings b ON b.id=p.building_id "
        "WHERE p.user_id=? AND p.status='in_progress' ORDER BY p.completes_at",
        (call.from_user.id,),
    )
    prj_lines = [f"   {p['bemoji']} {p['name'] or p['bname']} — {fmt_hm(hours_left(p['completes_at']))} مانده" for p in projects[:5]]
    text = (
        f"🏰 <b>امپراطوری من</b>\n\n{await country_display(call.from_user.id, extended=True)}\n\n"
        f"💰 درآمد (خودکار هر {minutes} دقیقه): {income_txt}\n"
    )
    if prj_lines:
        text += "\n🏗 <b>پروژه‌های در جریان:</b>\n" + "\n".join(prj_lines) + "\n"
    text += "\n" + blocked_banner(state)
    rows = [
        [("🏛 مدیریت کشور", "g|mg")],
        [("⚔️ اتاق جنگ", "g|war")],
        [("🤝 تجارت بین‌المللی", "g|trd")],
        [("🕊 سازمان ملل", "g|un")],
        [("🛟 سازمان نجات", "g|resc")],
        [("🏳️ پرچم رسمی کشور", "g|myflag"), ("📢 بیانیه", "g|stmt")],
    ]
    trusts = await trust_partners(call.from_user.id)
    if trusts:
        rows.append([(f"🤫 اعتماد ({len(trusts)})", "g|trust")])
    rows.append(home_row())
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(rows, home=False))


@router.message(Command("flag"))
@router.callback_query(F.data == "g|myflag")
async def show_my_flag(event: Message | CallbackQuery):
    is_call = isinstance(event, CallbackQuery)
    user_id = event.from_user.id
    if is_call:
        await event.answer()
    from core.economy import get_country
    country = await get_country(user_id)
    if not country:
        msg = "❌ شما هنوز کشوری انتخاب نکرده‌اید! ابتدا با /start کشور خود را برگزینید."
        return await (event.message.answer(msg) if is_call else event.answer(msg))
    flag_url = country.get("flag_url") or f"https://flagcdn.com/w640/{country.get('iso_code', 'ir')}.png"
    text = (
        f"🏳️ <b>پرچم رسمی کشور شما: {country['name']}</b> {country['flag']}\n\n"
        f"🌐 کد بین‌المللی ISO: <code>{country.get('iso_code', '').upper()}</code>\n"
        f"👥 جمعیت رسمی: {fmt(country['population'])} نفر\n"
        f"🗺 قاره / منطقه: {country['region']}\n"
        f"🌊 دسترسی به آب‌های آزاد: {'دارد ✅' if country['has_sea'] else 'محصور در خشکی ❌'}\n"
        f"💵 نام ارز ملی: {country.get('currency', 'ریال')}"
    )
    target = event.message if is_call else event
    try:
        await target.answer_photo(flag_url, caption=text, reply_markup=kb([[("◀️ بازگشت به امپراطوری", "g|emp")]]))
    except Exception:
        await target.answer(f"{text}\n\n🔗 لینک پرچم باکیفیت:\n{flag_url}", reply_markup=kb([[("◀️ بازگشت به امپراطوری", "g|emp")]]))


@router.callback_query(F.data == "g|inc")
async def income_info(call: CallbackQuery):
    """درآمد خودکار شده — این دکمه فقط اطلاعات می‌دهد."""
    state = await get_state(call.from_user.id)
    daily = await income_amount(call.from_user.id)
    minutes = int(float(await get_setting("income_interval_minutes", "30")))
    per_tick = int(daily * minutes / (24 * 60))
    subsidy = state.get("subsidy_daily") or 0
    sub_slice = int(subsidy * minutes / (24 * 60))
    await call.answer()
    await call.message.edit_text(
        f"💰 <b>درآمد خودکار</b>\n\nپرداخت درآمد مالیاتی هر <b>{minutes} دقیقه</b> خودکار انجام می‌شود و "
        "پیام آن برایتان ارسال می‌شود.\n\n"
        f"💵 درآمد روزانه کامل: <b>{fmt(daily)}</b>\n"
        f"⏱ درآمد هر دوره: <b>{fmt(per_tick)}</b>\n"
        + (f"🎁 کسر یارانه هر دوره: <b>{fmt(sub_slice)}</b>\n" if subsidy else "")
        + f"🕐 آخرین پرداخت: {state.get('last_income') or '—'}",
        reply_markup=kb([back_row("g|emp")]))


# ─── پیمان اعتماد: دیدن اطلاعات کامل کشورهای متعهد ───


@router.callback_query(F.data == "g|trust")
async def trust_menu(call: CallbackQuery):
    partners = await trust_partners(call.from_user.id)
    if not partners:
        return await call.answer("پیمان اعتماد فعالی ندارید", show_alert=True)
    lines = ["🤫 <b>اعتماد</b>\nکشورهای دارای پیمان اعتماد با شما — اطلاعات کاملشان را آنی ببینید:\n"]
    rows = []
    for p in partners:
        c = p["country"]
        lines.append(f"• {c['flag']} {c['name']}")
        rows.append([(f"👁 {c['flag']} {c['name']}", f"g|trustv|{p['user_id']}")])
    rows.append(back_row("g|emp"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|trustv|"))
async def trust_view(call: CallbackQuery):
    uid = int(call.data.split("|")[2])
    partners = await trust_partners(call.from_user.id)
    if not any(p["user_id"] == uid for p in partners):
        return await call.answer("پیمان اعتماد فعالی با این کشور ندارید", show_alert=True)
    target_state = await get_state(uid)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (uid,))
    lines = [f"👁 <b>اطلاعات کامل (پیمان اعتماد)</b>\n\n{await country_display(uid, extended=True)}\n"]
    if user:
        lines.append(f"🪙 سکه شاهی: <b>{fmt(user['royal_coins'])}</b>")
    # تجهیزات نظامی
    eqs = await assets_of(uid, "equipment")
    if eqs:
        lines.append("\n🪖 <b>تجهیزات نظامی:</b>")
        for e in eqs:
            lines.append(f"  {e['eq_emoji']} {e['eq_name']} ×{fmt(e['quantity'])} — "
                         f"⚔️{fmt(e['attack_power'] or 0)} 🛡{fmt(e['defense_power'] or 0)}")
    soldiers = await assets_of(uid, "soldier")
    if soldiers:
        lines.append("\n🎖 <b>سربازان:</b>")
        for s in soldiers:
            lines.append(f"  {s['soldier_emoji']} {s['soldier_name']} ×{fmt(s['quantity'])}")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([back_row("g|trust")]))


@router.callback_query(F.data == "g|mg")
async def manage_country(call: CallbackQuery):
    state = await get_state(call.from_user.id)
    await call.answer()
    await call.message.edit_text(
        f"🏛 <b>مدیریت کشور</b>\n\n{blocked_banner(state)}"
        "یکی از بخش‌های کشور خود را انتخاب کنید:",
        reply_markup=manage_kb(),
    )


@router.callback_query(F.data == "g|guide")
async def guide(call: CallbackQuery):
    await call.answer("📖 در حال ارسال راهنما...")
    from core import texts
    guide = await get_setting("guide_text", texts.GUIDE) or texts.GUIDE
    for part in split_text(guide):
        await send_home(call.message, part)
    await send_home(call.message, "📖 پایان راهنما", reply_markup=kb([home_row()]))

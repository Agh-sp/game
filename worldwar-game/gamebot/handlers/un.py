"""سازمان ملل (رای‌گیری/گزارش/تحریم) و بیانیه رسمی."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import (announce, bump_progress, get_country,
                          is_jammed, veto_users)
from core.utils import fmt, jloads, hours_left, fmt_hm, iso, add_hours
from gamebot.common import back_row, kb, send_home
from gamebot.handlers.war import settle_votes

router = Router()


class UNFSM(StatesGroup):
    report_reason = State()
    stmt_text = State()


@router.callback_query(F.data == "g|un")
async def un_menu(call: CallbackQuery):
    await settle_votes(call.bot)
    votes = await db.fetchall(
        "SELECT * FROM un_votes WHERE status='open' AND ends_at>? ORDER BY id DESC", (iso(),))
    lines = ["🕊 <b>سازمان ملل</b>\n"]
    rows = []
    if votes:
        lines.append("🗳 <b>رای‌گیری‌های فعال:</b>")
        for v in votes[:10]:
            ballots = await db.fetchall("SELECT choice, weight FROM un_ballots WHERE vote_id=?", (v["id"],))
            total = sum(b["weight"] for b in ballots)
            lines.append(f"• {v['title']} — {fmt(total)} رأی — {fmt_hm(hours_left(v['ends_at']))} مانده")
            rows.append([(f"🗳 {v['title'][:35]}", f"g|unv|{v['id']}")])
    else:
        lines.append("رای‌گیری فعالی وجود ندارد.")
    lines.append("\n💡 کشورهای قدرتمند اقتصادی و نظامی «حق وتو» دارند و رایشان ۲ برابر حساب می‌شود.")
    rows.append([("⚖️ گزارش کشور", "g|unrep")])
    rows.append(back_row("g|emp"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|unv|"))
async def vote_view(call: CallbackQuery):
    vid = int(call.data.split("|")[2])
    v = await db.fetchone("SELECT * FROM un_votes WHERE id=?", (vid,))
    if not v:
        return await call.answer("یافت نشد", show_alert=True)
    options = jloads(v["options"], [])
    ballots = await db.fetchall("SELECT * FROM un_ballots WHERE vote_id=?", (vid,))
    creator = await get_country(v["created_by"] or 0)
    veto = set(await veto_users())
    is_veto = call.from_user.id in veto
    lines = [
        f"🕊 <b>سازمان ملل — رای‌گیری</b>\n",
        f"📋 {v['title']}",
        f"🏳 پیشنهاددهنده: {creator['flag'] + ' ' + creator['name'] if creator else '—'}",
        f"⏳ پایان: {fmt_hm(hours_left(v['ends_at']))} دیگر",
        f"💪 قدرت رأی شما: {'۲ (حق وتو) 🗡' if is_veto else '۱'}\n",
        "📊 <b>نتایج فعلی:</b>",
    ]
    my_ballot = next((b for b in ballots if b["user_id"] == call.from_user.id), None)
    rows = []
    for i, opt in enumerate(options):
        votes = sum(b["weight"] for b in ballots if b["choice"] == i)
        mine = " 👈 رأی شما" if my_ballot and my_ballot["choice"] == i else ""
        lines.append(f"• {opt}: <b>{fmt(votes)}</b> رأی{mine}")
        if v["status"] == "open":
            rows.append([(f"{opt}", f"g|uvote|{vid}|{i}")])
    if v["status"] != "open":
        lines.append("\n🔒 این رای‌گیری بسته شده است.")
        rows = []
    voters = [(b["user_id"], b["choice"]) for b in ballots]
    if voters:
        lines.append("\n👥 <b>رأی‌دهندگان:</b>")
        for uid, choice in voters[:15]:
            c = await get_country(uid)
            if c:
                badge = " (۲رأی) 🗡" if uid in veto else ""
                lines.append(f"{c['flag']} {c['name']} → {options[choice] if 0 <= choice < len(options) else '?'}{badge}")
    rows.append(back_row("g|un"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|uvote|"))
async def cast_vote(call: CallbackQuery):
    _, _, vid, choice = call.data.split("|")
    vid, choice = int(vid), int(choice)
    v = await db.fetchone("SELECT * FROM un_votes WHERE id=? AND status='open'", (vid,))
    if not v:
        return await call.answer("این رای‌گیری بسته است", show_alert=True)
    if hours_left(v["ends_at"]) <= 0:
        return await call.answer("زمان رای‌گیری تمام شده", show_alert=True)
    veto = set(await veto_users())
    weight = 2 if call.from_user.id in veto else 1
    await db.execute(
        "INSERT INTO un_ballots(vote_id, user_id, choice, weight, voted_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(vote_id, user_id) DO UPDATE SET choice=excluded.choice, weight=excluded.weight",
        (vid, call.from_user.id, choice, weight, iso()))
    await bump_progress(call.from_user.id, "voted")
    options = jloads(v["options"], [])
    await call.answer(f"✅ رأی شما: {options[choice]} ثبت شد")
    await vote_view(call)


# ─── گزارش کشور / تحریم ───


@router.callback_query(F.data == "g|unrep")
async def report_list(call: CallbackQuery):
    if await is_jammed(call.from_user.id):
        return await call.answer("📡 سرورهای شما اختلال دارند!", show_alert=True)
    countries = await db.fetchall(
        "SELECT c.* FROM countries c JOIN users u ON u.id=c.owner_id "
        "WHERE c.owner_id IS NOT NULL AND c.owner_id!=? ORDER BY c.name", (call.from_user.id,))
    rows = [[(f"{c['flag']} {c['name']}", f"g|unrep|{c['owner_id']}")] for c in countries]
    rows.append(back_row("g|un"))
    await call.answer()
    await call.message.edit_text(
        "⚖️ <b>گزارش کشور به سازمان ملل</b>\n\nکدام کشور را گزارش می‌دهید؟ "
        "پس از ذکر دلایل، رای‌گیری برای تحریم انجام می‌شود:\n"
        "• 🔇 خلع سلاح (۷ روز)\n• 🚫 لغو تجارت با همه کشورها\n• 👑 برکناری رهبر (شروع رای‌گیری با سکه شاهی)",
        reply_markup=kb(rows),
    )


@router.callback_query(F.data.startswith("g|unrep|"))
async def report_sanction(call: CallbackQuery):
    target_id = int(call.data.split("|")[2])
    t_country = await get_country(target_id)
    await call.answer()
    await call.message.edit_text(
        f"⚖️ گزارش {t_country['flag']} <b>{t_country['name']}</b>\n\nچه تحریمی درخواست می‌کنید؟",
        reply_markup=kb([
            [("🔇 خلع سلاح", f"g|unsanc|disarm|{target_id}")],
            [("🚫 لغو تجارت", f"g|unsanc|trade|{target_id}")],
            [("👑 برکناری رهبر (۵۰ سکه)", f"g|unsanc|leader|{target_id}")],
            back_row("g|unrep"),
        ]),
    )


@router.callback_query(F.data.startswith("g|unsanc|"))
async def sanction_start(call: CallbackQuery, state: FSMContext):
    _, kind, target_id = call.data.split("|")
    target_id = int(target_id)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if kind == "leader":
        if user["royal_coins"] < 50:
            return await call.answer("🪙 برای برکناری رهبر ۵۰ سکه شاهی لازم است!", show_alert=True)
        await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?", (50, user["id"]))
    await state.set_state(UNFSM.report_reason)
    await state.update_data(sanc_kind=kind, target_id=target_id)
    await call.answer()
    titles = {"disarm": "خلع سلاح", "trade": "لغو تجارت", "leader": "برکناری رهبر"}
    await call.message.edit_text(
        f"⚖️ تحریم «<b>{titles[kind]}</b>» — دلایل خود را بنویسید:\n برای انصراف /cancel"
    )


@router.message(UNFSM.report_reason)
async def sanction_create(message: Message, state: FSMContext):
    reason = (message.text or "").strip()
    if not reason or len(reason) > 500:
        return await send_home(message, "❌ دلیل باید بین ۱ تا ۵۰۰ حرف باشد.")
    data = await state.get_data()
    await state.clear()
    kind, target_id = data["sanc_kind"], data["target_id"]
    t_country = await get_country(target_id)
    m_country = await get_country(message.from_user.id)
    titles = {"disarm": f"خلع سلاح کشور {t_country['name']}",
              "trade": f"لغو تجارت با {t_country['name']}",
              "leader": f"برکناری رهبر {t_country['name']}"}
    hours = float(await get_setting("vote_duration_hours", "24"))
    await db.execute(
        "INSERT INTO un_votes(title, kind, subject_id, options, ends_at, created_by) VALUES(?,?,?,?,?,?)",
        (titles[kind], "sanction", target_id, '["موافق","مخالف"]', add_hours(hours), message.from_user.id))
    await announce(message.bot,
                   f"⚖️ سازمان ملل: درخواست تحریم «{titles[kind]}» توسط "
                   f"{m_country['flag'] if m_country else ''} ثبت شد.\nدلیل: {reason}\n"
                   "کشورها از بخش 🕊 سازمان ملل رأی می‌دهند.")
    await send_home(message, 
        f"✅ درخواست تحریم ثبت شد و در سازمان ملل و کانال اعلام شد.\n"
        f"⏳ پایان رای‌گیری: {fmt_hm(hours)} دیگر — نتیجه به‌طور خودکار اعمال می‌شود.")
    from gamebot.common import kb
    await send_home(message, "🕊 سازمان ملل:", reply_markup=kb([back_row("g|emp")]))


# ─── بیانیه ───


@router.callback_query(F.data == "g|stmt")
async def statement_start(call: CallbackQuery, state: FSMContext):
    if await is_jammed(call.from_user.id):
        # طبق قانون، هنگام اختلال سرور فقط بیانیه مجاز است
        pass
    await state.set_state(UNFSM.stmt_text)
    await call.answer()
    await call.message.edit_text(
        "📢 <b>بیانیه رسمی</b>\n\nمتن بیانیه کشور خود را بنویسید؛ "
        "با تأیید، همراه پرچم حکومتی شما منتشر می‌شود:\n برای انصراف /cancel"
    )


@router.message(UNFSM.stmt_text)
async def statement_confirm(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 2000:
        return await send_home(message, "❌ متن باید بین ۱ تا ۲۰۰۰ حرف باشد.")
    country = await get_country(message.from_user.id)
    if not country:
        await state.clear()
        return await send_home(message, "❌ ابتدا با دستور /start کشور خود را انتخاب کنید.")
    await state.update_data(stmt=text)
    from core.db import db as _db
    st = await _db.fetchone("SELECT government_id FROM states WHERE user_id=?", (message.from_user.id,))
    gov = await _db.fetchone("SELECT * FROM governments WHERE id=?", (st["government_id"],)) if st and st["government_id"] else None
    
    country_flag = country.get("flag") or "🏳️"
    gov_flag = f" {gov['flag']}" if (gov and gov.get("flag")) else ""
    flag_display = f"{country_flag}{gov_flag}"
    gov_name = gov["name"] if gov else "—"
    
    preview = (f"{flag_display} <b>بیانیه رسمی {country['name']}</b>\n🏛 حکومت: {gov_name}\n\n\"{text}\"")
    await state.set_state(None)
    from gamebot.common import kb
    await send_home(message, 
        "👁 <b>پیش‌نمایش بیانیه:</b>\n"
        "<i>(این بیانیه همراه با پرچم رسمی کشورتان در کانال منتشر خواهد شد)</i>\n\n"
        + preview + "\n\nمنتشر می‌کنید؟",
        reply_markup=kb([
            [("✅ انتشار بیانیه", "g|stmtgo")],
            [("✏️ ویرایش متن", "g|stmt")],
            [("❌ انصراف", "g|cancel")],
        ]),
    )


@router.callback_query(F.data == "g|stmtgo")
async def statement_publish(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("stmt")
    await state.clear()
    if not text:
        return await call.answer("متنی ثبت نشده — دوباره بنویسید", show_alert=True)
    country = await get_country(call.from_user.id)
    if not country:
        return await call.answer("❌ کشوری برای شما یافت نشد", show_alert=True)
    st = await db.fetchone("SELECT government_id FROM states WHERE user_id=?", (call.from_user.id,))
    gov = await db.fetchone("SELECT * FROM governments WHERE id=?", (st["government_id"],)) if st and st["government_id"] else None
    
    country_flag = country.get("flag") or "🏳️"
    gov_flag = f" {gov['flag']}" if (gov and gov.get("flag")) else ""
    flag_display = f"{country_flag}{gov_flag}"
    gov_name = gov["name"] if gov else "—"

    full = (f"{flag_display} <b>بیانیه رسمی {country['name']}</b>\n"
            f"🏛 حکومت: {gov_name}\n\n\"{text}\"")
    await db.execute("INSERT INTO statements(user_id, text) VALUES(?,?)", (call.from_user.id, text))
    await bump_progress(call.from_user.id, "statements")
    
    from core.images import announce_statement
    await announce_statement(call.bot, full, country, gov)
    await call.answer("📢 منتشر شد")
    await call.message.edit_text(full + "\n\n✅ بیانیه شما همراه با تصویر پرچم رسمی در کانال منتشر شد.")


# ─── رای‌گیری سیزن جدید (دکمه‌های کانال) ───


@router.callback_query(F.data.startswith("g|svote|"))
async def season_vote_cast(call: CallbackQuery):
    """رأی بازیکن‌ها در کانال به سیزن جدید؛ هر گزینه که زودتر به حد مجاز برسد همان اجرا می‌شود."""
    try:
        _, _, vid, choice = call.data.split("|")
        vid, choice = int(vid), int(choice)
    except ValueError:
        return await call.answer("درخواست نامعتبر", show_alert=True)
    v = await db.fetchone("SELECT * FROM season_votes WHERE id=? AND status='open'", (vid,))
    if not v:
        return await call.answer("این رای‌گیری بسته است", show_alert=True)
    import json as _json
    options = _json.loads(v["options"] or "[]")
    if not 0 <= choice < len(options):
        return await call.answer("گزینه نامعتبر", show_alert=True)
    await db.execute(
        "INSERT INTO season_ballots(vote_id, user_id, choice) VALUES(?,?,?) "
        "ON CONFLICT(vote_id, user_id) DO UPDATE SET choice=excluded.choice",
        (vid, call.from_user.id, choice))
    await call.answer(f"✅ رأی شما: {options[choice]} — با تشکر!", show_alert=False)

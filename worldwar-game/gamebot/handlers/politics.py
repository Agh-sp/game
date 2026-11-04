"""بخش سیاست و رهبری — رئیس‌جمهور کشور، ترور، انقلاب و مهار آن."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

from core.db import get_setting
from core.economy import get_country
from core.politics import (active_revolution, all_leaders, candidates, country_leader,
                           elect_president, revolution_status, suppress_with_force,
                           suppress_with_money)
from core.utils import fmt, fmt_money
from gamebot.common import back_row, kb

router = Router()


async def _pol_text(user_id: int) -> tuple[str, list]:
    country = await get_country(user_id)
    leader = await country_leader(country)
    st = await revolution_status(user_id)
    lines = [f"🏛 <b>سیاست و رهبری — {country['flag'] if country else ''} "
             f"{country['name'] if country else '—'}</b>\n"]
    lines.append(f"{'👤' if not st['active'] else '💀'} {leader['title']}: <b>{leader['name']}</b>")

    buttons = []
    if st["active"]:
        rev = await active_revolution(user_id)
        lines += [
            "",
            "🔥 <b>انقلاب در جریان است!</b>",
            f"📊 شدت ناآرامی: <b>{st['severity']}٪</b>",
            f"⏳ فرصت باقی‌مانده: <b>{st['left']}</b>",
            f"📉 درآمد کشور تا پایان بحران: <b>{round(float(await get_setting('revolution_income_penalty', '0.55')) * 100)}٪</b>",
            "",
            "یکی از راه‌های مهار را انتخاب کنید:",
            "• 🗳 <b>انتخابات فوری</b> — رئیس‌جمهور جدید و آرام‌سازی خیابان‌ها",
            f"• 💸 <b>پول‌پاشی</b> — هزینهٔ این مرحله: {fmt_money(max(1, st['severity']) * 1_200_000)}"
            " (−۳۰٪ شدت)",
            "• 🎖 <b>سرکوب نظامی</b> — شانس‌دار، با تلفات سرباز",
        ]
        buttons.append([("🗳 انتخابات فوری", "g|pol_elec")])
        buttons.append([("💸 پول‌پاشی برای آرام‌سازی", "g|pol_money")])
        buttons.append([("🎖 سرکوب نظامی", "g|pol_force")])
        if rev and rev.get("troops_lost"):
            lines.append(f"\n🪖 تلفات سرکوب تا این لحظه: <b>{fmt(rev['troops_lost'])}</b> سرباز")
        if rev and rev.get("money_spent"):
            lines.append(f"💸 مجموع پول‌پاشی: <b>{fmt_money(rev['money_spent'])}</b>")
    else:
        lines += ["", "🕊 کشور در آرامش است و رهبر در قدرت مستقر است.",
                  "برای تغییر رهبر می‌توانید انتخابات برگزار کنید."]
        buttons.append([("🗳 برگزاری انتخابات", "g|pol_elec")])

    buttons.append([("🌍 رهبران کشورهای جهان", "g|pol_leaders")])
    buttons.append(back_row("g|mg"))
    return "\n".join(lines), buttons


@router.callback_query(F.data == "g|pol")
async def politics_menu(call: CallbackQuery):
    text, rows = await _pol_text(call.from_user.id)
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|pol_elec")
async def election_list(call: CallbackQuery):
    rev = await active_revolution(call.from_user.id)
    rev_id = int(rev["id"]) if rev else 1
    cands = candidates(rev_id)
    lines = ["🗳 <b>انتخابات فوری ریاست‌جمهوری</b>\n",
             "یکی از نامزدها را انتخاب کنید؛ هرکدام اثر فوری متفاوتی دارند:\n"]
    rows = []
    for c in cands:
        lines.append(f"{c['label']} <b>{c['name']}</b>")
        lines.append(f"   ↳ {c['desc']}")
        rows.append([(f"{c['label']} — {c['name']}", f"g|pol_cand|{c['idx']}")])
    rows.append(back_row("g|pol"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|pol_cand|"))
async def election_pick(call: CallbackQuery):
    idx = int(call.data.split("|")[2])
    ok, msg = await elect_president(call.from_user.id, idx, call.bot)
    await call.answer("✅ انتخابات انجام شد" if ok else "❌")
    text, rows = await _pol_text(call.from_user.id)
    await call.message.edit_text(msg + "\n\n" + text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|pol_money")
async def suppress_money(call: CallbackQuery):
    ok, msg = await suppress_with_money(call.from_user.id, call.bot)
    await call.answer("💸" if ok else "❌")
    text, rows = await _pol_text(call.from_user.id)
    await call.message.edit_text(msg + "\n\n" + text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|pol_force")
async def suppress_force(call: CallbackQuery):
    ok, msg = await suppress_with_force(call.from_user.id, call.bot)
    await call.answer("🎖" if ok else "❌")
    text, rows = await _pol_text(call.from_user.id)
    await call.message.edit_text(msg + "\n\n" + text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|pol_leaders")
async def leaders_list(call: CallbackQuery):
    rows_db = await all_leaders()
    lines = ["🌍 <b>رهبران کشورهای جهان</b>\n"]
    buttons = []
    for r in rows_db:
        leader = r["leader"]
        if r.get("revolution"):
            state_txt = f"🔥 انقلاب {r['revolution']['severity']}٪"
        else:
            state_txt = "🟢"
        lines.append(f"• {r['flag']} <b>{r['name']}</b> — {leader['title']}: {leader['name']} {state_txt}")
    # دکمه‌های هدف ترور برای کشورهایی که بازیکن دارند
    targets = [r for r in rows_db if r.get("player_id") and r["player_id"] != call.from_user.id]
    for r in targets[:10]:
        buttons.append([(f"🎯 ترور {r['leader']['name']}", f"g|cy|assass|{r['player_id']}")])
    buttons.append(back_row("g|pol"))
    await call.answer()
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))
    except Exception:
        await call.message.answer("\n".join(lines), reply_markup=kb(buttons))

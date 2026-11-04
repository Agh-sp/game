"""مدیریت کشور — دین و حکومت (با تغییر پرچم بر اساس حکومت)."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from core.db import db
from core.economy import get_country, get_state, my_gov_religion, satisfaction_recompute
from core.utils import jloads
from gamebot.common import back_row, kb

router = Router()


@router.callback_query(F.data == "g|gov")
async def gov_menu(call: CallbackQuery):
    state = await get_state(call.from_user.id)
    gov, rel = await my_gov_religion(call.from_user.id)
    country = await get_country(call.from_user.id)
    flag = country["flag"] if country else "🏳"
    if gov and gov.get("flag"):
        flag += gov["flag"]
    await call.answer()
    await call.message.edit_text(
        f"⛪ <b>دین و حکومت</b>\n\n"
        f"🏳 پرچم فعلی: {flag}\n"
        f"⛪ دین: <b>{rel['name'] if rel else '—'}</b>\n"
        f"🏛 حکومت: <b>{gov['name'] if gov else '—'}</b>\n\n"
        "با تغییر حکومت، پرچم نمایشی کشور شما عوض می‌شود. اثر قوانین هم به دین و حکومت بستگی دارد.",
        reply_markup=kb([
            [("⛪ تغییر دین", "g|rel")],
            [("🏛 تغییر حکومت", "g|govsel")],
            back_row("g|mg"),
        ]),
    )


def _effects_text(effects: dict) -> str:
    labels = {
        "satisfaction": "رضایت", "attack": "قدرت حمله", "defense": "قدرت دفاع",
        "trade": "تجارت", "science": "علم", "welfare": "رفاه", "religion": "اثر دین",
        "laws": "اثر قوانین", "tax": "مالیات",
    }
    parts = []
    for k, v in effects.items():
        sign = "+" if float(v) >= 0 else ""
        parts.append(f"{labels.get(k, k)} {sign}{v}%")
    return " | ".join(parts) if parts else "بدون اثر خاص"


@router.callback_query(F.data == "g|rel")
async def religion_list(call: CallbackQuery):
    rels = await db.fetchall("SELECT * FROM religions WHERE is_active=1 ORDER BY id")
    rows = []
    lines = ["⛪ <b>انتخاب دین</b>\n"]
    for r in rels:
        eff = _effects_text(jloads(r["effects"], {}))
        lines.append(f"{r['emoji']} <b>{r['name']}</b> — {r['description'] or ''}\n   اثر: {eff}")
        rows.append([(f"{r['emoji']} {r['name']}", f"g|relc|{r['id']}")])
    rows.append(back_row("g|gov"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|relc|"))
async def religion_confirm(call: CallbackQuery):
    rid = int(call.data.split("|")[2])
    r = await db.fetchone("SELECT * FROM religions WHERE id=?", (rid,))
    if not r:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("UPDATE states SET religion_id=? WHERE user_id=?", (rid, call.from_user.id))
    await satisfaction_recompute(call.from_user.id)
    await call.answer(f"✅ دین کشور شما {r['name']} شد")
    await gov_menu(call)


@router.callback_query(F.data == "g|govsel")
async def government_list(call: CallbackQuery):
    govs = await db.fetchall("SELECT * FROM governments WHERE is_active=1 ORDER BY id")
    rows = []
    lines = ["🏛 <b>انتخاب حکومت</b>\n"]
    for g in govs:
        eff = _effects_text(jloads(g["effects"], {}))
        lines.append(f"{g['emoji']} <b>{g['name']}</b> — {g['description'] or ''}\n   اثر: {eff}")
        rows.append([(f"{g['emoji']} {g['name']}", f"g|govc|{g['id']}")])
    rows.append(back_row("g|gov"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|govc|"))
async def government_confirm(call: CallbackQuery):
    gid = int(call.data.split("|")[2])
    g = await db.fetchone("SELECT * FROM governments WHERE id=?", (gid,))
    if not g:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("UPDATE states SET government_id=? WHERE user_id=?", (gid, call.from_user.id))
    await satisfaction_recompute(call.from_user.id)
    country = await get_country(call.from_user.id)
    await call.answer("✅ حکومت تغییر کرد")
    if country:
        from core.economy import announce
        await announce(call.bot,
                       f"{country['flag']}{g['flag']} کشور {country['name']} حکومت خود را به «{g['name']}» تغییر داد!")
    await gov_menu(call)

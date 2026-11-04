"""امپراطوری من — سازمان نجات (حمایت از جنگ‌زدگان با رای‌گیری و انرژی اهدایی)."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import get_country, get_state
from core.rescue import campaign_list, donate, donors_of
from core.utils import fmt, hours_left, fmt_hm
from gamebot.common import back_row, kb, send_home

router = Router()


class RescueFSM(StatesGroup):
    donate_qty = State()


async def _cname(user_id: int) -> str:
    c = await get_country(user_id)
    return f"{c['flag']} {c['name']}" if c else "؟"


@router.callback_query(F.data == "g|resc")
async def rescue_menu(call: CallbackQuery):
    if await get_setting("sec_rescue_org", "1") != "1":
        await call.answer("بخش سازمان نجات توسط ادمین خاموش شده است", show_alert=True)
        return
    campaigns = await campaign_list()
    state = await get_state(call.from_user.id)
    lines = ["🛟 <b>سازمان نجات (مراقبت از جنگ‌زدگان)</b>\n",
             "برای هر جنگ فعال یک بخش مجزا با رای‌گیری جدا باز می‌شود.\n"
             "🗳 با اهدای انرژی رأی می‌دهید (فقط اهداکنندگان حق رأی دارند). "
             "اگر اکثریت رأی با یک کشور باشد، ۱۰٪ ذخیره سازمان به آن کشور پرداخت می‌شود.\n",
             f"⚡️ انرژی شما: <b>{fmt(state.get('energy') or 0)}</b> kWh\n",
             "🔒 مقدار ذخیره سازمان مخفی است.\n"]
    rows = []
    if not campaigns:
        lines.append("— در حال حاضر جنگ فعالی وجود ندارد؛ این بخش فقط هنگام جنگ فعال می‌شود —")
    for c in campaigns:
        att, deff = await _cname(c["attacker_id"]), await _cname(c["defender_id"])
        donors = await donors_of(c["id"])
        my_vote = next((d for d in donors if d["user_id"] == call.from_user.id), None)
        lines.append(f"\n⚔️ <b>جنگ {att} علیه {deff}</b> — کمپین #{c['id']}")
        lines.append(f"👥 حامیان: {len(donors)} کشور | ⏳ {fmt_hm(hours_left(c['ends_at']))} مانده")
        if my_vote:
            lines.append(f"🗳 رأی شما: {await _cname(my_vote['voted_for'])}")
        rows.append([(f"🏥 کمپین #{c['id']} — {att} ⚔ {deff}", f"g|rescc|{c['id']}")])
    rows.append(back_row("g|emp"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|rescc|"))
async def campaign_view(call: CallbackQuery):
    cid = int(call.data.split("|")[2])
    c = await db.fetchone("SELECT rc.*, w.attacker_id, w.defender_id FROM rescue_campaigns rc "
                          "JOIN wars w ON w.id=rc.war_id WHERE rc.id=?", (cid,))
    if not c or c["status"] != "open":
        return await call.answer("کمپین بسته است", show_alert=True)
    att, deff = await _cname(c["attacker_id"]), await _cname(c["defender_id"])
    donors = await donors_of(cid)
    lines = [f"🏥 <b>کمپین نجات #{cid}</b>\n",
             f"⚔️ جنگ {att} علیه {deff}",
             f"⏳ {fmt_hm(hours_left(c['ends_at']))} مانده",
             f"👥 حامیان: {len(donors)} کشور\n",
             "برای رأی دادن، انرژی اهدا کنید (رأی شما = کشوری که در آخرین اهدا انتخاب کردید):"]
    rows = [
        [(f"⚡️ اهدای انرژی → {att}", f"g|rescdon|{cid}|{c['attacker_id']}")],
        [(f"⚡️ اهدای انرژی → {deff}", f"g|rescdon|{cid}|{c['defender_id']}")],
    ]
    if donors:
        lines.append("\n🗳 <b>رأی‌های فعلی:</b>")
        tally = {}
        for d in donors:
            tally[d["voted_for"]] = tally.get(d["voted_for"], 0) + 1
        for uid, cnt in tally.items():
            lines.append(f"• {await _cname(uid)}: {cnt} رأی")
    rows.append(back_row("g|resc"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|rescdon|"))
async def donate_start(call: CallbackQuery, state: FSMContext):
    _, _, cid, voted = call.data.split("|")
    st = await get_state(call.from_user.id)
    if (st.get("energy") or 0) <= 0:
        return await call.answer("❌ انرژی ندارید! مازاد برق هر ۳۰ دقیقه به انبار می‌رود.", show_alert=True)
    await state.set_state(RescueFSM.donate_qty)
    await state.update_data(cid=int(cid), voted=int(voted))
    await call.answer()
    await call.message.edit_text(
        f"⚡️ <b>اهدای انرژی به سازمان نجات</b>\n"
        f"موجودی: {fmt(st.get('energy') or 0)} kWh\nهدف رأی: {await _cname(int(voted))}\n\n"
        "چند کیلووات‌ساعت اهدا می‌کنید؟\n برای انصراف /cancel")


@router.message(RescueFSM.donate_qty)
async def donate_input(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد بفرستید.")
    if qty <= 0:
        return await send_home(message, "❌ عدد باید مثبت باشد.")
    data = await state.get_data()
    await state.clear()
    msg = await donate(message.bot, data["cid"], message.from_user.id, qty, data["voted"])
    await send_home(message, msg)
    fake = _fake_call(message, f"g|rescc|{data['cid']}")
    await campaign_view(fake)


class _fake_call:
    def __init__(self, message: Message, data: str = ""):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot
        self.data = data

    async def answer(self, *_a, **_k):
        pass

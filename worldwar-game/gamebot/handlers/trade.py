"""تجارت بین‌المللی (بازسازی کامل) — مذاکره مخفیانه، پیمان‌ها، تجارت مستقیم،
فروش انرژی به سازمان نجات و تنگه‌های راهبردی."""
import json

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import get_country, get_state
from core.events import log_event
from core.images import announce_img
from core.treaties import (TREATY_KINDS, break_treaty, confirm_treaty,
                           create_treaty, find_treaty, reject_treaty,
                           announce_treaty, active_treaties, diplomacy_add)
from core.straits import capture_strait, straits_menu_text
from core.utils import fmt, iso, clamp
from gamebot.common import back_row, kb, send_home, dm

router = Router()
neg_router = Router()  # آخرین روتر — برای گفتگوی آزاد مذاکره

TRADE_RESOURCES = {
    "money": "💰 پول",
    "coins": "🪙 سکه شاهی",
    "energy": "⚡️ انرژی (kWh)",
    "water": "💧 آب (واحد)",
    "gas": "🔥 گاز (واحد)",
    "oil": "🛢 نفت (بشکه)",
    "equip": "🪖 تجهیزات نظامی",
    "soldier": "🎖 سرباز",
}


class TradeFSM(StatesGroup):
    trade_percent = State()
    dt_qty = State()
    rs_qty = State()


async def _cname(user_id: int) -> str:
    c = await get_country(user_id)
    return f"{c['flag']} {c['name']}" if c else "؟"


def _sec_on(key: str):
    async def check() -> bool:
        return await get_setting(key, "1") == "1"
    return check


# ─── منوی اصلی تجارت ───


@router.callback_query(F.data == "g|trd")
async def trade_menu(call: CallbackQuery):
    treaties = await active_treaties(call.from_user.id)
    lines = ["🤝 <b>تجارت بین‌المللی</b>\n"]
    if treaties:
        lines.append("📜 <b>پیمان‌های فعال من:</b>")
        for t in treaties[:8]:
            other = t["party_b"] if t["party_a"] == call.from_user.id else t["party_a"]
            title = TREATY_KINDS.get(t["kind"], ("پیمان",))[0]
            extra = f" ({round(t['trade_percent'])}٪)" if t["kind"] == "trade" and t["trade_percent"] else ""
            lines.append(f"• {title} با {await _cname(other)}{extra}")
        lines.append("")
    rows = []
    if await get_setting("sec_negotiation", "1") == "1":
        rows.append([("🕊 مذاکره", "g|neg")])
    if await get_setting("sec_direct_trade", "1") == "1":
        rows.append([("🔁 تجارت مستقیم", "g|dtrd")])
    if await get_setting("sec_rescue_sale", "1") == "1":
        rows.append([("🏥 فروش انرژی به سازمان نجات", "g|rsale")])
    if await get_setting("sec_straits", "1") == "1":
        rows.append([("⚓ تنگه‌ها", "g|strait")])
    rows.append([("📜 پیمان‌های من", "g|mytrt")])
    rows.append(back_row("g|emp"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data == "g|mytrt")
async def my_treaties(call: CallbackQuery):
    treaties = await active_treaties(call.from_user.id)
    lines = ["📜 <b>پیمان‌های فعال من</b>\n"]
    if not treaties:
        lines.append("— پیمان فعالی ندارید — از مسیر مذاکره پیمان ببندید.")
    for t in treaties:
        other = t["party_b"] if t["party_a"] == call.from_user.id else t["party_a"]
        w = await get_country(t["witness_id"]) if t["witness_id"] else None
        title = TREATY_KINDS.get(t["kind"], ("پیمان",))[0]
        lines.append(f"• {title} با {await _cname(other)}"
                     + (f" | شاهد: {w['flag']} {w['name']}" if w else "")
                     + (f" | {round(t['trade_percent'])}٪ تجاری" if t["kind"] == "trade" else ""))
        lines.append(f"   {TREATY_KINDS.get(t['kind'], ('', ''))[1][:110]}")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([back_row("g|trd")]))


# ═══════════════ مذاکره ═══════════════


async def _countries_kb(user_id: int, cb_prefix: str) -> list:
    countries = await db.fetchall(
        "SELECT c.* FROM countries c JOIN users u ON u.id=c.owner_id "
        "WHERE c.owner_id IS NOT NULL AND c.owner_id!=? ORDER BY c.name", (user_id,))
    return [[(f"{c['flag']} {c['name']}", f"{cb_prefix}{c['owner_id']}")] for c in countries]


@router.callback_query(F.data == "g|neg")
async def negotiation_menu(call: CallbackQuery):
    mine = await db.fetchall(
        "SELECT n.* FROM negotiations n JOIN negotiation_members m ON m.neg_id=n.id "
        "WHERE m.user_id=? AND n.status IN ('pending','open') ORDER BY n.id DESC",
        (call.from_user.id,))
    lines = ["🕊 <b>مذاکره مخفیانه</b>\n",
             "با یک کشور مذاکره کنید؛ گفتگو فقط داخل ربات مخفی می‌ماند اما شروع آن در کانال اعلام می‌شود. "
             "در مذاکره می‌توانید کشور سومی را عضو کنید و در پایان «به نتیجه رسیدیم» را بزنید تا لیست پیمان‌ها بیاید."]
    rows = []
    if mine:
        lines.append("\n📡 <b>مذاکره‌های من:</b>")
        for n in mine:
            members = await db.fetchall(
                "SELECT user_id FROM negotiation_members WHERE neg_id=?", (n["id"],))
            names = []
            for m in members:
                c = await get_country(m["user_id"])
                if c:
                    names.append(f"{c['flag']}{c['name']}")
            status = "⏳ در انتظار تأیید" if n["status"] == "pending" else "🟢 باز"
            lines.append(f"• #{n['id']} — {' + '.join(names)} — {status}")
            if n["status"] == "open":
                rows.append([(f"💬 مذاکره #{n['id']}", f"g|negroom|{n['id']}")])
    rows.append([("➕ مذاکره جدید", "g|negnew")])
    rows.append(back_row("g|trd"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data == "g|negnew")
async def negotiation_new(call: CallbackQuery):
    rows = await _countries_kb(call.from_user.id, "g|negr|")
    if not rows:
        return await call.answer("کشور دیگری موجود نیست", show_alert=True)
    rows.append(back_row("g|neg"))
    await call.answer()
    await call.message.edit_text(
        "🕊 <b>مذاکره جدید</b>\n\nکشور مورد نظر برای مذاکره را انتخاب کنید:",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|negr|"))
async def negotiation_request(call: CallbackQuery):
    target = int(call.data.split("|")[2])
    existing = await db.fetchone(
        "SELECT n.id FROM negotiations n JOIN negotiation_members m ON m.neg_id=n.id "
        "WHERE m.user_id=? AND n.status IN ('pending','open')", (call.from_user.id,))
    if existing:
        return await call.answer("شما در یک مذاکره فعال هستید!", show_alert=True)
    if target == call.from_user.id:
        return await call.answer("خودتان را انتخاب کردید!", show_alert=True)
    neg_id = await db.execute(
        "INSERT INTO negotiations(initiator_id, status) VALUES(?, 'pending')", (call.from_user.id,))
    await db.execute(
        "INSERT INTO negotiation_members(neg_id, user_id, role) VALUES(?,?,'host')",
        (neg_id, call.from_user.id))
    try:
        await dm(call.bot, 
            target,
            f"🕊 کشور {await _cname(call.from_user.id)} درخواست <b>مذاکره مخفیانه</b> دارد.\n"
            "در صورت تأیید، شروع مذاکره در کانال اعلام می‌شود.",
            reply_markup=kb([
                [("✅ تأیید مذاکره", f"g|nega|{neg_id}")],
                [("❌ رد درخواست", f"g|negd|{neg_id}")],
            ]))
    except Exception:
        pass
    await call.answer("📨 درخواست مذاکره ارسال شد")
    await negotiation_menu(call)


async def _open_room(bot, neg_id: int) -> None:
    """اعلام کانال + پیام اتاق مذاکره برای اعضا."""
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=?", (neg_id,))
    members = await db.fetchall(
        "SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))
    names = []
    for m in members:
        c = await get_country(m["user_id"])
        if c:
            names.append(f"{c['flag']} {c['name']}")
    section = "negotiation" if len(members) == 2 else "negotiation3"
    await announce_img(bot, "🕊 " + " و ".join(names) + " وارد مذاکره شدند.", section)
    await log_event("negotiation", " و ".join(names) + " مذاکره را شروع کردند")
    for m in members:
        try:
            await dm(bot, 
                m["user_id"],
                f"🕊 <b>اتاق مذاکره #{neg_id}</b>\n\nمذاکره {(' و ').join(names)} شروع شد!\n"
                "💬 پیام‌هایتان را همین‌جا در چت بنویسید تا به اعضای مذاکره ارسال شود.\n"
                "• هر زمان به نتیجه رسیدید، دکمه «🤝 به توافق رسیدیم» را بزنید.\n"
                "• می‌توانید کشور سومی را نیز به عنوان شاهد یا عضو دعوت کنید.",
                reply_markup=kb([
                    [("🤝 به توافق رسیدیم", f"g|negok|{neg_id}")],
                    [("➕ عضو کردن کشور سوم", f"g|neginv|{neg_id}")],
                    [("❌ به نتیجه نرسیدیم و لغو", f"g|negno|{neg_id}")],
                ]))
        except Exception:
            pass


@router.callback_query(F.data.startswith("g|nega|"))
async def negotiation_approve(call: CallbackQuery):
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=? AND status='pending'", (neg_id,))
    if not neg or neg["initiator_id"] == call.from_user.id:
        return await call.answer("درخواست یافت نشد", show_alert=True)
    await db.execute(
        "INSERT OR IGNORE INTO negotiation_members(neg_id, user_id, role) VALUES(?,?,'guest')",
        (neg_id, call.from_user.id))
    await db.execute("UPDATE negotiations SET status='open' WHERE id=?", (neg_id,))
    await call.answer("✅ مذاکره شروع شد")
    try:
        await dm(call.bot, neg["initiator_id"],
                                    f"✅ کشور {await _cname(call.from_user.id)} مذاکره را پذیرفت!")
    except Exception:
        pass
    await _open_room(call.bot, neg_id)
    await negotiation_menu(call)


@router.callback_query(F.data.startswith("g|negd|"))
async def negotiation_decline(call: CallbackQuery):
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=? AND status='pending'", (neg_id,))
    if not neg:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("UPDATE negotiations SET status='rejected', ended_at=? WHERE id=?",
                     (iso(), neg_id))
    try:
        await dm(call.bot, neg["initiator_id"], "❌ درخواست مذاکره شما رد شد.")
    except Exception:
        pass
    await call.answer("رد شد")
    await negotiation_menu(call)


@router.callback_query(F.data.startswith("g|negroom|"))
async def negotiation_room(call: CallbackQuery):
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=? AND status='open'", (neg_id,))
    if not neg:
        return await call.answer("مذاکره بسته است", show_alert=True)
    members = await db.fetchall("SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))
    if call.from_user.id not in {m["user_id"] for m in members}:
        return await call.answer("عضو این مذاکره نیستید", show_alert=True)
    msgs = await db.fetchall(
        "SELECT * FROM negotiation_msgs WHERE neg_id=? ORDER BY id DESC LIMIT 10", (neg_id,))
    lines = [f"💬 <b>اتاق مذاکره #{neg_id}</b>\n"]
    for m in reversed(msgs):
        lines.append(f"👤 {await _cname(m['sender_id'])}: {m['text'][:200]}")
    if not msgs:
        lines.append("— هنوز پیامی رد و بدل نشده —")
    lines.append("\nپیام بعدی خود را در کادر چت بنویسید و ارسال کنید ✍️")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("🤝 به توافق رسیدیم (انعقاد معاهده)", f"g|negok|{neg_id}")],
        [("➕ عضو کردن کشور سوم", f"g|neginv|{neg_id}")],
        [("❌ به نتیجه نرسیدیم و خروج", f"g|negno|{neg_id}")],
        back_row("g|neg"),
    ]))


# ─── گفتگوی آزاد مذاکره (آخرین روتر) ───


@neg_router.message(F.text & ~F.text.startswith("/"))
async def negotiation_relay(message: Message, state: FSMContext):
    """هر متن عادی عضوِ مذاکره باز (بدون FSM فعال) به اعضای دیگر Relay می‌شود."""
    if await state.get_state() is not None:
        raise SkipHandler
    row = await db.fetchone(
        "SELECT n.* FROM negotiations n JOIN negotiation_members m ON m.neg_id=n.id "
        "WHERE m.user_id=? AND n.status='open'", (message.from_user.id,))
    if not row:
        raise SkipHandler
    neg_id = row["id"]
    text = (message.text or "").strip()
    if not text or len(text) > 700:
        return
    await db.execute(
        "INSERT INTO negotiation_msgs(neg_id, sender_id, text) VALUES(?,?,?)",
        (neg_id, message.from_user.id, text))
    members = await db.fetchall(
        "SELECT user_id FROM negotiation_members WHERE neg_id=? AND user_id!=?",
        (neg_id, message.from_user.id))
    sender_name = await _cname(message.from_user.id)
    for m in members:
        try:
            await dm(message.bot, 
                m["user_id"],
                f"🕊 <b>مذاکره</b> — از {sender_name}:\n\n{text}",
                reply_markup=kb([
                    [("✅ به نتیجه رسیدیم", f"g|negok|{neg_id}"),
                     ("❌ به نتیجه نرسیدم", f"g|negno|{neg_id}")],
                ]))
        except Exception:
            pass


# ─── دعوت کشور سوم ───


@router.callback_query(F.data.startswith("g|neginv|"))
async def invite_third(call: CallbackQuery):
    neg_id = int(call.data.split("|")[2])
    members = {m["user_id"] for m in await db.fetchall(
        "SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))}
    if call.from_user.id not in members:
        return await call.answer("عضو نیستید", show_alert=True)
    countries = await db.fetchall(
        "SELECT c.* FROM countries c JOIN users u ON u.id=c.owner_id "
        "WHERE c.owner_id IS NOT NULL ORDER BY c.name")
    rows = []
    for c in countries:
        if c["owner_id"] not in members:
            rows.append([(f"{c['flag']} {c['name']}", f"g|neginvr|{neg_id}|{c['owner_id']}")])
    if not rows:
        return await call.answer("کشور سومی موجود نیست", show_alert=True)
    rows.append(back_row("g|neg"))
    await call.answer()
    await call.message.edit_text(
        "➕ <b>عضو کردن کشور سوم</b>\nکشور سوم انتخاب شود؛ پس از پذیرش او، "
        "پیام عضویت با عکس مذاکره سه‌نفره در کانال گذاشته می‌شود:",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|neginvr|"))
async def invite_third_send(call: CallbackQuery):
    _, _, neg_id, target = call.data.split("|")
    neg_id, target = int(neg_id), int(target)
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=? AND status='open'", (neg_id,))
    if not neg:
        return await call.answer("مذاکره باز نیست", show_alert=True)
    members = await db.fetchall("SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))
    names = []
    for m in members:
        c = await get_country(m["user_id"])
        if c:
            names.append(f"{c['flag']} {c['name']}")
    try:
        await dm(call.bot, 
            target,
            f"🕊 کشورهای {' و '.join(names)} شما را به <b>مذاکره</b> دعوت کرده‌اند.\n"
            "در صورت پیوستن، مذاکره سه‌نفره در کانال اعلام می‌شود.",
            reply_markup=kb([
                [("✅ پیوستن به مذاکره", f"g|neginva|{neg_id}")],
                [("❌ رد دعوت", f"g|negd|{neg_id}")],
            ]))
    except Exception:
        pass
    await call.answer("📨 دعوت ارسال شد")


@router.callback_query(F.data.startswith("g|neginva|"))
async def invite_third_accept(call: CallbackQuery):
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=? AND status='open'", (neg_id,))
    if not neg:
        return await call.answer("مذاکره باز نیست", show_alert=True)
    await db.execute(
        "INSERT OR IGNORE INTO negotiation_members(neg_id, user_id, role) VALUES(?,?,'third')",
        (neg_id, call.from_user.id))
    # اعلام مجدد در کانال با عکس مذاکره سه نفره
    members = await db.fetchall("SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))
    names = []
    for m in members:
        c = await get_country(m["user_id"])
        if c:
            names.append(f"{c['flag']} {c['name']}")
    await announce_img(call.bot,
                       "🕊 کشور " + await _cname(call.from_user.id) +
                       " به مذاکره " + " و ".join(names[:-1]) + " پیوست — مذاکره سه‌نفره آغاز شد.",
                       "negotiation3")
    await log_event("negotiation", f"{' ، '.join(names)} مذاکره سه‌نفره شدند")
    for m in members:
        if m["user_id"] != call.from_user.id:
            try:
                await dm(call.bot, m["user_id"],
                                            f"➕ کشور {await _cname(call.from_user.id)} به مذاکره پیوست.")
            except Exception:
                pass
    await call.answer("✅ پیوستید")
    await negotiation_room(call)


# ─── پایان مذاکره ───


@router.callback_query(F.data.startswith("g|negno|"))
async def negotiation_fail(call: CallbackQuery):
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=? AND status IN ('pending','open')", (neg_id,))
    if not neg:
        return await call.answer("مذاکره بسته است", show_alert=True)
    await db.execute("UPDATE negotiations SET status='failed', ended_at=? WHERE id=?", (iso(), neg_id))
    members = await db.fetchall("SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))
    for m in members:
        if m["user_id"] != call.from_user.id:
            try:
                await dm(call.bot, 
                    m["user_id"],
                    f"❌ کشور {await _cname(call.from_user.id)} اعلام کرد مذاکره «به نتیجه نرسید». مذاکره بسته شد.")
            except Exception:
                pass
    await call.answer("مذاکره بسته شد")
    await negotiation_menu(call)


@router.callback_query(F.data.startswith("g|negok|"))
async def negotiation_success(call: CallbackQuery):
    """«به نتیجه رسیدیم» → لیست پیمان‌ها."""
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=? AND status='open'", (neg_id,))
    if not neg:
        return await call.answer("مذاکره باز نیست", show_alert=True)
    members = await db.fetchall("SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))
    if call.from_user.id not in {m["user_id"] for m in members}:
        return await call.answer("عضو نیستید", show_alert=True)
    # در مذاکره سه‌نفره، طرف قرارداد انتخاب می‌شود
    others = [m["user_id"] for m in members if m["user_id"] != call.from_user.id]
    if len(others) > 1:
        rows = []
        for uid in others:
            rows.append([(f"🤝 قرارداد با {await _cname(uid)}", f"g|trtyp|{neg_id}|{uid}")])
        rows.append(back_row("g|neg"))
        await call.answer()
        return await call.message.edit_text(
            "🤝 با کدام کشور قرارداد می‌بندید؟", reply_markup=kb(rows))
    await _treaty_list(call, neg_id, others[0])


async def _treaty_list(call: CallbackQuery, neg_id: int, counterpart: int):
    lines = [f"📜 <b>پیمان‌ها</b>\nقرارداد بین شما و {await _cname(counterpart)}:\n"]
    rows = []
    for kind, (title, desc) in TREATY_KINDS.items():
        lines.append(f"<b>{title}</b>: {desc}\n")
        rows.append([(title, f"g|trty|{neg_id}|{kind}|{counterpart}")])
    rows.append(back_row("g|neg"))
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|trtyp|"))
async def treaty_pick_counterpart(call: CallbackQuery):
    _, _, neg_id, uid = call.data.split("|")
    await _treaty_list(call, int(neg_id), int(uid))


# ─── ساخت پیمان ───


async def _witness_picker(call: CallbackQuery, neg_id: int, kind: str, counterpart: int):
    """انتخاب کشور سوم به عنوان شاهد (پیمان اعتماد)."""
    members = {m["user_id"] for m in await db.fetchall(
        "SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))}
    countries = await db.fetchall(
        "SELECT c.* FROM countries c JOIN users u ON u.id=c.owner_id "
        "WHERE c.owner_id IS NOT NULL ORDER BY c.name")
    rows = []
    for c in countries:
        if c["owner_id"] not in members:
            rows.append([(f"👁 شاهد: {c['flag']} {c['name']}",
                          f"g|trtwit|{neg_id}|{kind}|{counterpart}|{c['owner_id']}")])
    if not rows:
        return await call.answer("کشور سومی برای شاهد نیست", show_alert=True)
    rows.append(back_row("g|neg"))
    await call.answer()
    await call.message.edit_text(
        "👁 <b>انتخاب شاهد</b>\nپیمان اعتماد به تأیید و امضای یک کشور سوم نیاز دارد؛ "
        "شاهد در سازمان ملل ضامن قرارداد خواهد بود:",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|trty|"))
async def treaty_create(call: CallbackQuery, state: FSMContext):
    _, _, neg_id, kind, counterpart = call.data.split("|")
    neg_id, counterpart = int(neg_id), int(counterpart)
    me = call.from_user.id
    if kind == "trust":
        # شاهد: عضو سوم مذاکره یا انتخاب کشور
        members = [m["user_id"] for m in await db.fetchall(
            "SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))]
        others = [u for u in members if u not in (me, counterpart)]
        if others:
            return await _make_treaty(call, neg_id, kind, counterpart, others[0])
        return await _witness_picker(call, neg_id, kind, counterpart)
    if kind == "trade":
        await state.set_state(TradeFSM.trade_percent)
        await state.update_data(neg_id=neg_id, kind=kind, counterpart=counterpart)
        await call.answer()
        return await call.message.edit_text(
            "💼 <b>رفیقای تجاری</b>\n\nدرصد سود هر طرف از پول فروش‌های طرف مقابل (۱ تا ۵۰):\n"
            " برای انصراف /cancel")
    if kind == "peace":
        war = await db.fetchone(
            "SELECT * FROM wars WHERE status='active' AND "
            "((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?))",
            (me, counterpart, counterpart, me))
        if not war:
            return await call.answer("❌ پیمان صلح فقط حین جنگ فعال بین دو طرف ممکن است!", show_alert=True)
        return await _make_treaty(call, neg_id, kind, counterpart, None)
    if kind == "brothers":
        return await _brothers_select(call, state, neg_id, counterpart)
    return await _make_treaty(call, neg_id, kind, counterpart, None)


async def _brothers_select(call: CallbackQuery, state: FSMContext, neg_id: int, counterpart: int):
    await state.update_data(neg_id=neg_id, counterpart=counterpart, bro={"military": True, "trade": False, "trust": False})
    await call.answer()
    await _brothers_render(call, state)


async def _brothers_render(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bro: dict = data.get("bro", {})
    rows = [
        [(("✅ " if bro.get("military") else "▫️ ") + "پیمان نظامی", "g|broadd|military"),
         (("✅ " if bro.get("trade") else "▫️ ") + "رفیقای تجاری", "g|broadd|trade")],
        [(("✅ " if bro.get("trust") else "▫️ ") + "پیمان اعتماد", "g|broadd|trust")],
        [("🤝 نهایی کردن برادران تنی", "g|bropok")],
        back_row("g|neg"),
    ]
    await call.message.edit_text(
        "👥 <b>برادران تنی</b>\nکدام پیمان‌ها یکجا انجام شوند؟ (تجاری = ۱۰٪):\n"
        "💡 در صورت جنگ فعال، پیمان صلح هم خودکار اضافه می‌شود.",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|broadd|"))
async def brothers_toggle(call: CallbackQuery, state: FSMContext):
    kind = call.data.split("|")[2]
    data = await state.get_data()
    bro: dict = data.get("bro", {})
    if kind in bro:
        bro[kind] = not bro[kind]
        await state.update_data(bro=bro)
    await call.answer()
    await _brothers_render(call, state)


@router.callback_query(F.data == "g|bropok")
async def brothers_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bro: dict = data.get("bro", {})
    counterpart = data.get("counterpart")
    neg_id = data.get("neg_id")
    me = call.from_user.id
    if not counterpart or not any(bro.values()):
        return await call.answer("حداقل یک پیمان انتخاب کنید", show_alert=True)
    await state.clear()
    witness = None
    if bro.get("trust"):
        members = [m["user_id"] for m in await db.fetchall(
            "SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))]
        others = [u for u in members if u not in (me, counterpart)]
        witness = others[0] if others else None
    made = []
    for kind in ("military", "trade", "trust"):
        if bro.get(kind):
            if kind == "trust" and witness is None:
                continue
            tid = await create_treaty(kind, me, counterpart, neg_id, witness,
                                      10 if kind == "trade" else 0)
            made.append((tid, kind))
    war = await db.fetchone(
        "SELECT * FROM wars WHERE status='active' AND "
        "((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?))",
        (me, counterpart, counterpart, me))
    if war:
        tid = await create_treaty("peace", me, counterpart, neg_id, None, 0)
        made.append((tid, "peace"))
    if not made:
        return await call.answer("پیمانی ساخته نشد (شاهد لازم است)", show_alert=True)
    await _request_confirmations(call.bot, made, me, counterpart, witness)
    await call.answer("✅ پیمان‌های برادران تنی ساخته شد — در انتظار تأیید طرف‌ها")
    await my_treaties(call)


@router.message(TradeFSM.trade_percent)
async def trade_percent_input(message: Message, state: FSMContext):
    try:
        pct = int(message.text.strip().replace("٪", "").replace("%", ""))
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد (درصد) بفرستید.")
    if not 1 <= pct <= 50:
        return await send_home(message, "❌ درصد باید بین ۱ تا ۵۰ باشد.")
    data = await state.get_data()
    await state.clear()
    tid = await create_treaty("trade", message.from_user.id, data["counterpart"],
                              data["neg_id"], None, pct)
    await _request_confirmations(message.bot, [(tid, "trade")], message.from_user.id,
                                 data["counterpart"], None)
    await send_home(message, "✅ پیمان «رفیقای تجاری» پیشنهاد شد — در انتظار تأیید طرف مقابل.")


async def _make_treaty(call: CallbackQuery, neg_id: int, kind: str,
                       counterpart: int, witness: int | None):
    tid = await create_treaty(kind, call.from_user.id, counterpart, neg_id, witness)
    await _request_confirmations(call.bot, [(tid, kind)], call.from_user.id, counterpart, witness)
    await call.answer("📨 پیمان پیشنهاد شد — در انتظار تأیید طرف‌ها")
    await my_treaties(call)


async def _request_confirmations(bot, made: list, party_a: int, party_b: int, witness):
    """ارسال پیام تأیید به طرف مقابل و شاهد."""
    a_name = await _cname(party_a)
    b_name = await _cname(party_b)
    for tid, kind in made:
        title, desc = TREATY_KINDS[kind]
        text = (f"📜 <b>{title}</b>\nپیشنهاد شده توسط {a_name} برای قرارداد با {b_name}.\n\n"
                f"{desc}\n")
        if kind == "trade":
            t = await db.fetchone("SELECT trade_percent FROM treaties WHERE id=?", (tid,))
            text += f"\n💼 درصد تجاری: <b>{round(t['trade_percent'])}٪</b>"
        for uid in [party_b] + ([witness] if witness else []):
            try:
                await dm(bot, 
                    uid, text,
                    reply_markup=kb([
                        [("✅ تأیید قرارداد", f"g|trtcon|{tid}")],
                        [("❌ رد قرارداد", f"g|trtrej|{tid}")],
                    ]))
            except Exception:
                pass


@router.callback_query(F.data.startswith("g|trtcon|"))
async def treaty_confirm(call: CallbackQuery):
    tid = int(call.data.split("|")[2])
    t = await db.fetchone("SELECT * FROM treaties WHERE id=?", (tid,))
    if not t or t["status"] != "pending":
        return await call.answer("پیمان یافت نشد یا نهایی شده", show_alert=True)
    msg = await confirm_treaty(tid, call.from_user.id)
    if "فعال شد" in msg:
        # اعلان کانال با عکس + پایان جنگ در پیمان صلح
        if t["kind"] == "peace":
            await db.execute(
                "UPDATE wars SET status='ended', ended_at=? WHERE status='active' AND "
                "((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?))",
                (iso(), t["party_a"], t["party_b"], t["party_b"], t["party_a"]))
        await announce_treaty(call.bot, t)
        for uid in [t["party_a"], t["party_b"]] + ([t["witness_id"]] if t["witness_id"] else []):
            try:
                extra = ""
                if t["kind"] == "trust" and uid == t["witness_id"]:
                    extra = "\n\n👁 شما شاهد این پیمان هستید؛ در صورت لغو گواهی، پیمان شکسته و در سازمان ملل اعلام می‌شود."
                    await dm(call.bot, 
                        uid, f"✅ پیمان «اعتماد» فعال شد!{extra}",
                        reply_markup=kb([("🚫 لغو گواهی (شاهد)", f"g|wrevoke|{tid}")]))
                    continue
                await dm(call.bot, uid, f"✅ پیمان «{TREATY_KINDS[t['kind']][0]}» فعال شد!")
            except Exception:
                pass
    await call.answer(msg, show_alert=True)


@router.callback_query(F.data.startswith("g|trtrej|"))
async def treaty_reject(call: CallbackQuery):
    tid = int(call.data.split("|")[2])
    t = await db.fetchone("SELECT * FROM treaties WHERE id=?", (tid,))
    if not t:
        return await call.answer("یافت نشد", show_alert=True)
    msg = await reject_treaty(tid, call.from_user.id)
    other = t["party_a"] if call.from_user.id == t["party_b"] else t["party_b"]
    try:
        await dm(call.bot, other, f"❌ پیمان «{TREATY_KINDS[t['kind']][0]}» رد شد.")
    except Exception:
        pass
    await call.answer(msg, show_alert=True)


@router.callback_query(F.data.startswith("g|wrevoke|"))
async def witness_revoke(call: CallbackQuery):
    tid = int(call.data.split("|")[2])
    t = await db.fetchone("SELECT * FROM treaties WHERE id=? AND status='active'", (tid,))
    if not t or t["witness_id"] != call.from_user.id:
        return await call.answer("شاهد این پیمان نیستید", show_alert=True)
    a_name = await _cname(t["party_a"])
    b_name = await _cname(t["party_b"])
    await announce_img(call.bot,
                       f"🕊 سازمان ملل: شاهدِ پیمان اعتماد بین {a_name} و {b_name} گواهی خود را لغو کرد — پیمان باطل شد.",
                       "treaty_trust")
    await break_treaty(t, call.bot, call.from_user.id)
    await call.answer("گواهی لغو شد")


# ═══════════════ تجارت مستقیم ═══════════════


async def _has_amount(uid: int, rtype: str, rid: int, qty: int) -> bool:
    if rtype == "money":
        u = await db.fetchone("SELECT money FROM users WHERE id=?", (uid,))
        return (u or {}).get("money", 0) >= qty
    if rtype == "coins":
        u = await db.fetchone("SELECT royal_coins FROM users WHERE id=?", (uid,))
        return (u or {}).get("royal_coins", 0) >= qty
    if rtype in ("energy", "water", "gas", "oil_stock"):
        col = {"energy": "energy", "water": "water", "gas": "gas", "oil_stock": "oil_stock"}[rtype]
        s = await db.fetchone(f"SELECT {col} FROM states WHERE user_id=?", (uid,))
        return (s or {}).get(col, 0) >= qty
    table = "equipment" if rtype == "equip" else "soldier_types"
    row = await db.fetchone(
        f"SELECT quantity FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
        (uid, "equipment" if rtype == "equip" else "soldier", rid))
    return (row or {}).get("quantity", 0) >= qty if row else False


async def _transfer(from_id: int, to_id: int, rtype: str, rid: int, qty: int) -> None:
    if rtype == "money":
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (qty, from_id))
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (qty, to_id))
    elif rtype == "coins":
        await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?", (qty, from_id))
        await db.execute("UPDATE users SET royal_coins=royal_coins+? WHERE id=?", (qty, to_id))
    elif rtype in ("energy", "water", "gas", "oil_stock"):
        col = rtype
        await db.execute(f"UPDATE states SET {col}={col}-? WHERE user_id=?", (qty, from_id))
        await db.execute(f"UPDATE states SET {col}={col}+? WHERE user_id=?", (qty, to_id))
    else:
        itype = "equipment" if rtype == "equip" else "soldier"
        await db.execute(
            "UPDATE player_assets SET quantity=quantity-? WHERE user_id=? AND item_type=? AND item_id=?",
            (qty, from_id, itype, rid))
        await db.execute(
            "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
            (to_id, itype, rid, qty, qty))


async def _value_of(rtype: str, rid: int, qty: int) -> int:
    """ارزش پولی تقریبی برای آمار تجارت."""
    if rtype == "money":
        return qty
    if rtype == "coins":
        rate = int(await get_setting("coins_to_money_rate", "5000000"))
        return qty * rate
    if rtype in ("energy", "water", "gas"):
        key = {"energy": "rescue_energy_price", "water": "rescue_water_price", "gas": "rescue_gas_price"}[rtype]
        return qty * int(await get_setting(key, "2000"))
    if rtype == "oil_stock":
        return qty * int(await get_setting("oil_price_per_barrel", "8000"))
    if rtype == "equip":
        e = await db.fetchone("SELECT price_money, price_coins FROM equipment WHERE id=?", (rid,))
        if not e:
            return 0
        rate = int(await get_setting("coins_to_money_rate", "5000000"))
        return qty * (e["price_money"] + (e["price_coins"] or 0) * rate)
    s = await db.fetchone("SELECT cost_per_unit FROM soldier_types WHERE id=?", (rid,))
    return qty * (s["cost_per_unit"] if s else 0)


def _res_name(rtype: str) -> str:
    return {"oil_stock": "🛢 نفت (بشکه)"}.get(rtype, TRADE_RESOURCES.get(rtype, rtype))


async def _describe(rtype: str, rid: int, qty: int) -> str:
    if rtype in ("equip", "soldier"):
        table = "equipment" if rtype == "equip" else "soldier_types"
        row = await db.fetchone(f"SELECT name, emoji FROM {table} WHERE id=?", (rid,))
        return f"{row['emoji']} {row['name']} ×{fmt(qty)}" if row else f"#{rid} ×{fmt(qty)}"
    return f"{_res_name(rtype)}: {fmt(qty)}"


@router.callback_query(F.data == "g|dtrd")
async def direct_trade_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    rows = await _countries_kb(call.from_user.id, "g|dtrp|")
    if not rows:
        return await call.answer("کشور دیگری موجود نیست", show_alert=True)
    rows.append(back_row("g|trd"))
    await call.answer()
    await call.message.edit_text(
        "🔁 <b>تجارت مستقیم</b>\n\nکشور طرف معامله را انتخاب کنید. مثال:\n"
        "کشور X مقدار ۵ سکه شاهی در ازای ۱۰۰ کیلووات برق معاوضه می‌کند.\n"
        "⚠️ این معاملات در کانال اعلام نمی‌شود.",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|dtrp|"))
async def dt_pick_give(call: CallbackQuery, state: FSMContext):
    partner = int(call.data.split("|")[2])
    await state.update_data(partner=partner, give=None, want=None)
    await call.answer()
    await call.message.edit_text(
        f"🔁 معامله با {await _cname(partner)}\n\n<b>۱) چه چیزی می‌دهید؟</b>",
        reply_markup=kb(_res_rows("g|dtg|")))


def _res_rows(prefix: str) -> list:
    return [
        [(TRADE_RESOURCES["money"], f"{prefix}money"), (TRADE_RESOURCES["coins"], f"{prefix}coins")],
        [(TRADE_RESOURCES["energy"], f"{prefix}energy"), (TRADE_RESOURCES["water"], f"{prefix}water")],
        [(TRADE_RESOURCES["gas"], f"{prefix}gas"), (TRADE_RESOURCES["oil"], f"{prefix}oil_stock")],
        [(TRADE_RESOURCES["equip"], f"{prefix}equip"), (TRADE_RESOURCES["soldier"], f"{prefix}soldier")],
    ]


@router.callback_query(F.data.startswith("g|dtg|"))
async def dt_give_type(call: CallbackQuery, state: FSMContext):
    rtype = call.data.split("|")[2]
    if rtype in ("equip", "soldier"):
        itype = "equipment" if rtype == "equip" else "soldier"
        items = await db.fetchall(
            f"SELECT a.item_id, a.quantity, t.name, t.emoji FROM player_assets a "
            f"JOIN {'equipment' if rtype == 'equip' else 'soldier_types'} t ON t.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type=? AND a.quantity>0",
            (call.from_user.id, itype))
        if not items:
            return await call.answer("موجودی ندارید", show_alert=True)
        rows = [[(f"{i['emoji']} {i['name']} ({fmt(i['quantity'])})", f"g|dtgi|{rtype}|{i['item_id']}")
                 for i in items]]
        await call.answer()
        return await call.message.edit_text("۱) چه چیزی می‌دهید؟ (تجهیزات/سرباز):", reply_markup=kb(rows))
    await state.update_data(give_type=rtype, give_id=0)
    await state.set_state(TradeFSM.dt_qty)
    await call.answer()
    await call.message.edit_text(f"۱) مقدار «{_res_name(rtype)}» که می‌دهید را بنویسید:\n برای انصراف /cancel")


@router.callback_query(F.data.startswith("g|dtgi|"))
async def dt_give_item(call: CallbackQuery, state: FSMContext):
    _, _, rtype, rid = call.data.split("|")
    await state.update_data(give_type=rtype, give_id=int(rid))
    await state.set_state(TradeFSM.dt_qty)
    await call.answer()
    await call.message.edit_text("۱) تعداد را بنویسید:\n برای انصراف /cancel")


@router.message(TradeFSM.dt_qty)
async def dt_qty_input(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد بفرستید.")
    if qty <= 0:
        return await send_home(message, "❌ عدد باید مثبت باشد.")
    data = await state.get_data()
    side = data.get("side", "give")
    rtype, rid = data.get(f"{side}_type"), data.get(f"{side}_id", 0) or 0
    if side == "give":
        if not await _has_amount(message.from_user.id, rtype, rid, qty):
            return await send_home(message, "❌ موجودی کافی ندارید.")
        await state.update_data(give_qty=qty, side="want")
        await send_home(message, 
            "۲) <b>چه چیزی در ازای آن می‌خواهید؟</b>",
            reply_markup=kb(_res_rows("g|dtw|")))
    else:
        if not await _has_amount(data.get("partner"), rtype, rid, qty):
            return await send_home(message, "❌ طرف مقابل موجودی لازم را ندارد.")
        await state.update_data(want_qty=qty)
        await state.set_state(None)
        d = await state.get_data()
        await send_home(message, 
            "🔁 <b>خلاصه معامله</b>\n\n"
            f"شما می‌دهید: {await _describe(d['give_type'], d.get('give_id', 0), d['give_qty'])}\n"
            f"شما می‌گیرید: {await _describe(d['want_type'], d.get('want_id', 0), d['want_qty'])}\n"
            f"طرف مقابل: {await _cname(d['partner'])}\n\nتأیید می‌کنید؟",
            reply_markup=kb([
                [("✅ ارسال پیشنهاد", "g|dtok")],
                [("❌ انصراف", "g|trd")],
            ]))


@router.callback_query(F.data.startswith("g|dtw|"))
async def dt_want_type(call: CallbackQuery, state: FSMContext):
    rtype = call.data.split("|")[2]
    data = await state.get_data()
    partner = data.get("partner") or 0
    if rtype in ("equip", "soldier"):
        itype = "equipment" if rtype == "equip" else "soldier"
        items = await db.fetchall(
            f"SELECT a.item_id, a.quantity, t.name, t.emoji FROM player_assets a "
            f"JOIN {'equipment' if rtype == 'equip' else 'soldier_types'} t ON t.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type=? AND a.quantity>0",
            (partner, itype))
        if not items:
            return await call.answer("طرف مقابل موجودی ندارد", show_alert=True)
        rows = [[(f"{i['emoji']} {i['name']} ({fmt(i['quantity'])})", f"g|dtwi|{rtype}|{i['item_id']}")
                 for i in items]]
        await call.answer()
        return await call.message.edit_text("۲) چه می‌خواهید؟ (تجهیزات/سرباز طرف مقابل):", reply_markup=kb(rows))
    await state.update_data(want_type=rtype, want_id=0)
    await state.set_state(TradeFSM.dt_qty)
    await call.answer()
    await call.message.edit_text(f"۲) مقدار «{_res_name(rtype)}» که می‌خواهید را بنویسید:\n برای انصراف /cancel")


@router.callback_query(F.data.startswith("g|dtwi|"))
async def dt_want_item(call: CallbackQuery, state: FSMContext):
    _, _, rtype, rid = call.data.split("|")
    await state.update_data(want_type=rtype, want_id=int(rid))
    await state.set_state(TradeFSM.dt_qty)
    await call.answer()
    await call.message.edit_text("۲) تعداد را بنویسید:\n برای انصراف /cancel")


@router.callback_query(F.data == "g|dtok")
async def dt_send(call: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    partner = d.get("partner")
    if not partner or not d.get("give_qty") or not d.get("want_qty"):
        return await call.answer("اطلاعات ناقص است — از ابتدا شروع کنید", show_alert=True)
    value = (await _value_of(d["give_type"], d.get("give_id", 0), d["give_qty"])
             + await _value_of(d["want_type"], d.get("want_id", 0), d["want_qty"]))
    tid = await db.execute(
        "INSERT INTO direct_trades(from_id, to_id, give_type, give_id, give_qty, "
        "want_type, want_id, want_qty, value_estimate) VALUES(?,?,?,?,?,?,?,?,?)",
        (call.from_user.id, partner, d["give_type"], d.get("give_id", 0), d["give_qty"],
         d["want_type"], d.get("want_id", 0), d["want_qty"], value))
    try:
        await dm(call.bot, 
            partner,
            f"🔁 <b>پیشنهاد تجارت مستقیم</b> از {await _cname(call.from_user.id)}:\n\n"
            f"آنها می‌دهند: {await _describe(d['give_type'], d.get('give_id', 0), d['give_qty'])}\n"
            f"آنها می‌خواهند: {await _describe(d['want_type'], d.get('want_id', 0), d['want_qty'])}",
            reply_markup=kb([
                [("✅ قبول معامله", f"g|dtacc|{tid}")],
                [("❌ رد", f"g|dtdeny|{tid}")],
            ]))
    except Exception:
        pass
    await call.answer("📨 پیشنهاد ارسال شد")
    await trade_menu(call)


@router.callback_query(F.data.startswith("g|dtacc|"))
async def dt_accept(call: CallbackQuery):
    tid = int(call.data.split("|")[2])
    t = await db.fetchone("SELECT * FROM direct_trades WHERE id=? AND status='pending'", (tid,))
    if not t or t["to_id"] != call.from_user.id:
        return await call.answer("پیشنهاد یافت نشد", show_alert=True)
    # اعتبارسنجی دوطرفه
    if not await _has_amount(t["from_id"], t["give_type"], t["give_id"], t["give_qty"]):
        await db.execute("UPDATE direct_trades SET status='failed' WHERE id=?", (tid,))
        return await call.answer("❌ طرف مقابل دیگر موجودی لازم را ندارد", show_alert=True)
    if not await _has_amount(t["to_id"], t["want_type"], t["want_id"], t["want_qty"]):
        return await call.answer("❌ شما موجودی لازم را ندارید", show_alert=True)
    await _transfer(t["from_id"], t["to_id"], t["give_type"], t["give_id"], t["give_qty"])
    await _transfer(t["to_id"], t["from_id"], t["want_type"], t["want_id"], t["want_qty"])
    await db.execute("UPDATE direct_trades SET status='accepted' WHERE id=?", (tid,))
    a, b = await _cname(t["from_id"]), await _cname(t["to_id"])
    await log_event("trade", f"تجارت مستقیم {a} ↔ {b} (ارزش ~{fmt(t['value_estimate'])})")
    for uid, txt in ((t["from_id"], f"✅ معامله با {b} انجام شد!"),
                     (t["to_id"], f"✅ معامله با {a} انجام شد!")):
        try:
            await dm(call.bot, uid, txt)
        except Exception:
            pass
    # پیمان تجاری فعال بین این دو؟ → پیام سهم فروش برای دریافت‌کننده پول
    tr = await find_treaty(t["from_id"], t["to_id"], "trade")
    if tr:
        money_receiver = t["from_id"] if t["want_type"] == "money" else (
            t["to_id"] if t["give_type"] == "money" else None)
        amount = t["want_qty"] if t["want_type"] == "money" else (
            t["give_qty"] if t["give_type"] == "money" else 0)
        if money_receiver and amount:
            partner_id = t["to_id"] if money_receiver == t["from_id"] else t["from_id"]
            share = int(amount * (tr["trade_percent"] or 0) / 100)
            try:
                await dm(call.bot, 
                    money_receiver,
                    f"💼 شما «رفیق تجاری» {await _cname(partner_id)} هستید.\n"
                    f"آیا این مقدار از پولت ({fmt(share)}) را برای این کشور می‌دهی؟",
                    reply_markup=kb([
                        [("✅ بله، پرداخت سهم", f"g|shy|{tr['id']}|{share}|{partner_id}")],
                        [("❌ نه", f"g|shn|{tr['id']}|{partner_id}")],
                    ]))
            except Exception:
                pass
    await call.answer("✅ معامله انجام شد")
    await trade_menu(call)


@router.callback_query(F.data.startswith("g|dtdeny|"))
async def dt_deny(call: CallbackQuery):
    tid = int(call.data.split("|")[2])
    t = await db.fetchone("SELECT * FROM direct_trades WHERE id=? AND status='pending'", (tid,))
    if not t or t["to_id"] != call.from_user.id:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("UPDATE direct_trades SET status='declined' WHERE id=?", (tid,))
    try:
        await dm(call.bot, t["from_id"], "❌ پیشنهاد تجارت مستقیم شما رد شد.")
    except Exception:
        pass
    await call.answer("رد شد")


# ─── سهم/خیانت رفقای تجاری ───


@router.callback_query(F.data.startswith("g|shy|"))
async def share_yes(call: CallbackQuery):
    _, _, trid, share, partner = call.data.split("|")
    tr = await db.fetchone("SELECT * FROM treaties WHERE id=? AND status='active'", (int(trid),))
    if not tr:
        return await call.answer("قرارداد یافت نشد", show_alert=True)
    share = int(share)
    payer = call.from_user.id
    u = await db.fetchone("SELECT money FROM users WHERE id=?", (payer,))
    if (u or {}).get("money", 0) < share:
        return await call.answer("پول کافی ندارید!", show_alert=True)
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (share, payer))
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (share, int(partner)))
    await log_event("treaty", f"سهم تجاری {fmt(share)} پرداخت شد")
    await call.answer("✅ سهم پرداخت شد")
    try:
        await dm(call.bot, int(partner),
                                    f"💼 رفیق تجاری شما سهم قرارداد ({fmt(share)}) را پرداخت کرد.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("g|shn|"))
async def share_no(call: CallbackQuery):
    _, _, trid, partner = call.data.split("|")
    tr = await db.fetchone("SELECT * FROM treaties WHERE id=? AND status='active'", (int(trid),))
    if not tr:
        return await call.answer("قرارداد یافت نشد", show_alert=True)
    await call.answer()
    try:
        await dm(call.bot, 
            int(partner),
            f"💥 رفیق تجاری شما ({await _cname(call.from_user.id)}) خیانت کرد و سهم را پرداخت نکرد!\n"
            "می‌خواهی قرارداد را بهم بزنی؟ (دیپلماسی هر دو کشور کم می‌شود و خیانت در کانال اعلام می‌شود)",
            reply_markup=kb([
                [("💥 بله، شکستن قرارداد", f"g|brk|{tr['id']}")],
                [("⏭ بخشش", f"g|frg|{tr['id']}")],
            ]))
    except Exception:
        pass


@router.callback_query(F.data.startswith("g|brk|"))
async def treaty_break(call: CallbackQuery):
    trid = int(call.data.split("|")[2])
    tr = await db.fetchone("SELECT * FROM treaties WHERE id=? AND status='active'", (trid,))
    if not tr:
        return await call.answer("یافت نشد", show_alert=True)
    if call.from_user.id not in (tr["party_a"], tr["party_b"]):
        return await call.answer("طرف این قرارداد نیستید", show_alert=True)
    await break_treaty(tr, call.bot, call.from_user.id)
    await call.answer("💥 قرارداد شکسته شد")
    await my_treaties(call)


@router.callback_query(F.data.startswith("g|frg|"))
async def treaty_forgive(call: CallbackQuery):
    await call.answer("⏭ گذشت — قرارداد پابرجا ماند")


# ═══════════════ فروش انرژی به سازمان نجات ═══════════════


RESCUE_RES = {
    "energy": ("⚡️ برق", "rescue_energy_price", "energy"),
    "water": ("💧 آب", "rescue_water_price", "water"),
    "gas": ("🔥 گاز", "rescue_gas_price", "gas"),
    "oil_stock": ("🛢 نفت", "rescue_oil_price", "oil_stock"),
}


@router.callback_query(F.data == "g|rsale")
async def rescue_sale_menu(call: CallbackQuery):
    state = await get_state(call.from_user.id)
    rows = []
    lines = ["🏥 <b>فروش منابع به سازمان نجات</b>\n",
             "با فروش برق/آب/گاز/نفت به «سازمان مراقبت از جنگ‌زدگان» پول بدست می‌آورید؛ "
             "این کار نوعی حمایت انسان‌دوستانه است و در کانال اعلام می‌شود "
             "(بدون ذکر درآمد یا مقدار منبع).\n",
             "موجودی شما:"]
    for key, (title, _p, col) in RESCUE_RES.items():
        qty = state.get(col) or 0
        lines.append(f"• {title}: {fmt(qty)}")
        rows.append([(f"🏥 فروش {title}", f"g|rsr|{key}")])
    rows.append(back_row("g|trd"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|rsr|"))
async def rescue_sale_pick(call: CallbackQuery, state: FSMContext):
    key = call.data.split("|")[2]
    title, price_key, col = RESCUE_RES[key]
    price = int(await get_setting(price_key, "2000"))
    await state.set_state(TradeFSM.rs_qty)
    await state.update_data(rs_key=key)
    await call.answer()
    await call.message.edit_text(
        f"🏥 فروش {title} به سازمان نجات\nقیمت هر واحد: <b>{fmt(price)}</b>\n\n"
        "مقدار را بنویسید:\n برای انصراف /cancel")


@router.message(TradeFSM.rs_qty)
async def rescue_sale_input(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد بفرستید.")
    if qty <= 0:
        return await send_home(message, "❌ عدد باید مثبت باشد.")
    data = await state.get_data()
    key = data.get("rs_key")
    title, price_key, col = RESCUE_RES[key]
    st = await get_state(message.from_user.id)
    if (st.get(col) or 0) < qty:
        return await send_home(message, f"❌ موجودی کافی ندارید ({fmt(st.get(col) or 0)}).")
    await state.clear()
    price = int(await get_setting(price_key, "2000"))
    total = qty * price
    await db.execute(f"UPDATE states SET {col}={col}-? WHERE user_id=?", (qty, message.from_user.id))
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (total, message.from_user.id))
    await db.execute("UPDATE states SET satisfaction=MIN(100, satisfaction+0.5) WHERE user_id=?",
                     (message.from_user.id,))
    c = await get_country(message.from_user.id)
    await log_event("rescue", f"{c['name']} منابع به سازمان نجات فروخت (حمایت انسان‌دوستانه)")
    # اعلام کانال با عکس — بدون ذکر درآمد/مقدار
    await announce_img(message.bot,
                       f"🏥 کشور {c['flag']} {c['name']} با اهدای {title.split()[0]} "
                       "از جنگ‌زدگان جهان حمایت کرد. 👏",
                       "rescue")
    await send_home(message, 
        f"✅ {fmt(qty)} {title} به سازمان نجات فروخته شد.\n💰 درآمد: {fmt(total)} (+رضایت ۰.۵)")
    await rescue_sale_menu(_fake_call(message))


class _fake_call:
    def __init__(self, message: Message):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot

    async def answer(self, *_a, **_k):
        pass


# ═══════════════ تنگه‌ها ═══════════════


@router.callback_query(F.data == "g|strait")
async def straits_menu(call: CallbackQuery):
    text, buttons = await straits_menu_text(call.from_user.id)
    buttons.append(back_row("g|trd"))
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("g|stc|"))
async def strait_capture(call: CallbackQuery):
    sid = int(call.data.split("|")[2])
    msg = await capture_strait(call.bot, call.from_user.id, sid)
    await call.answer(msg[:180], show_alert=True)
    await straits_menu(call)


@router.callback_query(F.data == "g|stblk_menu")
async def strait_blockade_menu(call: CallbackQuery):
    """مدیریت انسداد تنگه‌ها توسط مالک."""
    from core.straits import my_straits, get_owner_blockades
    straits = await my_straits(call.from_user.id)
    if not straits:
        return await call.answer("❌ شما مالکیتی بر هیچ تنگه‌ای ندارید!", show_alert=True)
    
    active_blockades = await get_owner_blockades(call.from_user.id)
    lines = [
        "🚫 <b>مدیریت انسداد و تحریم آبراه‌های استراتژیک</b>\n",
        "با بستن هر تنگه روی یک کشور، <b>۱۰٪ از درآمد نوبتی آن کشور کسر می‌شود</b>.",
        f"تنگه‌های تحت فرمانروایی شما: <b>{len(straits)}</b>\n",
    ]
    if active_blockades:
        lines.append("⚠️ <b>کشورهای در حال حاضر مسدودشده توسط شما:</b>")
        for b in active_blockades:
            lines.append(f"  • {b['strait_emoji']} {b['strait_name']} ➔ {b['target_flag']} {b['target_name']}")
    else:
        lines.append("— در حال حاضر هیچ تنگه‌ای مسدود نشده است —")
    
    lines.append("\nتنگه مورد نظر برای اعمال یا لغو انسداد را انتخاب کنید:")
    rows = [[(f"⚓ {s['emoji']} {s['name']}", f"g|stblk_strait|{s['id']}")] for s in straits]
    rows.append(back_row("g|strait"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|stblk_strait|"))
async def strait_blockade_strait_view(call: CallbackQuery):
    strait_id = int(call.data.split("|")[2])
    strait = await db.fetchone("SELECT * FROM straits WHERE id=? AND owner_id=?", (strait_id, call.from_user.id))
    if not strait:
        return await call.answer("شما مالک این تنگه نیستید", show_alert=True)
    
    # دریافت لیست کشورهایی که بازیکن دارند
    countries = await db.fetchall(
        "SELECT c.*, u.id AS uid FROM countries c JOIN users u ON u.id=c.owner_id "
        "WHERE c.owner_id IS NOT NULL AND c.owner_id!=? ORDER BY c.name", (call.from_user.id,))
    
    # دریافت بلاک‌های فعلی این تنگه
    blocks = await db.fetchall(
        "SELECT target_user_id FROM strait_blockades WHERE strait_id=?", (strait_id,))
    blocked_uids = {b["target_user_id"] for b in blocks}

    lines = [
        f"⚓ <b>تنظیم انسداد تنگه {strait['emoji']} {strait['name']}</b>\n",
        "روی هر کشور کلیک کنید تا تنگه به روی آن <b>بسته یا باز</b> شود.",
        "کشورهایی که با 🔴 مشخص شده‌اند هم‌اکنون مسدود بوده و ۱۰٪ جریمه درآمد دارند.\n",
    ]
    rows = []
    for c in countries:
        is_blk = c["uid"] in blocked_uids
        badge = "🔴 مسدود (کلیک برای بازگشایی)" if is_blk else "🟢 آزاد (کلیک برای انسداد)"
        rows.append([(f"{c['flag']} {c['name']} — {badge}", f"g|stblk_tog|{strait_id}|{c['uid']}")])
    
    rows.append(back_row("g|stblk_menu"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|stblk_tog|"))
async def strait_blockade_toggle(call: CallbackQuery):
    _, _, sid, target_id = call.data.split("|")
    from core.straits import toggle_strait_blockade
    is_now_blocked, msg = await toggle_strait_blockade(call.from_user.id, int(sid), int(target_id))
    await call.answer(msg, show_alert=True)
    call.data = f"g|stblk_strait|{sid}"
    await strait_blockade_strait_view(call)

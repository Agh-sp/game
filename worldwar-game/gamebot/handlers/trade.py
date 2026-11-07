"""تجارت بین‌المللی (بازسازی کامل) — مذاکره مخفیانه، پیمان‌ها، تجارت مستقیم،
فروش انرژی به سازمان نجات و تنگه‌های راهبردی."""
import html
import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

log = logging.getLogger(__name__)

from core.db import db, get_setting
from core.economy import get_country, get_state
from core.events import log_event
from core.images import announce_img
from core.treaties import (TREATY_KINDS, break_treaty, confirm_treaty,
                           create_treaty, find_treaty, reject_treaty,
                           announce_treaty, active_treaties, diplomacy_add)
from core.straits import capture_strait, straits_menu_text
from core.utils import fmt, fmt_money, iso, clamp
from gamebot.common import back_row, dm, kb, safe_edit, send_home

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
    neg_chat = State()


async def _cname(user_id: int) -> str:
    """نام کشور برای نمایش در متن (خروجی HTML-safe)."""
    c = await get_country(user_id)
    return f"{c['flag']} {html.escape(c['name'])}" if c else "؟"


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
    """دریافت لیست کشورهای دارای بازیکن و همچنین هیئت‌های دیپلماتیک سایر ملل جهان."""
    # ۱. بازیکنان واقعی دارای کشور
    players = await db.fetchall(
        "SELECT u.id AS player_id, c.name, c.flag, c.id AS cid "
        "FROM users u JOIN countries c ON c.id=u.country_id "
        "WHERE u.id!=? AND u.banned=0 AND u.country_id IS NOT NULL "
        "ORDER BY c.name", (user_id,))
    rows = []
    used_cids = set()
    for r in players:
        # 🔒 حریم خصوصی: هیچ یوزرنیم/آیدی تلگرامی نمایش داده نمی‌شود —
        # به‌جای آن «نام فرمانده» محرمانه و ثابت نشان داده می‌شود.
        try:
            from core.privacy import commander_name
            nick = await commander_name(r["player_id"])
        except Exception:
            nick = ""
        cmd = f" — فرمانده: {nick}" if nick else ""
        rows.append([(f"👤 {r['flag']} {r['name']}{cmd}", f"{cb_prefix}{r['player_id']}")])
        used_cids.add(r["cid"])

    # ۲. هیئت‌های دیپلماتیک سایر کشورهای جهان (NPC) جهت تعامل دائمی
    my_u = await db.fetchone("SELECT country_id FROM users WHERE id=?", (user_id,))
    my_cid = my_u["country_id"] if my_u else None
    if my_cid:
        used_cids.add(my_cid)

    npcs = await db.fetchall(
        "SELECT id, name, flag, is_special FROM countries "
        "WHERE is_active=1 AND id NOT IN ({}) ORDER BY is_special DESC, name ASC LIMIT 20".format(
            ",".join(str(c) for c in used_cids) if used_cids else "0"
        )
    )
    for c in npcs:
        rows.append([(f"🏛 {c['flag']} {c['name']} (هیئت دیپلماتیک)", f"{cb_prefix}{-c['id']}")])

    return rows


@router.callback_query(F.data == "g|neg")
async def negotiation_menu(call: CallbackQuery):
    mine = await db.fetchall(
        "SELECT n.*, m.role AS my_role FROM negotiations n JOIN negotiation_members m ON m.neg_id=n.id "
        "WHERE m.user_id=? AND n.status IN ('pending','open') ORDER BY n.id DESC",
        (call.from_user.id,))
    lines = ["🕊 <b>مرکز مذاکرات بین‌المللی و دیپلماسی محرمانه</b>\n",
             "با کشورهای دیگر گفتگو و مذاکره کنید. آغاز مذاکره به عنوان رویداد دیپلماتیک در کانال اعلام می‌شود اما متن گفتگوها کاملاً محرمانه می‌ماند.",
             "در اتاق مذاکره می‌توانید پیام بفرستید، کشور سومی را به عنوان شاهد دعوت کنید و در پایان با زدن «🤝 به توافق رسیدیم» ۵ پیمان رسمی منعقد نمایید.\n"]
    rows = []
    if mine:
        lines.append("📡 <b>مذاکرات فعال و در جریان شما:</b>")
        for n in mine:
            members = await db.fetchall(
                "SELECT user_id, role FROM negotiation_members WHERE neg_id=?", (n["id"],))
            names = []
            for m in members:
                cname = await _cname(m["user_id"])
                names.append(cname)
            joined_names = " + ".join(names) if names else f"مذاکره #{n['id']}"
            if n["status"] == "pending":
                if n["initiator_id"] == call.from_user.id:
                    lines.append(f"• #{n['id']} — {joined_names} — ⏳ <i>در انتظار پاسخ طرف مقابل</i>")
                    rows.append([
                        (f"💬 ورود به اتاق #{n['id']}", f"g|negroom|{n['id']}"),
                        ("⚡ پذیرش فوری", f"g|nega|{n['id']}"),
                        ("❌ لغو", f"g|negd|{n['id']}")
                    ])
                else:
                    lines.append(f"• #{n['id']} — {joined_names} — 📨 <b>درخواست دریافتی</b>")
                    rows.append([
                        ("✅ تأیید مذاکره", f"g|nega|{n['id']}"),
                        (f"💬 بررسی اتاق", f"g|negroom|{n['id']}"),
                        ("❌ رد", f"g|negd|{n['id']}")
                    ])
            else:
                lines.append(f"• #{n['id']} — {joined_names} — 🟢 <b>فعال و باز</b>")
                rows.append([
                    (f"💬 ورود به اتاق مذاکره #{n['id']}", f"g|negroom|{n['id']}"),
                    ("🤝 بستن پیمان", f"g|negok|{n['id']}"),
                    ("❌ پایان", f"g|negno|{n['id']}")
                ])
    else:
        lines.append("— شما در حال حاضر مذاکره فعالی ندارید —")

    rows.append([("➕ آغاز مذاکره جدید با کشور دیگر", "g|negnew")])
    rows.append([("📜 مشاهده پیمان‌های فعال من", "g|mytrt")])
    rows.append(back_row("g|trd"))
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit(call, "\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data == "g|negnew")
async def negotiation_new(call: CallbackQuery):
    rows = await _countries_kb(call.from_user.id, "g|negr|")
    if not rows:
        return await call.answer("کشور دیگری برای مذاکره یافت نشد!", show_alert=True)
    rows.append(back_row("g|neg"))
    try:
        await call.answer()
    except Exception:
        pass
    text = (
        "🕊 <b>آغاز مذاکره جدید</b>\n\n"
        "کشور مورد نظر خود را جهت افتتاح کانال دیپلماتیک محرمانه انتخاب فرمایید:\n"
        "<i>(می‌توانید با رهبران بازیکنان یا هیئت‌های دیپلماتیک رسمی ملل جهان وارد گفتگو شوید)</i>"
    )
    await safe_edit(call, text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|negr|"))
async def negotiation_request(call: CallbackQuery, state: FSMContext):
    target = int(call.data.split("|")[2])
    if target == call.from_user.id:
        return await call.answer("نمی‌توانید با کشور خودتان مذاکره کنید!", show_alert=True)

    sender_name = await _cname(call.from_user.id)
    target_name = await _cname(target)

    # اگر هدف یک هیئت دیپلماتیک (NPC) باشد، مذاکره بلافاصله باز و تایید می‌شود
    is_npc = target < 0
    init_status = 'open' if is_npc else 'pending'

    neg_id = await db.execute(
        "INSERT INTO negotiations(initiator_id, status) VALUES(?, ?)",
        (call.from_user.id, init_status)
    )
    await db.execute(
        "INSERT INTO negotiation_members(neg_id, user_id, role) VALUES(?,?,'host')",
        (neg_id, call.from_user.id)
    )
    await db.execute(
        "INSERT OR IGNORE INTO negotiation_members(neg_id, user_id, role) VALUES(?,?,?)",
        (neg_id, target, 'guest' if is_npc else 'guest_pending')
    )

    if is_npc:
        # پیام استقبال اولیه از طرف هیئت دیپلماتیک
        welcome_text = (
            f"درود بر رهبر عالی‌مقام کشور {sender_name}.\n"
            f"هیئت دیپلماتیک و فرستاده ویژه {target_name} پیام شما را دریافت نموده و کانال مذاکره رسمی گشوده شد.\n"
            "ما آماده گفتگو درباره پیمان‌های دفاع مشترک، رفیقای تجاری، پیمان‌های صلح و همکاری منطقه‌ای هستیم."
        )
        await db.execute(
            "INSERT INTO negotiation_msgs(neg_id, sender_id, text) VALUES(?,?,?)",
            (neg_id, target, welcome_text)
        )
        await _open_room(call.bot, neg_id)
        await call.answer("✅ هیئت دیپلماتیک وارد مذاکره شد")
    else:
        # ارسال پیام خصوصی به بازیکن هدف
        try:
            await dm(call.bot,
                target,
                f"🕊 کشور <b>{html.escape(sender_name)}</b> درخواست <b>مذاکره محرمانه</b> با شما دارد.\n"
                "در صورت تایید، شروع مذاکره در کانال اعلام شده و اتاق گفتگو فعال می‌گردد.",
                reply_markup=kb([
                    [("✅ تأیید و ورود به مذاکره", f"g|nega|{neg_id}")],
                    [("💬 مشاهده اتاق", f"g|negroom|{neg_id}")],
                    [("❌ رد درخواست", f"g|negd|{neg_id}")],
                ]))
        except Exception as e:
            log.warning("DM failed to negotiation target %s: %s", target, e)
        await call.answer("📨 درخواست مذاکره ارسال گردید")

    # هدایت مستقیم به اتاق مذاکره + فعال‌سازی حالت چت
    await state.set_state(TradeFSM.neg_chat)
    await state.update_data(active_neg_id=neg_id)
    await _show_negotiation_room(call, neg_id)


async def _open_room(bot, neg_id: int) -> None:
    """اعلام کانال + ارسال نوتیفیکیشن فعال‌سازی اتاق مذاکره برای اعضا."""
    members = await db.fetchall(
        "SELECT user_id FROM negotiation_members WHERE neg_id=? AND role IN ('host','guest','third')", (neg_id,))
    names = []
    for m in members:
        cname = await _cname(m["user_id"])
        names.append(cname)
    section = "negotiation" if len(members) == 2 else "negotiation3"
    await announce_img(bot, "🕊 " + " و ".join(names) + " وارد مذاکره دیپلماتیک شدند.", section)
    await log_event("negotiation", " و ".join(names) + " مذاکره را آغاز نمودند")
    for m in members:
        if m["user_id"] > 0:
            try:
                await dm(bot,
                    m["user_id"],
                    f"🕊 <b>اتاق مذاکره دیپلماتیک #{neg_id}</b>\n\n"
                    f"مذاکره بین {(' و ').join(names)} آغاز شد!\n"
                    "💬 برای ارسال پیام روی «✍️ ارسال پیام در چت مذاکره» بزنید یا مستقیماً در این چت متن خود را بفرستید.\n"
                    "• هر زمان به نتیجه رسیدید، دکمه «🤝 به توافق رسیدیم» را بزنید.",
                    reply_markup=kb([
                        [("💬 ورود به اتاق مذاکره", f"g|negroom|{neg_id}")],
                        [("✍️ ارسال پیام در چت مذاکره", f"g|negsend|{neg_id}")],
                        [("🤝 به توافق رسیدیم", f"g|negok|{neg_id}")],
                        [("❌ پایان مذاکره", f"g|negno|{neg_id}")],
                    ]))
            except Exception as e:
                log.warning("DM failed in _open_room to %s: %s", m["user_id"], e)


@router.callback_query(F.data.startswith("g|nega|"))
async def negotiation_approve(call: CallbackQuery, state: FSMContext):
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=?", (neg_id,))
    if not neg:
        return await call.answer("درخواست مذاکره یافت نشد!", show_alert=True)
    await db.execute(
        "INSERT INTO negotiation_members(neg_id, user_id, role) VALUES(?,?,'guest') "
        "ON CONFLICT(neg_id, user_id) DO UPDATE SET role='guest'",
        (neg_id, call.from_user.id))
    await db.execute("UPDATE negotiations SET status='open' WHERE id=?", (neg_id,))
    try:
        await call.answer("✅ مذاکره پذیرفته و اتاق فعال شد")
    except Exception:
        pass
    guest_name = await _cname(call.from_user.id)
    if neg["initiator_id"] != call.from_user.id and neg["initiator_id"] > 0:
        try:
            await dm(call.bot, neg["initiator_id"],
                     f"✅ کشور <b>{html.escape(guest_name)}</b> مذاکره را پذیرفت!\n"
                     f"اتاق مذاکره #{neg_id} هم‌اکنون فعال و آماده گفتگو است.",
                     reply_markup=kb([
                         [("💬 ورود به اتاق مذاکره", f"g|negroom|{neg_id}")],
                         [("✍️ ارسال پیام", f"g|negsend|{neg_id}")],
                     ]))
        except Exception as e:
            log.warning("DM approve failed to host %s: %s", neg["initiator_id"], e)
    await _open_room(call.bot, neg_id)
    await state.set_state(TradeFSM.neg_chat)
    await state.update_data(active_neg_id=neg_id)
    await _show_negotiation_room(call, neg_id)


@router.callback_query(F.data.startswith("g|negd|"))
async def negotiation_decline(call: CallbackQuery):
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=?", (neg_id,))
    if not neg:
        return await call.answer("مذاکره یافت نشد", show_alert=True)
    await db.execute("UPDATE negotiations SET status='rejected', ended_at=? WHERE id=?",
                     (iso(), neg_id))
    try:
        decliner = await _cname(call.from_user.id)
        target_uid = neg["initiator_id"] if call.from_user.id != neg["initiator_id"] else None
        if target_uid and target_uid > 0:
            await dm(call.bot, target_uid, f"❌ درخواست مذاکره توسط {html.escape(decliner)} لغو یا رد شد.")
    except Exception as e:
        log.warning("DM decline error: %s", e)
    await call.answer("درخواست لغو یا رد شد")
    await negotiation_menu(call)


@router.callback_query(F.data.startswith("g|negroom|"))
async def negotiation_room(call: CallbackQuery, state: FSMContext):
    """ورود به اتاق مذاکره؛ هر متن بعدی بازیکن مستقیم در همین اتاق ارسال می‌شود."""
    neg_id = int(call.data.split("|")[2])
    members = {m["user_id"] for m in await db.fetchall(
        "SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))}
    if call.from_user.id in members:
        # state قبلی (مثلاً خرید نیمه‌کاره) پاک می‌شود تا پیام‌های چت بلعیده نشوند
        await state.set_state(TradeFSM.neg_chat)
        await state.update_data(active_neg_id=neg_id)
    await _show_negotiation_room(call, neg_id)


async def _show_negotiation_room(call: CallbackQuery, neg_id: int):
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=?", (neg_id,))
    if not neg:
        return await call.answer("مذاکره مورد نظر یافت نشد!", show_alert=True)
    members = await db.fetchall("SELECT user_id, role FROM negotiation_members WHERE neg_id=?", (neg_id,))
    member_ids = {m["user_id"] for m in members}
    if call.from_user.id not in member_ids and call.from_user.id != neg["initiator_id"]:
        return await call.answer("شما عضو این مذاکره نیستید", show_alert=True)

    names = []
    for m in members:
        names.append(await _cname(m["user_id"]))
    parties_str = " و ".join(names) if names else "کشورها"

    msgs = await db.fetchall(
        "SELECT * FROM negotiation_msgs WHERE neg_id=? ORDER BY id DESC LIMIT 15", (neg_id,))

    status_badge = "🟢 <b>فعال و در جریان</b>" if neg["status"] == "open" else "⏳ <b>در انتظار پاسخ رسمی طرف مقابل</b>"

    lines = [
        f"💬 <b>اتاق مذاکره محرمانه #{neg_id}</b>",
        f"طرفین گفتگو: <b>{html.escape(parties_str)}</b>",
        f"وضعیت: {status_badge}\n",
        "────────────────────",
        "📜 <b>تاریخچه پیام‌های رد و بدل شده:</b>"
    ]
    if msgs:
        for m in reversed(msgs):
            sender_title = await _cname(m['sender_id'])
            safe_body = html.escape(m['text'].strip())
            lines.append(f"👤 <b>{html.escape(sender_title)}</b>:\n«{safe_body}»\n")
    else:
        lines.append("<i>— هنوز پیامی در این اتاق ارسال نشده است —</i>\n")

    lines.append("────────────────────")
    lines.append("✍️ برای ارسال پیام، روی دکمه زیر کلیک کنید یا مستقیماً در چت تایپ فرمایید:")

    rows = [
        [("✍️ ارسال پیام در چت مذاکره", f"g|negsend|{neg_id}")],
        [("🤝 به توافق رسیدیم (انعقاد معاهده)", f"g|negok|{neg_id}")],
        [("➕ عضو کردن کشور سوم (شاهد)", f"g|neginv|{neg_id}"), ("🔄 بروزرسانی چت", f"g|negroom|{neg_id}")],
        [("❌ به نتیجه نرسیدیم و خروج", f"g|negno|{neg_id}")],
        back_row("g|neg", "◀️ بازگشت به لیست مذاکرات"),
    ]

    try:
        await call.answer()
    except Exception:
        pass

    full_content = "\n".join(lines)
    ok = await safe_edit(call, full_content, reply_markup=kb(rows))
    if not ok:
        try:
            await call.answer("🔄 چت به‌روز است")
        except Exception:
            pass


@router.callback_query(F.data.startswith("g|negsend|"))
async def negotiation_send_prompt(call: CallbackQuery, state: FSMContext):
    neg_id = int(call.data.split("|")[2])
    await state.set_state(TradeFSM.neg_chat)
    await state.update_data(active_neg_id=neg_id)
    try:
        await call.answer()
    except Exception:
        pass
    text = (
        f"💬 <b>ارسال پیام در مذاکره #{neg_id}</b>\n\n"
        "متن پیام یا شرایط پیشنهادی خود را تایپ کرده و ارسال فرمایید تا فوراً در تاریخچه ثبت و به دیگر اعضا تحویل داده شود:\n\n"
        "<i>(برای انصراف /cancel بزنید)</i>"
    )
    rows = [[("◀️ بازگشت به اتاق مذاکره", f"g|negroom|{neg_id}")]]
    await safe_edit(call, text, reply_markup=kb(rows))


@router.message(TradeFSM.neg_chat)
async def negotiation_chat_input(message: Message, state: FSMContext):
    """هر پیام متنی بازیکن داخل اتاق مذاکره — بدون نیاز به دکمه، مستقیم ارسال می‌شود."""
    data = await state.get_data()
    neg_id = data.get("active_neg_id")
    text = (message.text or "").strip()
    if text in ("/cancel", "لغو", "خروج", "پایان"):
        await state.clear()
        return await send_home(message, "🚪 از اتاق مذاکره خارج شدید.",
                               reply_markup=kb([back_row("g|neg", "◀️ لیست مذاکرات")]))
    if not text:
        return await send_home(message, "❌ لطفاً متن پیام را ارسال کنید.")
    # state عمداً پاک نمی‌شود تا گفتگو پشت‌سرهم ادامه پیدا کند
    await _send_negotiation_msg(message, neg_id, text)


async def _generate_npc_diplomatic_reply(country_name: str, user_text: str) -> str:
    """پاسخ دیپلماتیک هوشمند و واقع‌گرایانه از طرف هیئت نمایندگی کشور هدف."""
    lower_t = user_text.lower()
    if any(k in lower_t for k in ["صلح", "آتش‌بس", "جنگ", "peace"]):
        return (
            f"پیام شما با عالی‌ترین مقامات کشور {country_name} در میان گذاشته شد. "
            "ما عمیقاً از صلح، ثبات منطقه‌ای و پایان تخاصم استقبال می‌کنیم. "
            "پیشنهاد می‌کنیم جهت نهایی‌سازی، دکمه «🤝 به توافق رسیدیم» را فشرده و «🕊 پیمان صلح» را منعقد فرمایید."
        )
    if any(k in lower_t for k in ["نظامی", "دفاع", "اتحاد", "جنگنده", "سرباز", "military"]):
        return (
            f"ستاد مشترک نیروهای مسلح {country_name} پیشنهادات دفاعی شما را بررسی نمود. "
            "ما آماده تشکیل بلوک امنیتی مشترک و اضافه شدن ۳۰٪ از توان دفاعی‌مان در مواجهه با تهدیدات خارجی هستیم. "
            "لطفاً پیمان نظامی را در منوی توافق ثبت فرمایید."
        )
    if any(k in lower_t for k in ["تجارت", "پول", "اقتصاد", "نفت", "گاز", "انرژی", "سود", "trade"]):
        return (
            f"وزارت بازرگانی و دارایی {country_name} از گسترش مبادلات اقتصادی با کشور شما حمایت می‌کند. "
            "ما مایل به برقراری پیمان رفیقای تجاری با تسهیم درصدی از سود معاملات فی‌مابین هستیم. "
            "آمادگی کامل جهت امضای معاهده وجود دارد."
        )
    if any(k in lower_t for k in ["تنگه", "هرمز", "سوئز", "دریایی", "عوارض"]):
        return (
            f"سیاست امنیت دریانوردی {country_name} بر عبور ایمن و احترام متقابل به آبراه‌ها و تنگه‌ها استوار است. "
            "همکاری‌های متقابل در خطوط کشتیرانی به سود اقتصاد هر دو کشور خواهد بود."
        )
    return (
        f"پیام شما توسط وزارت امور خارجه {country_name} دریافت و ثبت شد. "
        "ما خواستار توسعه روابط سازنده و امضای توافقات پایدار هستیم. "
        "هر زمان مایل بودید، دکمه «🤝 به توافق رسیدیم» را برگزینید تا معاهده رسمی تنظیم گردد."
    )


async def _send_negotiation_msg(message: Message, neg_id: int | None, text: str):
    if not neg_id:
        row = await db.fetchone(
            "SELECT n.id FROM negotiations n JOIN negotiation_members m ON m.neg_id=n.id "
            "WHERE m.user_id=? AND n.status IN ('open','pending') ORDER BY n.id DESC", (message.from_user.id,))
        if not row:
            return await send_home(message, "❌ شما در حال حاضر در هیچ مذاکره فعالی حضور ندارید.")
        neg_id = row["id"]

    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=?", (neg_id,))
    if not neg:
        return await send_home(message, "❌ مذاکره مورد نظر یافت نشد.")

    # ذخیره پیام کاربر در تاریخچه مذاکره
    await db.execute(
        "INSERT INTO negotiation_msgs(neg_id, sender_id, text) VALUES(?,?,?)",
        (neg_id, message.from_user.id, text))

    # دریافت سایر اعضای فعال مذاکره
    members = await db.fetchall(
        "SELECT user_id, role FROM negotiation_members WHERE neg_id=? AND user_id!=?",
        (neg_id, message.from_user.id))

    sender_name = await _cname(message.from_user.id)
    safe_text = html.escape(text)
    safe_sender = html.escape(sender_name)

    sent_count = 0
    human_total = 0
    human_delivered = 0
    undelivered: list[int] = []
    npc_targets = []
    for m in members:
        uid = m["user_id"]
        if uid < 0:
            npc_targets.append(uid)
            sent_count += 1
            continue
        human_total += 1
        # دو تلاش: اول با HTML، بعد متن خالی (اگر HTML مشکل داشت)
        res = None
        for attempt in range(2):
            try:
                res = await message.bot.send_message(
                    uid,
                    (f"🕊 <b>پیام جدید در مذاکره #{neg_id}</b>\n"
                     f"فرستنده: <b>{safe_sender}</b>\n\n"
                     f"«{safe_text}»") if attempt == 0 else
                    (f"🕊 پیام جدید در مذاکره #{neg_id}\n"
                     f"فرستنده: {sender_name}\n\n«{text}»"),
                    reply_markup=kb([
                        [("✍️ پاسخ به این پیام", f"g|negsend|{neg_id}")],
                        [("💬 مشاهده اتاق مذاکره", f"g|negroom|{neg_id}")],
                        [("🤝 به توافق رسیدیم", f"g|negok|{neg_id}")],
                    ]))
                break
            except Exception as e:
                log.warning("DM attempt %s failed to member %s: %s", attempt + 1, uid, e)
                res = None
        if res:
            sent_count += 1
            human_delivered += 1
        else:
            undelivered.append(uid)

    # اگر هدف یک هیئت دیپلماتیک باشد، پاسخ هوشمند متقابل تولید و ارسال شود
    for npc_id in npc_targets:
        c = await get_country(npc_id)
        cname = c["name"] if c else "هیئت دیپلماتیک"
        npc_reply = await _generate_npc_diplomatic_reply(cname, text)
        await db.execute(
            "INSERT INTO negotiation_msgs(neg_id, sender_id, text) VALUES(?,?,?)",
            (neg_id, npc_id, npc_reply))
        # ارسال پیام پاسخ هیئت دیپلماتیک به بازیکن
        try:
            await dm(message.bot,
                message.from_user.id,
                f"🏛 <b>پاسخ هیئت دیپلماتیک {html.escape(cname)} در مذاکره #{neg_id}:</b>\n\n"
                f"«{html.escape(npc_reply)}»",
                reply_markup=kb([
                    [("✍️ ارسال پیام بعدی", f"g|negsend|{neg_id}")],
                    [("💬 ورود به اتاق مذاکره", f"g|negroom|{neg_id}")],
                    [("🤝 به توافق رسیدیم", f"g|negok|{neg_id}")],
                ]))
        except Exception:
            pass

    if human_total and not human_delivered:
        names = []
        for u in undelivered[:3]:
            try:
                names.append(await _cname(u))
            except Exception:
                names.append(str(u))
        delivery = ("⚠️ <b>پیام در اتاق ذخیره شد، اما به طرف مقابل تحویل داده نشد.</b>\n"
                    f"دلیل معمول: {', '.join(names)} ربات را استارت نکرده یا بلاک کرده است.\n"
                    "📌 پیام شما از بین نرفته — طرف مقابل با «💬 مشاهده اتاق مذاکره» آن را می‌بیند.")
    else:
        delivery = f"👥 تحویل داده شده به {human_delivered} نفر"
    confirm_text = (
        f"✅ <b>پیام شما در مذاکره #{neg_id} ثبت و ارسال شد:</b>\n\n"
        f"«{safe_text}»\n\n{delivery}"
    )
    rows = [
        [("✍️ ارسال پیام بعدی", f"g|negsend|{neg_id}")],
        [("💬 مشاهده اتاق مذاکره", f"g|negroom|{neg_id}")],
        [("📨 ارسال دوباره به طرف مقابل", f"g|negresend|{neg_id}")],
        [("🤝 به توافق رسیدیم (انعقاد معاهده)", f"g|negok|{neg_id}")],
        back_row("g|neg", "◀️ لیست مذاکرات"),
    ]
    await message.answer(confirm_text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|negresend|"))
async def negotiation_resend(call: CallbackQuery):
    """ارسال دوبارهٔ آخرین پیام اتاق به همهٔ اعضا (اگر تحویل نشده بود)."""
    neg_id = int(call.data.split("|")[2])
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=?", (neg_id,))
    if not neg:
        return await call.answer("مذاکره یافت نشد", show_alert=True)
    last = await db.fetchone(
        "SELECT * FROM negotiation_msgs WHERE neg_id=? ORDER BY id DESC LIMIT 1", (neg_id,))
    if not last:
        return await call.answer("پیامی در این اتاق نیست", show_alert=True)
    members = await db.fetchall(
        "SELECT user_id FROM negotiation_members WHERE neg_id=? AND user_id>0 AND user_id!=?",
        (neg_id, call.from_user.id))
    if not members:
        return await call.answer("طرف مقابل انسانی در این مذاکره نیست", show_alert=True)
    sender_name = await _cname(last["sender_id"])
    sent = 0
    for m in members:
        try:
            await call.bot.send_message(
                int(m["user_id"]),
                f"🕊 پیام در مذاکره #{neg_id}\n"
                f"فرستنده: {sender_name}\n\n«{last['text']}»",
                reply_markup=kb([
                    [("✍️ پاسخ", f"g|negsend|{neg_id}")],
                    [("💬 مشاهده اتاق", f"g|negroom|{neg_id}")],
                ]))
            sent += 1
        except Exception as e:
            log.warning("resend failed to %s: %s", m["user_id"], e)
    if sent:
        await call.answer(f"✅ به {sent} نفر ارسال شد", show_alert=True)
    else:
        await call.answer("❌ باز هم تحویل نشد — طرف مقابل ربات را بلاک کرده است",
                          show_alert=True)


# ─── گفتگوی آزاد مذاکره (آخرین روتر) ───


@neg_router.message(F.text & ~F.text.startswith("/"))
async def negotiation_relay(message: Message, state: FSMContext):
    """هر متن عادی عضوِ مذاکره باز (بدون FSM فعال دیگر) به اعضای دیگر ارسال می‌شود."""
    curr_state = await state.get_state()
    if curr_state is not None and curr_state != "TradeFSM:neg_chat":
        return
    data = await state.get_data()
    neg_id = data.get("active_neg_id")
    if not neg_id:
        row = await db.fetchone(
            "SELECT n.* FROM negotiations n JOIN negotiation_members m ON m.neg_id=n.id "
            "WHERE m.user_id=? AND n.status IN ('open','pending') ORDER BY n.id DESC",
            (message.from_user.id,))
        if not row:
            return
        neg_id = row["id"]
    text = (message.text or "").strip()
    if not text or len(text) > 1000:
        return
    await _send_negotiation_msg(message, neg_id, text)


# ─── دعوت کشور سوم ───


@router.callback_query(F.data.startswith("g|neginv|"))
async def invite_third(call: CallbackQuery):
    neg_id = int(call.data.split("|")[2])
    members = {m["user_id"] for m in await db.fetchall(
        "SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))}
    if call.from_user.id not in members:
        return await call.answer("عضو نیستید", show_alert=True)
    countries = await db.fetchall(
        "SELECT u.id AS player_id, c.name, c.flag "
        "FROM users u JOIN countries c ON c.id=u.country_id "
        "WHERE u.id!=? AND u.banned=0 AND u.country_id IS NOT NULL ORDER BY c.name",
        (call.from_user.id,))
    rows = []
    for c in countries:
        if c["player_id"] not in members:
            rows.append([(f"{c['flag']} {c['name']}", f"g|neginvr|{neg_id}|{c['player_id']}")])
    if not rows:
        return await call.answer("کشور سومی موجود نیست", show_alert=True)
    rows.append(back_row(f"g|negroom|{neg_id}"))
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
    await _show_negotiation_room(call, neg_id)


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
        if m["user_id"] != call.from_user.id and m["user_id"] > 0:
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
    neg = await db.fetchone("SELECT * FROM negotiations WHERE id=? AND status IN ('open','pending')", (neg_id,))
    if not neg:
        return await call.answer("مذاکره یافت نشد", show_alert=True)
    members = await db.fetchall("SELECT user_id FROM negotiation_members WHERE neg_id=?", (neg_id,))
    if call.from_user.id not in {m["user_id"] for m in members} and call.from_user.id != neg["initiator_id"]:
        return await call.answer("عضو نیستید", show_alert=True)

    others = [m["user_id"] for m in members if m["user_id"] != call.from_user.id]
    if not others:
        return await call.answer("طرف مقابل در مذاکره مشخص نیست", show_alert=True)
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
    cname = await _cname(counterpart)
    lines = [f"📜 <b>انعقاد پیمان رسمی بین‌المللی</b>\nقرارداد بین شما و <b>{html.escape(cname)}</b>:\n"]
    rows = []
    for kind, (title, desc) in TREATY_KINDS.items():
        lines.append(f"• <b>{title}</b>: {desc}\n")
        rows.append([(f"✍️ انعقاد {title}", f"g|trty|{neg_id}|{kind}|{counterpart}")])
    rows.append(back_row(f"g|negroom|{neg_id}", "◀️ بازگشت به اتاق مذاکره"))
    try:
        await call.answer()
    except Exception:
        pass
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))
    except Exception:
        await call.message.answer("\n".join(lines), reply_markup=kb(rows))


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
        "SELECT u.id AS player_id, c.name, c.flag "
        "FROM users u JOIN countries c ON c.id=u.country_id "
        "WHERE u.id!=? AND u.banned=0 AND u.country_id IS NOT NULL ORDER BY c.name",
        (call.from_user.id,))
    rows = []
    for c in countries:
        if c["player_id"] not in members:
            rows.append([(f"👁 شاهد: {c['flag']} {c['name']}",
                          f"g|trtwit|{neg_id}|{kind}|{counterpart}|{c['player_id']}")])
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
    try:
        await call.answer(msg, show_alert=True)
    except Exception:
        pass
    try:
        await call.message.edit_text(
            f"✅ <b>پیمان شماره #{tid} با موفقیت تأیید شد:</b>\n{msg}\n\nجزئیات و آثار پیمان در بخش «📜 پیمان‌های من» فعال است.",
            reply_markup=kb([[("📜 پیمان‌های فعال من", "g|mytrt")], [("🏰 بازگشت به امپراطوری", "g|emp")]])
        )
    except Exception:
        pass


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
    try:
        await call.answer(msg, show_alert=True)
    except Exception:
        pass
    try:
        await call.message.edit_text(
            f"❌ <b>پیمان شماره #{tid} لغو/رد شد.</b>",
            reply_markup=kb([[("📜 پیمان‌های من", "g|mytrt")], [("🏰 بازگشت به امپراطوری", "g|emp")]])
        )
    except Exception:
        pass


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
        f"🏥 فروش {title} به سازمان نجات\nقیمت هر واحد: <b>{fmt_money(price)}</b>\n\n"
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
        f"✅ {fmt(qty)} {title} به سازمان نجات فروخته شد.\n💰 درآمد: {fmt_money(total)} (+رضایت ۰.۵)")
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
async def strait_attack_confirm(call: CallbackQuery):
    """صفحهٔ تأیید حملهٔ فرسایشی — همیشه اجازه می‌دهد، فقط نتیجه را شفاف می‌گوید."""
    from core.straits import attack_outlook
    sid = int(call.data.split("|")[2])
    s = await db.fetchone("SELECT * FROM straits WHERE id=? AND is_active=1", (sid,))
    if not s:
        return await call.answer("تنگه یافت نشد", show_alert=True)
    look = await attack_outlook(call.from_user.id, s)
    oc = look["owner_country"]
    owner_label = (f"{oc['flag']} <b>{oc['name']}</b>" if oc else "بدون مالک")

    if not s["owner_id"]:
        # تنگهٔ آزاد: استقرار بدون درگیری
        await call.answer()
        msg = await capture_strait(call.bot, call.from_user.id, sid)
        await call.message.answer(msg, reply_markup=kb([back_row("g|strait")]))
        return await straits_menu(call)

    if look["can_capture"]:
        verdict = (f"✅ <b>این حمله شانس تصرف دارد: {look['win_chance']}٪</b>")
    else:
        verdict = ("⚔️ <b>این حمله فرسایشی است — تصرف در همین حمله ممکن نیست</b>\n"
                   f"با حدود <b>{look['needed_rounds'] or '—'}</b> حملهٔ پیوسته، "
                   "دفاع مدافع شکسته می‌شود.")
    text = (
        f"⚓ <b>حمله به تنگهٔ {s['emoji']} {s['name']}</b>\n\n"
        f"🛡 مالک فعلی: {owner_label}\n\n"
        f"🚢 قدرت دریایی شما: <b>{fmt(look['my_naval'])}</b>\n"
        f"   (با استراتژی {look['strategy']['emoji']} {look['strategy']['name']}: "
        f"<b>{fmt(look['atk_power'])}</b>)\n"
        f"🛡 توان دفاع دریایی مدافع: <b>{fmt(look['owner_def'])}</b>\n"
        f"🎯 قدرت لازم برای تصرف: <b>{fmt(look['need'])}</b>\n\n"
        f"{verdict}\n\n"
        f"♻️ <b>نبرد فرسایشی است:</b> هر حمله حداقل "
        f"<b>{look['attrition']}٪</b> از ناوگان مدافع را از بین می‌برد، "
        "حتی اگر این بار تنگه را نگیرید.\n\n"
        "آیا حمله می‌کنید؟"
    )
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb([
        [("⚔️ بله، حمله کن", f"g|stgo|{sid}")],
        back_row("g|strait", "🔴 انصراف"),
    ]))


@router.callback_query(F.data.startswith("g|stgo|"))
async def strait_capture(call: CallbackQuery):
    sid = int(call.data.split("|")[2])
    msg = await capture_strait(call.bot, call.from_user.id, sid)
    await call.answer("🛰 گزارش نبرد دریایی صادر شد")
    # گزارش کامل (استراتژی + تلفات دو طرف) به‌صورت پیام ارسال می‌شود تا کوتاه نشود
    try:
        await call.message.answer(msg, reply_markup=kb([back_row("g|strait")]))
    except Exception:
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
        "SELECT c.*, u.id AS uid FROM countries c JOIN users u ON u.country_id=c.id "
        "WHERE u.id!=? AND u.banned=0 ORDER BY c.name", (call.from_user.id,))
    
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

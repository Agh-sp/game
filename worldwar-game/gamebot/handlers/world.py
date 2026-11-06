"""بخش‌های تازهٔ بازی: 🗺 استان‌ها، 🤝 اتحاد، ☢️ غنی‌سازی، 💵 درآمد.

همه در منوی «امپراطوری من» در دسترس هستند.
"""
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


class WorldFSM(StatesGroup):
    alliance_name = State()
    invite_query = State()
    enrich_stage = State()


# ═══════════════ 🗺 استان‌ها ═══════════════

@router.callback_query(F.data == "g|prov")
async def provinces_menu(call: CallbackQuery):
    from core import provinces as prov
    await call.answer()
    await call.message.edit_text(
        await prov.provinces_text(call.from_user.id),
        reply_markup=kb([back_row("g|emp", "◀️ امپراطوری من")]))


# ═══════════════ 💵 درآمد ═══════════════

@router.callback_query(F.data == "g|inc")
async def income_menu(call: CallbackQuery):
    from core import income as inc
    src = await inc.income_sources(call.from_user.id)
    g = src["growth"]
    lines = [
        f"💵 <b>درآمد {src['minutes']} دقیقه‌ای شما</b>\n",
        f"💰 مالیات مردم: <b>{fmt_money(src['tax']['amount'])}</b>",
        f"   └ ضریب اقتصاد کشور: ×{src['tax']['gdp']} | "
        f"رضایت ×{src['tax']['sat_mult']} | مالیات ×{src['tax']['tax_mult']}",
        f"🛢 فروش نفت: <b>{fmt_money(src['oil']['amount'])}</b>",
        f"   └ پایهٔ نفتی: {src['oil']['base_m']} میلیون | "
        f"تجهیزات ×{src['oil']['level_mult']}",
        f"⚓ عوارض تنگه‌ها: <b>{fmt_money(src['strait']['amount'])}</b>",
        f"   └ {src['strait']['count']} تنگه × {src['strait']['per_m']} میلیون\n",
        f"📊 <b>جمع هر دوره: {fmt_money(src['total'])}</b>",
        f"📈 ضریب ارتقا: <b>×{g['mult']}</b> از سقف ×{g['cap']}\n",
        "<b>راه‌های افزایش (خودکار):</b>",
        f"  🏗 پروژه‌های ساخته‌شده: +{round(g['project'] * 100)}٪",
        f"  🛠 تجهیزات استخراج نفت: +{round(g['rig'] * 100)}٪",
        f"  🏢 شرکت‌های اقتصادی: +{round(g['company'] * 100)}٪",
        f"  🙂 رضایت بالای ۵۰٪: +{round(g['satisfaction'] * 100)}٪",
        f"  🗺 استان‌های اضافه: +{round(g['province'] * 100)}٪",
        "\n💡 کشورهای قوی‌تر (چین، آمریکا، روسیه) پایهٔ بالاتری دارند، "
        "ولی کشورهای ضعیف با ارتقا می‌توانند جبران کنند.",
    ]
    await call.answer()
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=kb([back_row("g|emp", "◀️ امپراطوری من")]))


# ═══════════════ ☢️ غنی‌سازی ═══════════════

@router.callback_query(F.data == "g|enrich")
async def enrich_menu(call: CallbackQuery):
    from core import enrichment as en
    await en.settle(call.from_user.id)
    st = await en.get_state(call.from_user.id)
    nxt = int(st.get("stage") or 0) + 1
    rows = []
    if nxt <= en.MAX_STAGE:
        rows.append([(f"▶️ شروع مرحله {nxt}", f"g|enrichgo|{nxt}")])
    rows.append(back_row("g|emp", "◀️ امپراطوری من"))
    await call.answer()
    await call.message.edit_text(await en.enrichment_text(call.from_user.id),
                                 reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|enrichgo|"))
async def enrich_start(call: CallbackQuery):
    from core import enrichment as en
    stage = int(call.data.split("|")[2])
    ok, msg = await en.start_stage(call.from_user.id, stage)
    if not ok:
        return await call.answer(msg, show_alert=True)
    await call.answer("☢️ مرحله آغاز شد")
    await call.message.edit_text(
        msg, reply_markup=kb([back_row("g|enrich", "◀️ بخش غنی‌سازی")]))


# ═══════════════ 🤝 اتحاد ═══════════════

@router.callback_query(F.data == "g|ally")
async def alliance_menu(call: CallbackQuery, state: FSMContext):
    from core import alliances as al
    await state.clear()
    mine = await al.my_alliance(call.from_user.id)
    invites = await al.pending_invites(call.from_user.id)
    rows = []
    if mine:
        rows.append([("👥 اعضای اتحاد", "g|allymem")])
        rows.append([("➕ دعوت بازیکن جدید", "g|allyinv")])
        rows.append([("📋 فهرست اتحادهای جهان", "g|allylist")])
        rows.append([("🚪 خروج از اتحاد", "g|allyleave")])
    else:
        rows.append([("🆕 ساخت اتحاد جدید", "g|allynew")])
        if invites:
            rows.append([(f"📨 دعوت‌نامه‌ها ({len(invites)})", "g|allyinbox")])
        rows.append([("📋 فهرست اتحادهای جهان", "g|allylist")])
    rows.append(back_row("g|emp", "◀️ امپراطوری من"))
    await call.answer()
    await call.message.edit_text(await al.alliance_text(call.from_user.id),
                                 reply_markup=kb(rows))


@router.callback_query(F.data == "g|allynew")
async def alliance_new(call: CallbackQuery, state: FSMContext):
    await state.set_state(WorldFSM.alliance_name)
    await call.answer()
    await call.message.edit_text(
        "🆕 <b>ساخت اتحاد جدید</b>\n\n"
        "یک نام برای اتحاد بنویسید (۳ تا ۴۰ حرف):\n"
        "برای انصراف /cancel",
        reply_markup=kb([back_row("g|ally", "◀️ بازگشت")]))


@router.message(WorldFSM.alliance_name)
async def alliance_name_input(message: Message, state: FSMContext):
    from core import alliances as al
    await state.clear()
    ok, msg = await al.create_alliance(message.from_user.id, message.text or "")
    await send_home(message, msg,
                    reply_markup=kb([back_row("g|ally", "◀️ بخش اتحاد")]))


@router.callback_query(F.data == "g|allymem")
async def alliance_members_view(call: CallbackQuery):
    from core import alliances as al
    await call.answer()
    await call.message.edit_text(
        await al.alliance_text(call.from_user.id),
        reply_markup=kb([[("➕ دعوت بازیکن جدید", "g|allyinv")],
                         back_row("g|ally", "◀️ بازگشت")]))


@router.callback_query(F.data == "g|allyinv")
async def alliance_invite_menu(call: CallbackQuery, state: FSMContext):
    from core import alliances as al
    mine = await al.my_alliance(call.from_user.id)
    if not mine:
        return await call.answer("شما در اتحادی نیستید", show_alert=True)
    await state.set_state(WorldFSM.invite_query)
    await state.update_data(alliance_id=mine["id"])
    await call.answer()
    await call.message.edit_text(
        f"➕ <b>دعوت به اتحاد «{mine['name']}»</b>\n\n"
        "نام کشور یا آیدی عددی بازیکن مورد نظر را بنویسید:\n"
        "برای انصراف /cancel",
        reply_markup=kb([back_row("g|ally", "◀️ بازگشت")]))


@router.message(WorldFSM.invite_query)
async def alliance_invite_input(message: Message, state: FSMContext):
    from core import alliances as al
    data = await state.get_data()
    aid = data.get("alliance_id")
    query = (message.text or "").strip()
    if not query:
        return await send_home(message, "❌ نام یا آیدی را بنویسید.")
    await state.clear()
    # آیدی عددی
    target = None
    if query.isdigit():
        row = await db.fetchone("SELECT id FROM users WHERE id=?", (int(query),))
        target = row["id"] if row else None
    else:
        row = await db.fetchone(
            "SELECT u.id FROM users u JOIN countries c ON c.id=u.country_id "
            "WHERE c.name LIKE ? AND u.id!=? LIMIT 1", (f"%{query}%", message.from_user.id))
        target = row["id"] if row else None
    if not target:
        return await send_home(message, "❌ بازیکنی با این مشخصات پیدا نشد.")
    ok, msg = await al.invite(aid, message.from_user.id, int(target))
    if ok:
        try:
            from gamebot.common import dm
            mine = await al.my_alliance(message.from_user.id)
            inv = await db.fetchone(
                "SELECT id FROM alliance_invites WHERE alliance_id=? AND invitee_id=? "
                "AND status='pending' ORDER BY id DESC", (aid, target))
            await dm(message.bot, int(target),
                     f"🤝 <b>دعوت‌نامهٔ اتحاد</b>\n\n"
                     f"شما به اتحاد «<b>{mine['name'] if mine else '—'}</b>» دعوت شده‌اید.\n"
                     "برای پاسخ وارد بخش 🤝 اتحاد شوید.",
                     reply_markup=kb([[("✅ مشاهدهٔ دعوت‌نامه", "g|allyinbox")]]))
        except Exception:
            pass
    await send_home(message, msg,
                    reply_markup=kb([back_row("g|ally", "◀️ بخش اتحاد")]))


@router.callback_query(F.data == "g|allyinbox")
async def alliance_inbox(call: CallbackQuery):
    from core import alliances as al
    invites = await al.pending_invites(call.from_user.id)
    if not invites:
        return await call.answer("دعوت‌نامه‌ای ندارید", show_alert=True)
    lines = ["📨 <b>دعوت‌نامه‌های اتحاد</b>\n"]
    rows = []
    for inv in invites:
        lines.append(f"• اتحاد «<b>{inv['alliance_name']}</b>»")
        rows.append([(f"✅ قبول «{inv['alliance_name']}»", f"g|allyacc|{inv['id']}"),
                     (f"❌ رد", f"g|allydec|{inv['id']}")])
    rows.append(back_row("g|ally", "◀️ بازگشت"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|allyacc|"))
async def alliance_accept(call: CallbackQuery):
    from core import alliances as al
    iid = int(call.data.split("|")[2])
    ok, msg = await al.accept_invite(iid, call.from_user.id)
    await call.answer(msg[:180], show_alert=True)
    if ok:
        await call.message.edit_text(
            await al.alliance_text(call.from_user.id),
            reply_markup=kb([("👥 اعضای اتحاد", "g|allymem"),
                             back_row("g|ally", "◀️ بخش اتحاد")]))


@router.callback_query(F.data.startswith("g|allydec|"))
async def alliance_decline(call: CallbackQuery):
    from core import alliances as al
    iid = int(call.data.split("|")[2])
    ok, msg = await al.decline_invite(iid, call.from_user.id)
    await call.answer(msg[:180], show_alert=True)
    await call.message.edit_text(await al.alliance_text(call.from_user.id),
                                 reply_markup=kb([back_row("g|ally", "◀️ بخش اتحاد")]))


@router.callback_query(F.data == "g|allylist")
async def alliance_list(call: CallbackQuery):
    from core import alliances as al
    items = await al.list_alliances()
    if not items:
        body = "📋 <b>فهرست اتحادهای جهان</b>\n\nهنوز هیچ اتحادی ساخته نشده است."
    else:
        lines = ["📋 <b>فهرست اتحادهای جهان</b>\n"]
        for a in items[:15]:
            lines.append(f"🤝 <b>{a['name']}</b> — {a['members']} عضو")
        body = "\n".join(lines)
    await call.answer()
    await call.message.edit_text(body,
                                 reply_markup=kb([back_row("g|ally", "◀️ بازگشت")]))


@router.callback_query(F.data == "g|allyleave")
async def alliance_leave(call: CallbackQuery):
    from core import alliances as al
    ok, msg = await al.leave_alliance(call.from_user.id)
    await call.answer(msg[:180], show_alert=True)
    await call.message.edit_text(await al.alliance_text(call.from_user.id),
                                 reply_markup=kb([back_row("g|ally", "◀️ بخش اتحاد")]))

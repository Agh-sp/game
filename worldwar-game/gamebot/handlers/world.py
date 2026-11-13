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
    bomb_name = State()   # ☢️ نام دلخواه کلاهک هسته‌ای


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
    lines = [f"💵 <b>درآمد {src['minutes']} دقیقه‌ای شما</b>\n"]
    lines += await inc.income_breakdown_lines(call.from_user.id)
    lines += [
        "",
        "<b>💰 جزئیات مالیات:</b>",
        f"  ضریب اقتصاد کشور: ×{src['tax']['gdp']}",
        f"  رضایت مردم: ×{src['tax']['sat_mult']}",
        f"  نرخ مالیات: ×{src['tax']['tax_mult']}",
        "",
        "<b>🛢 جزئیات نفت:</b>",
        f"  پایهٔ نفتی کشور: {src['oil']['base_m']} میلیون",
        f"  تعداد دکل نفتی: <b>{src['oil']['rigs']}</b>",
        f"  پاداش دکل‌ها: <b>×{src['oil']['rig_mult']}</b> "
        f"(هر دکل {src['oil']['bonus_pct']:g}٪ بیشتر)",
        f"  تجهیزات استخراج: ×{src['oil']['level_mult']}",
        "",
        "<b>⚓ تنگه‌ها:</b>",
        f"  {src['strait']['count']} تنگه × {src['strait']['per_m']} میلیون",
        "",
        "💡 <b>هر دکلی که می‌سازی درآمدت را بیشتر می‌کند.</b>",
        "دکل نفتی از 🎖 پادگان → دستهٔ گاز/نفت ساخته می‌شود.",
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
    # ☢️ بعد از ۹۰٪: زرادخانه و ساخت بمب اتم
    rows.append([("☢️ سلاح هسته‌ای و بمب اتم", "g|nuke")])
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


# ═══════════════ ☢️ سلاح هسته‌ای (بمب اتم) ═══════════════

@router.callback_query(F.data == "g|nuke")
async def nuke_menu(call: CallbackQuery, state: FSMContext):
    """زرادخانهٔ هسته‌ای: ساخت کلاهک، فهرست کلاهک‌ها و شلیک."""
    from core import nuke
    await state.clear()
    await nuke.settle(call.from_user.id)
    text = await nuke.arsenal_text(call.from_user.id)
    ok, why = await nuke.can_build(call.from_user.id)
    can_strike, strike_why = await nuke.can_strike(call.from_user.id)
    rows = []
    if ok:
        rows.append([("🏭 ساخت کلاهک هسته‌ای", "g|nukebuild")])
    else:
        rows.append([("🏭 ساخت کلاهک (قفل)", "g|nukewhy")])
    if can_strike:
        rows.append([("🚀 شلیک به دشمن", "g|nuketg")])
    else:
        rows.append([("🚀 شلیک (قفل)", "g|nukewhy")])
    rows.append([("📖 راهنمای بمب اتم", "g|nukehelp")])
    rows.append(back_row("g|enrich", "◀️ غنی‌سازی"))
    await call.answer()
    try:
        await call.message.edit_text(text, reply_markup=kb(rows))
    except Exception:
        await call.message.answer(text, reply_markup=kb(rows))


@router.callback_query(F.data == "g|nukewhy")
async def nuke_why(call: CallbackQuery):
    """دلیل قفل‌بودن ساخت/شلیک."""
    from core import nuke
    ok_b, why_b = await nuke.can_build(call.from_user.id)
    ok_s, why_s = await nuke.can_strike(call.from_user.id)
    lines = ["☢️ <b>وضعیت سلاح هسته‌ای</b>", ""]
    lines.append(("✅ ساخت ممکن است." if ok_b else f"🏭 ساخت: {why_b}"))
    lines.append(("✅ شلیک ممکن است." if ok_s else f"🚀 شلیک: {why_s}"))
    await call.answer()
    await call.message.edit_text("\n".join(lines),
                                 reply_markup=kb([[("🔄 بروزرسانی", "g|nuke")],
                                                  back_row("g|enrich", "◀️ غنی‌سازی")]))


@router.callback_query(F.data == "g|nukebuild")
async def nuke_build_start(call: CallbackQuery, state: FSMContext):
    """شروع ساخت: گرفتن نام دلخواه برای کلاهک."""
    from core import nuke
    ok, why = await nuke.can_build(call.from_user.id)
    if not ok:
        return await call.answer(why, show_alert=True)
    await state.set_state(WorldFSM.bomb_name)
    await call.answer()
    await call.message.edit_text(
        "🏭 <b>ساخت کلاهک هسته‌ای</b>\n\n"
        "یک نام برای این سلاح بنویسید (مثلاً «فاتح هسته‌ای»)\n"
        "اگر نمی‌خواهید نام بگذارید، بنویسید: <code>-</code>\n"
        "برای انصراف /cancel",
        reply_markup=kb([[("❌ انصراف", "g|nuke")]]))


@router.message(WorldFSM.bomb_name)
async def nuke_build_name(message: Message, state: FSMContext):
    from core import nuke
    raw = (message.text or "").strip()
    await state.clear()
    name = "" if raw in ("-", "—", "") else raw[:40]
    ok, msg = await nuke.build(message.bot, message.from_user.id, name)
    await send_home(message, msg, reply_markup=kb([[("☢️ زرادخانه", "g|nuke")]]))


@router.callback_query(F.data == "g|nuketg")
async def nuke_targets(call: CallbackQuery):
    """فهرست کشورهای قابل هدف برای ضربهٔ هسته‌ای."""
    from core import nuke
    ok, why = await nuke.can_strike(call.from_user.id)
    if not ok:
        return await call.answer(why, show_alert=True)
    targets = await nuke.targets(call.from_user.id)
    lines = ["🚀 <b>انتخاب هدف ضربهٔ هسته‌ای</b>\n",
             f"📦 کلاهک آماده: <b>{fmt(int((await nuke.arsenal(call.from_user.id)).get('bombs') or 0))}</b>\n",
             "⚠️ هر ضربه: تلفات غیرنظامی، فرسایش سنگین، احتمال جداشدن استان و محکومیت جهانی.\n"]
    rows = []
    for t in targets[:12]:
        lines.append(f"{t['flag']} <b>{t['name']}</b>")
        rows.append([(f"☢️ {t['flag']} {t['name']}", f"g|nukeconf|{t['user_id']}")])
    if not targets:
        lines.append("— کشوری برای هدف نیست —")
    rows.append([("◀️ زرادخانه", "g|nuke")])
    await call.answer()
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))
    except Exception:
        await call.message.answer("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|nukeconf|"))
async def nuke_confirm(call: CallbackQuery):
    """پیش‌نمایش اثر ضربه و تأیید نهایی."""
    from core import nuke
    defender_id = int(call.data.split("|")[2])
    ok, why = await nuke.can_strike(call.from_user.id)
    if not ok:
        return await call.answer(why, show_alert=True)
    look = await nuke.outlook(call.from_user.id, defender_id)
    c = look["country"]
    lines = [
        "☢️ <b>تأیید ضربهٔ هسته‌ای</b>",
        "",
        f"🎯 هدف: {c['flag']} <b>{c['name']}</b>" if c else "🎯 هدف: —",
        f"💣 قدرت کلاهک: <b>{fmt(look['yield_kt'])} کیلوتن</b>",
        f"🗺 استان‌های هدف: <b>{fmt(look['provinces'])}</b>",
        f"🛡 پدافند هدف: <b>{fmt(look['shield'])}</b> (اثر حمله {100 - look['mitigation']}٪)",
        "",
        f"💀 تلفات غیرنظامی تخمینی: <b>{fmt(int(look['civilian']))}</b> نفر",
        f"😞 افت رضایت هدف: <b>-{look['satisfaction_drop']}٪</b>",
        f"⛓ فرسایش هدف: <b>+{look['wear']}٪</b>",
        f"💰 غارت خزانه: <b>{look['loot_percent']}٪</b>",
        "",
        "⚠️ این عمل غیرقابل بازگشت است و در تاریخ جهان ثبت می‌شود.",
    ]
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("☢️💥 شلیک کن — تأیید نهایی", f"g|nukego|{defender_id}")],
        [("❌ انصراف", "g|nuke")],
    ]))


@router.callback_query(F.data.startswith("g|nukego|"))
async def nuke_fire(call: CallbackQuery):
    from core import nuke
    defender_id = int(call.data.split("|")[2])
    await call.answer("☢️ در حال شلیک…")
    report = await nuke.strike(call.bot, call.from_user.id, defender_id)
    try:
        await call.message.edit_text(report, reply_markup=kb([
            [("☢️ زرادخانه", "g|nuke")],
        ]))
    except Exception:
        await call.message.answer(report, reply_markup=kb([[("☢️ زرادخانه", "g|nuke")]]))


@router.callback_query(F.data == "g|nukehelp")
async def nuke_help(call: CallbackQuery):
    from core import nuke
    n = {k: await nuke._num(k, d) for k, d in (
        ("nuke_bomb_cost_m", 1800), ("nuke_bomb_materials", 40000),
        ("nuke_bomb_coins", 25), ("nuke_bomb_minutes", 30),
        ("nuke_bomb_yield_kt", 150), ("nuke_bomb_limit", 8),
        ("nuke_strike_cooldown_hours", 12), ("nuke_blast_provinces", 40),
        ("nuke_blast_max_provinces", 2), ("nuke_blast_loot_percent", 25),
        ("nuke_blast_wear", 35), ("nuke_blast_satisfaction", 45),
        ("nuke_blast_civilian", 900000), ("nuke_fallout_self", 6),
        ("nuke_catastrophe_chance", 6))}
    text = (
        "📖 <b>راهنمای سلاح هسته‌ای</b>\n\n"
        "۱️⃣ <b>غنی‌سازی:</b> چهار مرحله را تا ۹۰٪ کامل کنید (هر مرحله ۵ دقیقه).\n"
        "۲️⃣ <b>ساخت کلاهک:</b> در تأسیسات فعال، با هزینه و مصالح و سکه.\n"
        f"   💰 {fmt_money(int(n['nuke_bomb_cost_m'] * 1_000_000))} • "
        f"🧱 {fmt(int(n['nuke_bomb_materials']))} • 🪙 {fmt(int(n['nuke_bomb_coins']))}\n"
        f"   ⏱ {int(n['nuke_bomb_minutes'])} دقیقه • 💣 {int(n['nuke_bomb_yield_kt'])} کیلوتن\n"
        f"   📦 سقف زرادخانه: {int(n['nuke_bomb_limit'])} کلاهک\n"
        "۳️⃣ <b>شلیک:</b> کشور هدف را انتخاب و تأیید کنید.\n"
        f"   ⏱ کول‌داون هر ضربه: {int(n['nuke_strike_cooldown_hours'])} ساعت\n\n"
        "<b>اثر واقعی هر ضربه:</b>\n"
        f"  💀 تا ~{fmt(int(n['nuke_blast_civilian']))} تلفات غیرنظامی\n"
        f"  😞 افت رضایت هدف تا {int(n['nuke_blast_satisfaction'])}٪\n"
        f"  ⛓ فرسایش هدف تا {int(n['nuke_blast_wear'])}٪\n"
        f"  💰 غارت {int(n['nuke_blast_loot_percent'])}٪ خزانه\n"
        f"  🗺 احتمال {int(n['nuke_blast_provinces'])}٪ جداشدن تا "
        f"{int(n['nuke_blast_max_provinces'])} استان\n"
        f"  🌍 محکومیت جهانی: {int(n['nuke_fallout_self'])}٪ افت رضایت خودتان\n"
        f"  🔥 احتمال فاجعهٔ انسانی: {int(n['nuke_catastrophe_chance'])}٪\n\n"
        "🛡 پدافند دشمن اثر را کم می‌کند (حداکثر ۳۵٪) و تأسیسات آسیب‌دیده باید "
        "اول بازسازی شود.\n"
        "⚙️ همهٔ این اعداد از پنل ادمین قابل تغییرند."
    )
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb([[("◀️ زرادخانه", "g|nuke")]]))

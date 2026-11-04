"""اتاق جنگ: اعلان جنگ (با/بدون مجوز)، حمله (۶ نوع) و عملیات سایبری."""
import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import (announce, army_power, bump_progress, get_country,
                          get_state, has_project_named, is_disarmed,
                          is_jammed, is_leader_blocked, sub_asset, veto_users)
from core.utils import fmt, fmt_money, add_hours, iso, hours_left, fmt_hm, jloads, clamp
from gamebot.common import back_row, blocked_banner, kb, send_home, dm

router = Router()

ATTACK_TYPES = {"sea": "⚓ دریایی", "air": "✈️ هوایی", "land": "🪖 زمینی",
                "missile": "🚀 موشکی", "space": "🛰️ فضایی", "mixed": "🔀 ترکیبی"}

ATTACK_CATS = {"sea": ["sea"], "air": ["air"], "land": ["land"],
               "missile": ["missile", "land"], "space": ["space"],
               "mixed": ["sea", "air", "land", "missile", "space"]}

ATTACK_RULES = {
    "sea": "کشور هدف باید دریا داشته باشد و شما نیروی دریایی داشته باشید",
    "air": "نیاز به تجهیزات هوایی + ناو هواپیمابر، پایگاه نزدیک یا هم‌منطقه بودن",
    "land": "هم‌منطقه بودن یا پایگاه در منطقه هدف + تجهیزات زمینی یا سرباز",
    "missile": "از هر فاصله‌ای — نیاز به موشک (کروز/بالستیک/ضدکشتی/راکت‌انداز)",
    "space": "از هرجای دنیا — فقط با تسلیحات فضایی",
    "mixed": "ترکیب دو یا چند نوع حمله",
}


class WarFSM(StatesGroup):
    reason = State()
    evidence = State()
    atk_qty = State()
    steal_amount = State()


# ─── منوی اتاق جنگ ───


async def war_room(call: CallbackQuery):
    state = await get_state(call.from_user.id)
    if await is_jammed(call.from_user.id):
        return await call.answer("📡 سرورهای شما اختلال دارند! فقط بیانیه مجاز است.", show_alert=True)
    wars = await db.fetchall(
        "SELECT w.*, ca.name AS atk_name, ca.flag AS atk_flag, cd.name AS def_name, cd.flag AS def_flag "
        "FROM wars w "
        "JOIN users ua ON ua.id=w.attacker_id JOIN countries ca ON ca.id=ua.country_id "
        "JOIN users ud ON ud.id=w.defender_id JOIN countries cd ON cd.id=ud.country_id "
        "WHERE (w.attacker_id=? OR w.defender_id=?) AND w.status IN ('voting','active')",
        (call.from_user.id, call.from_user.id))
    lines = ["⚔️ <b>اتاق جنگ</b>\n"]
    if wars:
        lines.append("🔥 <b>جنگ‌های من:</b>")
        for w in wars:
            role = "🗡 مهاجم" if w["attacker_id"] == call.from_user.id else "🛡 مدافع"
            status = "🗳 در رای‌گیری مجوز" if w["status"] == "voting" else "🔥 فعال"
            crime = " | ⚠️ جنایت جنگی" if w["war_crime"] else ""
            lines.append(
                f"{role} علیه {w['def_flag'] if w['attacker_id'] == call.from_user.id else w['atk_flag']} "
                f"{w['def_name'] if w['attacker_id'] == call.from_user.id else w['atk_name']} — {status}{crime}")
    else:
        lines.append("در حال حاضر در جنگی نیستید.")
    lines += ["\n" + blocked_banner(state)]
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("📢 اعلان جنگ", "g|wdec")],
        [("🗡 حمله", "g|watk")],
        [("🕶 سایبری", "g|wcyb")],
        back_row("g|emp"),
    ]))


@router.callback_query(F.data == "g|war")
async def war_menu(call: CallbackQuery):
    await war_room(call)


async def enemy_countries(user_id: int) -> list[dict]:
    """کشورهای قابل هدف‌گیری (اعلان جنگ / سایبری).

    ملاک، کشورِ ثبت‌شده روی کاربر (`users.country_id`) است نه فقط `countries.owner_id`؛
    قبلاً کشورهایی مثل روسیه/ژاپن که owner_id آن‌ها خالی مانده بود در هیچ لیستی نمی‌آمدند
    و جنگ/عملیات سایبری روی آن‌ها ممکن نبود.
    """
    rows = await db.fetchall(
        "SELECT c.*, u.id AS player_id, u.full_name FROM users u "
        "JOIN countries c ON c.id = u.country_id "
        "WHERE u.id != ? AND u.banned = 0 AND c.is_active = 1 "
        "ORDER BY c.name", (user_id,))
    for r in rows:
        r["owner_uid"] = r["player_id"]      # شناسه بازیکنِ هدف (نه owner_id جدول کشورها)
    return rows


# ─── اعلان جنگ ───


@router.callback_query(F.data == "g|wdec")
async def declare_list(call: CallbackQuery):
    if await is_leader_blocked(call.from_user.id):
        return await call.answer("🚫 رهبر شما ترور شده — دیپلماسی مسدود است!", show_alert=True)
    countries = await enemy_countries(call.from_user.id)
    if not countries:
        return await call.answer("کشور دیگری برای جنگ وجود ندارد", show_alert=True)
    rows = [[(f"{c['flag']} {c['name']}", f"g|wdec|{c['owner_uid']}")] for c in countries]
    rows.append(back_row("g|war"))
    await call.answer()
    await call.message.edit_text(
        "📢 <b>اعلان جنگ</b>\n\nکشور دشمن را انتخاب کنید. حمله فقط بعد از اعلان جنگ ممکن است:\n"
        "• <b>با مجوز</b>: دلایل و مدارک می‌دهید، سازمان ملل رای‌گیری می‌کند.\n"
        "• <b>بدون مجوز</b>: جنگ فوری شروع می‌شود اما ممکن است «جنایت جنگی» ثبت شود.",
        reply_markup=kb(rows),
    )


@router.callback_query(F.data.startswith("g|wdec|"))
async def declare_mode(call: CallbackQuery):
    defender_id = int(call.data.split("|")[2])
    d_country = await get_country(defender_id)
    await call.answer()
    await call.message.edit_text(
        f"📢 اعلان جنگ علیه {d_country['flag']} <b>{d_country['name']}</b>\n\nروش را انتخاب کنید:",
        reply_markup=kb([
            [("🗳 با مجوز سازمان ملل", f"g|wperm|{defender_id}")],
            [("⚡ بدون مجوز (فوری)", f"g|wnoperm|{defender_id}")],
            back_row("g|wdec"),
        ]),
    )


@router.callback_query(F.data.startswith("g|wperm|"))
async def declare_with_permission(call: CallbackQuery, state: FSMContext):
    defender_id = int(call.data.split("|")[2])
    await state.set_state(WarFSM.reason)
    await state.update_data(defender_id=defender_id, permission=1)
    await call.answer()
    await call.message.edit_text(
        "🗳 <b>اعلان جنگ با مجوز</b>\n\n"
        "دلایل خود برای جنگ را بنویسید (بعداً می‌توانید مدرک هم بفرستید):\n برای انصراف /cancel"
    )


@router.message(WarFSM.reason)
async def war_reason(message: Message, state: FSMContext):
    reason = (message.text or "").strip()
    if not reason or len(reason) > 500:
        return await send_home(message, "❌ دلیل باید بین ۱ تا ۵۰۰ حرف باشد.")
    await state.set_state(WarFSM.evidence)
    await state.update_data(reason=reason)
    await send_home(message, 
        "📎 اگر <b>مدرک</b> (عکس) دارید همین‌جا بفرستید، وگرنه دکمه «بدون مدرک» را بزنید:",
        reply_markup=kb([[("⏭ بدون مدرک ادامه بده", "g|wnoev")]]),
    )


@router.message(WarFSM.evidence, F.photo)
async def war_evidence(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await create_war(message.from_user.id, data["defender_id"], data["reason"],
                    data.get("permission", 1), message.photo[-1].file_id, message.bot)


@router.callback_query(F.data == "g|wnoev")
async def war_no_evidence(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await create_war(call.from_user.id, data["defender_id"], data["reason"],
                    data.get("permission", 1), "", call.bot)


async def create_war(attacker_id: int, defender_id: int, reason: str,
                     permission: int, evidence: str, bot):
    a_country = await get_country(attacker_id)
    d_country = await get_country(defender_id)
    status = "voting" if permission else "active"
    war_id = await db.execute(
        "INSERT INTO wars(attacker_id, defender_id, reason, permission, status) VALUES(?,?,?,?,?)",
        (attacker_id, defender_id, reason, permission, status))
    if permission:
        # رای‌گیری مجوز حمله در سازمان ملل — پیش‌فرض ۳۰ دقیقه
        hours = float(await get_setting("war_vote_minutes", "30")) / 60
        vote_id = await db.execute(
            "INSERT INTO un_votes(title, kind, subject_id, options, ends_at, created_by) VALUES(?,?,?,?,?,?)",
            (f"مجوز جنگ {a_country['name']} علیه {d_country['name']}",
             "war", war_id, '["تایید","رد","بی‌طرف"]', add_hours(hours), attacker_id))
        await announce(bot,
                       f"🗳 سازمان ملل: درخواست <b>مجوز جنگ</b> {a_country['flag']} {a_country['name']} "
                       f"علیه {d_country['flag']} {d_country['name']}\nدلیل: {reason}\n"
                       "کشورها از بخش 🕊 سازمان ملل رأی می‌دهند.", section="un")
    else:
        # جنگ فوری + بررسی جنایت جنگی
        hours = float(await get_setting("vote_duration_hours", "24"))
        await db.execute(
            "INSERT INTO un_votes(title, kind, subject_id, options, ends_at, created_by) VALUES(?,?,?,?,?,?)",
            (f"آیا جنگ {a_country['name']} علیه {d_country['name']} جنایت جنگی است؟",
             "crime", war_id, '["جنایت جنگی است","جنایت نیست","بی‌طرف"]', add_hours(hours), attacker_id))
        await announce(bot,
                       f"⚔️ {a_country['flag']} {a_country['name']} بدون مجوز سازمان ملل به "
                       f"{d_country['flag']} {d_country['name']} اعلان جنگ داد!", section="war_declare")
    try:
        await dm(bot, 
            defender_id,
            f"⚔️ کشور {a_country['flag']} <b>{a_country['name']}</b> به شما اعلان جنگ داد!\n"
            + ("این جنگ در انتظار رأی سازمان ملل است." if permission else "جنگ فعال شد — آماده دفاع باشید!"))
    except Exception:
        pass
    # پیمان نظامی: متحدان مدافع در جبهه او می‌جنگند
    from core.treaties import pact_allies
    for ally in await pact_allies(defender_id):
        if ally in (attacker_id, defender_id):
            continue
        try:
            await dm(bot, 
                ally,
                f"🤝 متحد شما {d_country['flag']} <b>{d_country['name']}</b> مورد اعلان جنگ "
                f"{a_country['flag']} {a_country['name']} قرار گرفت!\n"
                "طبق پیمان نظامی، شما در جبهه این کشور هستید و قدرت شما به دفاعش کمک می‌کند.")
        except Exception:
            pass
    # سازمان نجات: برای هر جنگ یک بخش/کمپین مجزا
    try:
        from core.rescue import ensure_campaign
        await ensure_campaign(war_id)
    except Exception:
        pass
    text = (
        f"📢 اعلان جنگ ثبت شد علیه {d_country['flag']} <b>{d_country['name']}</b>!\n"
        + ("🗳 در انتظار رأی سازمان ملل — اگر اکثریت تأیید کنند حمله آزاد می‌شود."
           if permission else "⚡ جنگ فعال است! از بخش 🗡 حمله حمله کنید.")
    )
    from gamebot.common import main_menu_kb
    await dm(bot, attacker_id, text)


@router.callback_query(F.data.startswith("g|wnoperm|"))
async def declare_no_permission(call: CallbackQuery, state: FSMContext):
    defender_id = int(call.data.split("|")[2])
    await state.clear()
    d_country = await get_country(defender_id)
    await call.answer()
    await call.message.edit_text(
        f"⚡ اعلان جنگ فوری علیه {d_country['flag']} <b>{d_country['name']}</b>\n\n"
        "⚠️ سازمان ملل ممکن است این جنگ را «جنایت جنگی» ثبت کند (جنگ لغو نمی‌شود).\nتأیید می‌کنید؟",
        reply_markup=kb([
            [("✅ تأیید اعلان جنگ", f"g|wnpgo|{defender_id}")],
            back_row("g|wdec"),
        ]),
    )


@router.callback_query(F.data.startswith("g|wnpgo|"))
async def declare_no_permission_go(call: CallbackQuery, state: FSMContext):
    defender_id = int(call.data.split("|")[2])
    await state.clear()
    await create_war(call.from_user.id, defender_id, "بدون مجوز", 0, "", call.bot)
    await call.answer("⚔️ جنگ اعلان شد")
    await war_room(call)


# ─── حمله ───


@router.callback_query(F.data == "g|watk")
async def attack_wars(call: CallbackQuery):
    if await is_disarmed(call.from_user.id):
        return await call.answer("🕊 خلع سلاح شده‌اید — حمله ممکن نیست!", show_alert=True)
    if await is_leader_blocked(call.from_user.id):
        return await call.answer("🚫 رهبر شما ترور شده!", show_alert=True)
    await settle_votes(call.bot)
    wars = await db.fetchall(
        "SELECT w.*, cd.name AS def_name, cd.flag AS def_flag, cd.has_sea, cd.id AS cid "
        "FROM wars w JOIN users ud ON ud.id=w.defender_id JOIN countries cd ON cd.id=ud.country_id "
        "WHERE w.attacker_id=? AND w.status='active'", (call.from_user.id,))
    if not wars:
        voting = await db.fetchall(
            "SELECT w.*, cd.name AS def_name FROM wars w JOIN users ud ON ud.id=w.defender_id "
            "JOIN countries cd ON cd.id=ud.country_id WHERE w.attacker_id=? AND w.status='voting'",
            (call.from_user.id,))
        if voting:
            votes = await db.fetchall(
                "SELECT ends_at FROM un_votes WHERE kind='war' AND status='open' ORDER BY id DESC LIMIT 1")
            left = fmt_hm(hours_left(votes[0]["ends_at"])) if votes else "—"
            return await call.answer(
                f"🗳 هنوز مجوز سازمان ملل صادر نشده — {left} مانده. حمله پس از پایان رای‌گیری آزاد می‌شود.",
                show_alert=True)
        rejected = await db.fetchone(
            "SELECT id FROM wars WHERE attacker_id=? AND status='rejected' LIMIT 1", (call.from_user.id,))
        if rejected:
            return await call.answer(
                "🗳 مجوز جنگ شما رد شد. یک بار دیگر اعلان جنگ بدهید؛ این‌بار «بدون مجوز» را بزنید تا فوری فعال شود.",
                show_alert=True)
        return await call.answer("اول باید اعلان جنگ بدهید!", show_alert=True)
    rows = [[(f"🎯 {w['def_flag']} {w['def_name']}", f"g|watkc|{w['id']}")] for w in wars]
    rows.append(back_row("g|war"))
    await call.answer()
    await call.message.edit_text("🗡 <b>حمله</b>\n\nجنگ فعال خود را انتخاب کنید:", reply_markup=kb(rows))


async def _my_equipment(user_id: int) -> list[dict]:
    """همه تجهیزات فعال بازیکن همراه با کلید دسته‌بندی."""
    return await db.fetchall(
        "SELECT e.*, c.key AS cat_key, a.quantity FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id LEFT JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0", (user_id,))


def _is_missile(e: dict) -> bool:
    """آیا این تجهیز یک سلاح موشکی/راکتی است؟"""
    name = e.get("name") or ""
    sub = (e.get("subcategory") or "").lower()
    return (e.get("cat_key") == "missile" or sub in ("artillery", "space_weapon", "cruise",
                                                     "ballistic", "antiship")
            or "موشک" in name or "راکت" in name or "هایمارس" in name)


async def _attack_options(user_id: int, defender_id: int) -> tuple[dict, dict]:
    """بررسی قواعد هر نوع حمله؛ خروجی: (dict وضعیت، dict توضیح)."""
    d_country = await get_country(defender_id)
    a_country = await get_country(user_id)
    my_equipment = await _my_equipment(user_id)
    has = lambda cat: any(e["cat_key"] == cat for e in my_equipment)
    has_carrier = any((e.get("subcategory") or "") == "carrier" or "ناو هواپیمابر" in (e.get("name") or "")
                      for e in my_equipment)
    has_missile = any(_is_missile(e) for e in my_equipment)
    soldiers = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
        (user_id,))
    has_soldiers = bool(soldiers and soldiers["c"] > 0)
    bases = await db.fetchall(
        "SELECT b.*, c.region FROM bases b JOIN countries c ON c.owner_id=b.host_id "
        "WHERE b.guest_id=? AND b.status='active'", (user_id,))
    base_near = any(b["region"] == d_country["region"] for b in bases) if d_country else False
    same_region = bool(a_country and d_country and a_country["region"] == d_country["region"])

    sea_ok = bool(d_country and d_country["has_sea"] == 1 and has("sea"))
    air_ok = bool(d_country and has("air") and (has_carrier or base_near or same_region))
    land_ok = bool(d_country and (same_region or base_near) and (has("land") or has_soldiers))
    missile_ok = bool(d_country and has_missile)
    space_ok = bool(d_country and has("space"))
    ok = {"sea": sea_ok, "air": air_ok, "land": land_ok,
          "missile": missile_ok, "space": space_ok,
          "mixed": sum([sea_ok, air_ok, land_ok, missile_ok, space_ok]) >= 2}

    reason = {}
    if not sea_ok:
        reason["sea"] = ("کشور هدف دریا ندارد" if not (d_country and d_country["has_sea"]) else
                         "نیروی دریایی (قایق/ناو/زیردریایی) ندارید")
    if not air_ok:
        reason["air"] = ("تجهیزات هوایی ندارید" if not has("air") else
                         "بدون ناو هواپیمابر باید هم‌منطقه باشید یا پایگاه نزدیک داشته باشید")
    if not land_ok:
        reason["land"] = ("هم‌منطقه نیستید و پایگاه نزدیک ندارید" if not (same_region or base_near) else
                          "تجهیزات زمینی یا سرباز ندارید")
    if not missile_ok:
        reason["missile"] = "سلاح موشکی ندارید (از 🎖 پادگان → 🚀 موشکی بخرید)"
    if not space_ok:
        reason["space"] = "تسلیحات فضایی ندارید (فقط با سکه شاهی)"
    if not ok["mixed"]:
        reason["mixed"] = "برای حمله ترکیبی باید حداقل دو نوع حمله ممکن داشته باشید"
    return ok, reason


@router.callback_query(F.data.startswith("g|watkc|"))
async def attack_type(call: CallbackQuery, state: FSMContext):
    war_id = int(call.data.split("|")[2])
    war = await db.fetchone("SELECT * FROM wars WHERE id=? AND attacker_id=? AND status='active'",
                            (war_id, call.from_user.id))
    if not war:
        return await call.answer("جنگ فعال نیست", show_alert=True)
    d_country = await get_country(war["defender_id"])
    if not d_country:
        return await call.answer("کشور مدافع یافت نشد", show_alert=True)
    ok, reason = await _attack_options(call.from_user.id, war["defender_id"])

    lines = [f"🎯 حمله به {d_country['flag']} <b>{d_country['name']}</b>\n"]
    for key, title in ATTACK_TYPES.items():
        lines.append(f"{'✅' if ok[key] else '❌'} {title} — {ATTACK_RULES[key]}")
        if not ok[key] and reason.get(key):
            lines.append(f"     ↳ {reason[key]}")
    if not any(ok.values()):
        lines.append("\n💡 هیچ‌کدام از روش‌های حمله ممکن نیست. از 🎖 پادگان تجهیزات/سرباز بخرید "
                     "یا با کشوری هم‌منطقه بجنگید.")
    rows = []
    for key, title in ATTACK_TYPES.items():
        rows.append([(f"{'✅' if ok[key] else '❌'} {title}", f"g|wtype|{war_id}|{key}")])
    rows.append(back_row("g|watk"))
    await state.update_data(plan={}, war_id=war_id)
    await call.answer()
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))
    except Exception:
        await call.message.answer("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|wtype|"))
async def attack_equipment(call: CallbackQuery, state: FSMContext):
    _, _, war_id, atype = call.data.split("|")
    war_id = int(war_id)
    war = await db.fetchone("SELECT * FROM wars WHERE id=? AND attacker_id=? AND status='active'",
                            (war_id, call.from_user.id))
    if not war:
        return await call.answer("جنگ فعال نیست", show_alert=True)
    ok, reason = await _attack_options(call.from_user.id, war["defender_id"])
    if not ok.get(atype):
        return await call.answer(f"⛔️ {ATTACK_TYPES.get(atype, atype)}: {reason.get(atype, 'امکان‌پذیر نیست')}",
                                 show_alert=True)
    await state.update_data(war_id=war_id, atype=atype, plan={})
    await _equip_picker(call, state, ATTACK_CATS[atype])


async def _equip_picker(call, state: FSMContext, allowed_cats: list, as_message: bool = False):
    """انتخاب نیروی حمله. اگر از یک پیام کاربر آمده باشیم، پیام تازه ساخته می‌شود."""
    data = await state.get_data()
    plan = data.get("plan", {})
    atype = data.get("atype", "mixed")
    placeholders = ",".join("?" * len(allowed_cats))
    my_equipment = await db.fetchall(
        "SELECT e.*, a.quantity, c.title AS cat_title, c.emoji AS cat_emoji, c.key AS cat_key "
        "FROM player_assets a JOIN equipment e ON e.id=a.item_id "
        "LEFT JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0 AND c.key IN (%s) "
        "ORDER BY c.id, e.id" % placeholders, (call.from_user.id, *allowed_cats))
    if atype == "missile":
        my_equipment = [e for e in my_equipment if _is_missile(e)]
    elif atype == "land":
        # راکت‌اندازها هم در حمله زمینی قابل استفاده‌اند
        extra = [e for e in await _my_equipment(call.from_user.id)
                 if _is_missile(e) and e["id"] not in {x["id"] for x in my_equipment}]
        my_equipment += extra
    soldiers = await db.fetchall(
        "SELECT s.*, a.quantity FROM player_assets a JOIN soldier_types s ON s.id=a.item_id "
        "WHERE a.user_id=? AND a.item_type='soldier' AND a.quantity>0", (call.from_user.id,))
    total_soldiers = sum(s["quantity"] for s in soldiers)

    lines = [f"🗡 <b>انتخاب نیروی حمله</b> — {ATTACK_TYPES.get(atype, atype)}\n"]
    if plan:
        lines.append("📦 <b>نیروهای انتخاب‌شده:</b>")
        eq_names = {e["id"]: f"{e['emoji']} {e['name']}" for e in my_equipment}
        for eid, qty in plan.items():
            lines.append(f"  {eq_names.get(int(eid), eid)} ×{fmt(qty)}")
        lines.append("")
    if my_equipment:
        lines.append("برای افزودن تجهیزات، روی آن بزنید و تعداد را بنویسید:")
    else:
        lines.append("⚠️ تجهیز مناسب این نوع حمله ندارید — می‌توانید فقط با سربازان حمله کنید."
                     if total_soldiers else
                     "❌ تجهیز مناسب ندارید! اول از 🎖 پادگان خرید کنید.")
    if total_soldiers:
        lines.append(f"\n🪖 <b>{fmt(total_soldiers)} سرباز</b> به‌طور خودکار در نبرد شرکت می‌کنند.")

    rows = [[(f"{e['emoji']} {e['name']} (موجود {fmt(e['quantity'])})",
              f"g|weq|{e['id']}")] for e in my_equipment]
    if plan or total_soldiers:
        rows.append([("⚔️ حمله!", "g|wgo")])
    war_id = data.get("war_id")
    if war_id:
        rows.append(back_row(f"g|watkc|{war_id}", "◀️ بازگشت به انواع حمله"))
    rows.append(back_row("g|war"))
    text = "\n".join(lines)
    if as_message:
        await send_home(call.message, text, reply_markup=kb(rows))
    else:
        await call.answer()
        try:
            await call.message.edit_text(text, reply_markup=kb(rows))
        except Exception:
            await send_home(call.message, text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|weq|"))
async def attack_eq_qty(call: CallbackQuery, state: FSMContext):
    eid = int(call.data.split("|")[2])
    e = await db.fetchone(
        "SELECT e.*, a.quantity FROM equipment e JOIN player_assets a ON a.item_id=e.id AND a.user_id=? "
        "AND a.item_type='equipment' WHERE e.id=?", (call.from_user.id, eid))
    if not e:
        return await call.answer("یافت نشد", show_alert=True)
    await state.set_state(WarFSM.atk_qty)
    await state.update_data(eq_id=eid)
    await call.answer()
    await call.message.edit_text(
        f"{e['emoji']} <b>{e['name']}</b> — موجود: {fmt(e['quantity'])} (سرعت ⚡{e['speed']})\n\n"
        "تعداد برای اعزام را بنویسید:\n برای انصراف /cancel"
    )


@router.message(WarFSM.atk_qty)
async def attack_qty_input(message: Message, state: FSMContext):
    try:
        qty = int((message.text or "").strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد بفرستید.")
    data = await state.get_data()
    e = await db.fetchone(
        "SELECT e.*, a.quantity FROM equipment e JOIN player_assets a ON a.item_id=e.id AND a.user_id=? "
        "AND a.item_type='equipment' WHERE e.id=?", (message.from_user.id, data.get("eq_id", 0)))
    if not e or qty <= 0 or qty > e["quantity"]:
        return await send_home(message, f"❌ عدد باید بین ۱ تا {fmt(e['quantity'] if e else 0)} باشد.")
    plan = data.get("plan", {})
    plan[str(data["eq_id"])] = qty
    await state.set_state(None)
    await state.update_data(plan=plan)
    # پیام تازه ارسال می‌شود (پیام کاربر قابل ویرایش نیست)
    await _equip_picker(_MessageCall(message), state, ATTACK_CATS.get(data.get("atype", "mixed"),
                                                                      ["land"]), as_message=True)


class _MessageCall:
    """پوشش سبک برای استفاده از منطق picker روی یک پیام ورودی کاربر."""

    def __init__(self, message: Message):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot

    async def answer(self, *_a, **_k):
        pass


@router.callback_query(F.data == "g|wgo")
async def attack_go(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    plan = data.get("plan", {})
    war = await db.fetchone("SELECT * FROM wars WHERE id=? AND attacker_id=? AND status='active'",
                            (data.get("war_id"), call.from_user.id))
    if not war:
        await state.clear()
        return await call.answer("جنگ فعال نیست — اول اعلان جنگ بدهید", show_alert=True)
    soldiers = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
        (call.from_user.id,))
    if not plan and not (soldiers and soldiers["c"] > 0):
        return await call.answer("❌ نیرویی برای حمله انتخاب نکرده‌اید!", show_alert=True)
    atype = data.get("atype", "mixed")
    await state.clear()
    await resolve_battle(call, war, plan, atype)


async def resolve_battle(call, war: dict, plan: dict, atype: str):
    attacker_id, defender_id = war["attacker_id"], war["defender_id"]
    a_country = await get_country(attacker_id)
    d_country = await get_country(defender_id)
    if not a_country or not d_country:
        return await call.answer("❌ کشور مهاجم یا مدافع یافت نشد", show_alert=True)
    plan = {str(k): int(v) for k, v in (plan or {}).items() if int(v) > 0}

    # قدرت مهاجم
    atk_power = 0.0
    for eid, qty in plan.items():
        e = await db.fetchone("SELECT * FROM equipment WHERE id=?", (int(eid),))
        if e:
            atk_power += qty * (e["attack_power"] or 0) * (0.5 + (e["speed"] or 3) / 10)
    for s in await db.fetchall(
            "SELECT s.power, a.quantity FROM player_assets a JOIN soldier_types s ON s.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='soldier'", (attacker_id,)):
        atk_power += s["power"] * s["quantity"]
    a_atk, _a_def, _ = await army_power(attacker_id)
    atk_power += a_atk * 0.1
    if await has_project_named(attacker_id, "ویروس"):
        atk_power *= 1.25  # سلاح زیستی
    if await has_project_named(attacker_id, "هوش مصنوعی"):
        atk_power *= 1.10
    if atype == "missile":
        atk_power *= 1.15  # ضربه موشکی غافلگیرکننده

    # قدرت مدافع
    d_def = 0.0
    for e in await db.fetchall(
            "SELECT e.*, a.quantity FROM player_assets a JOIN equipment e ON e.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='equipment'", (defender_id,)):
        d_def += (e["defense_power"] or 0) * e["quantity"]
    for s in await db.fetchall(
            "SELECT s.power, a.quantity FROM player_assets a JOIN soldier_types s ON s.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='soldier'", (defender_id,)):
        d_def += s["power"] * s["quantity"] * 0.8
    _da, d_army_def, _ = await army_power(defender_id)
    d_def += d_army_def * 0.15 + (d_country["population"] or 1) / 200_000
    if await has_project_named(defender_id, "واکسن"):
        atk_power *= 0.75  # واکسن در برابر ویروس
    # 🤝 پیمان نظامی: متحدان مدافع در جبهه او می‌جنگند (۳۰٪ توانشان به دفاع اضافه می‌شود)
    from core.treaties import pact_allies
    for ally in await pact_allies(defender_id):
        if ally == attacker_id:
            continue
        _aa, _ad, _ = await army_power(ally)
        d_def += (_aa + _ad) * 0.3
        try:
            await dm(call.bot, 
                ally, f"⚔️ طبق پیمان نظامی، شما در دفاع از {d_country['name']} جنگیدید!")
        except Exception:
            pass

    # محاسبه سامانه‌های پدافندی و موشکی مدافع
    def_air_defense_power = 0.0
    def_equipment_list = await db.fetchall(
        "SELECT e.*, a.quantity FROM player_assets a JOIN equipment e ON e.id=a.item_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0", (defender_id,))
    for e in def_equipment_list:
        subcat = (e.get("subcategory") or "").lower()
        ename = e.get("name") or ""
        if subcat == "air_defense" or "پدافند" in ename or "پاتریوت" in ename or "اس ۴۰۰" in ename or "تور ام" in ename:
            def_air_defense_power += (e["defense_power"] or 0) * e["quantity"]

    # بررسی تسلیحات موشکی و پرتابه‌های مهاجم
    missile_power = 0.0
    for eid, qty in plan.items():
        e = await db.fetchone("SELECT * FROM equipment WHERE id=?", (int(eid),))
        if e:
            ename = e.get("name") or ""
            subcat = (e.get("subcategory") or "").lower()
            if "موشک" in ename or "راکت" in ename or subcat in ("artillery", "space_weapon") or "هایمارس" in ename:
                missile_power += qty * (e["attack_power"] or 0)

    # سیستم رهگیری موشکی توسط سامانه‌های پدافندی (پاتریوت، اس ۴۰۰، تور ام۱)
    intercepted_missiles = False
    intercept_rate = 0.0
    if missile_power > 0 and def_air_defense_power > 0:
        intercept_rate = clamp(def_air_defense_power / (missile_power * 1.2), 0.15, 0.90)
        # کاهش توان موشکی مهاجم بر اثر پدافند هوایی موثر
        missile_damage_blocked = missile_power * intercept_rate
        atk_power = max(10.0, atk_power - missile_damage_blocked)
        intercepted_missiles = True

    chance = clamp(atk_power / (atk_power + d_def), 0.05, 0.95) if (atk_power + d_def) > 0 else 0.5
    won = random.random() < chance

    # تلفات و غارت
    defender_user = await db.fetchone("SELECT * FROM users WHERE id=?", (defender_id,)) or {"money": 0}
    loot = 0
    if won:
        loot = int((defender_user["money"] or 0) * 0.10)
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (loot, defender_id))
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (loot, attacker_id))
        def_loss, atk_loss = 0.30, 0.15
    else:
        def_loss, atk_loss = 0.10, 0.40

    # محاسبه و کسر تلفات تجهیزات مهاجم با نام
    atk_destroyed_names = []
    for eid, qty in plan.items():
        lost_count = max(1, int(qty * atk_loss))
        if not await sub_asset(attacker_id, "equipment", int(eid), lost_count):
            continue
        eq_info = await db.fetchone("SELECT name, emoji FROM equipment WHERE id=?", (int(eid),))
        if eq_info:
            atk_destroyed_names.append(f"{lost_count}× {eq_info['emoji']} {eq_info['name']}")

    # محاسبه و کسر تلفات تجهیزات مدافع با نام
    def_destroyed_names = []
    for e in def_equipment_list:
        row = await db.fetchone("SELECT quantity FROM player_assets WHERE user_id=? AND item_id=? AND item_type='equipment'",
                                (defender_id, e["id"]))
        if row and row["quantity"] > 0:
            lost_count = max(1, int(row["quantity"] * def_loss))
            await sub_asset(defender_id, "equipment", e["id"], lost_count)
            def_destroyed_names.append(f"{lost_count}× {e['emoji']} {e['name']}")

    # آسیب به زیرساخت‌ها در صورت برخورد موشک
    infrastructure_damage = ""
    if won and (missile_power > 0 or atype in ("air", "space", "mixed")):
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-4) WHERE user_id=?", (defender_id,))
        infrastructure_damage = "💥 <b>تخریب زیرساخت‌ها:</b> اصابت موشک‌ها و آتشباری هوایی به مراکز صنعتی (-۴٪ رضایت ملی دشمن)\n"

    await db.execute(
        "INSERT INTO battles(war_id, attacker_id, defender_id, atk_type, atk_power, def_power, result, loot) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (war["id"], attacker_id, defender_id, atype, round(atk_power), round(d_def),
         "win" if won else "lose", loot))
    await bump_progress(attacker_id, "war")
    await bump_progress(defender_id, "war")

    atype_fa = ATTACK_TYPES.get(atype, atype)
    
    # ساخت گزارش کامل عملیات نظامی با پدافند و تلفات
    report_lines = [
        f"⚔️ <b>گزارش نبرد {atype_fa}</b>",
        f"طرفین: {a_country['flag']} <b>{a_country['name']}</b> ➔ {d_country['flag']} <b>{d_country['name']}</b>\n",
        f"🗡 توان عملیاتی تهاجم: <b>{fmt(atk_power)}</b>",
        f"🛡 استحکامات و توان پدافندی: <b>{fmt(d_def)}</b>",
    ]

    if intercepted_missiles:
        report_lines.append(
            f"🛡️ <b>عملکرد پدافند هوایی مدافع:</b> سامانه‌های پدافندی {round(intercept_rate * 100)}٪ از موشک‌ها و راکت‌های شلیک‌شده را در آسمان منهدم و رهگیری کردند!"
        )
    elif missile_power > 0:
        report_lines.append(
            "🚀 <b>تخریب موشکی:</b> مدافع فاقد پوشش پدافندی موثر بود؛ موشک‌ها مستقیماً به اهداف اصابت کردند!"
        )

    report_lines.append(f"🎲 شانس موفقیت ارتش: <b>{round(chance * 100)}%</b>\n")

    if won:
        report_lines.append(f"🏆 <b>پیروزی قاطع نیروهای {a_country['name']}!</b>")
        report_lines.append(f"💰 غارت خزانه: <b>{fmt_money(loot)}</b> پول ملی")
    else:
        report_lines.append(f"🛡 <b>مدافعان {d_country['name']} حمله را دفع کردند!</b>")

    if infrastructure_damage:
        report_lines.append(infrastructure_damage.strip())

    report_lines.append("\n💥 <b>تلفات و خسارات وارده:</b>")
    if def_destroyed_names:
        report_lines.append(f"• ادوات منهدم‌شده مدافع ({round(def_loss * 100)}%):\n   " + " ، ".join(def_destroyed_names[:5]))
    else:
        report_lines.append("• مدافع تجهیزی در منطقه نداشت.")

    if atk_destroyed_names:
        report_lines.append(f"• ادوات منهدم‌شده مهاجم ({round(atk_loss * 100)}%):\n   " + " ، ".join(atk_destroyed_names[:5]))

    result_text = "\n".join(report_lines)
    await announce(call.bot, result_text, section="war_attack")
    await call.answer()
    try:
        await call.message.edit_text(result_text, reply_markup=kb([back_row("g|war")]))
    except Exception:
        await call.message.answer(result_text, reply_markup=kb([back_row("g|war")]))
    try:
        await dm(call.bot, defender_id, result_text)
    except Exception:
        pass


# ─── سایبری ───


@router.callback_query(F.data == "g|wcyb")
async def cyber_enemy_list(call: CallbackQuery):
    if await is_leader_blocked(call.from_user.id):
        return await call.answer("🚫 رهبر شما ترور شده!", show_alert=True)
    countries = await enemy_countries(call.from_user.id)
    rows = [[(f"{c['flag']} {c['name']}", f"g|wcyb|{c['owner_uid']}")] for c in countries]
    rows.append(back_row("g|war"))
    await call.answer()
    await call.message.edit_text(
        "🕶 <b>عملیات سایبری (مخفیانه)</b>\n\nکشور هدف را انتخاب کنید.\n"
        "💡 شانس موفقیت: قدرت برابر = ۵۰٪ • دو برابر = ۹۵٪ • نصفِ دشمن = ۲۵٪.\n"
        "🖥 قدرت سایبری از تجهیزات سایبری (پادگان → 💻 سایبری) و سربازها می‌آید.",
        reply_markup=kb(rows),
    )


async def cyber_cooldown_ok(attacker_id: int, defender_id: int) -> bool:
    hours = float(await get_setting("cyber_cooldown_hours", "6"))
    last = await db.fetchone(
        "SELECT created_at FROM cyber_ops WHERE attacker_id=? AND defender_id=? ORDER BY id DESC LIMIT 1",
        (attacker_id, defender_id))
    if last and hours_left(last["created_at"]) < hours:
        return False
    return True


def cyber_chance(my_cyber: int, their_cyber: int) -> float:
    """شانس موفقیت سایبری بر اساس نسبت قدرت دو کشور.

    قدرت برابر → ۵۰٪ | دو برابر → ۹۵٪ | نصف → ۲۵٪ | یک‌چهارم → ۱۲٪
    (قبلاً با قدرت برابر شانس فقط ۵٪ بود و عملاً هیچ عملیات سایبری موفق نمی‌شد.)
    """
    my = max(1, int(my_cyber or 0))
    their = max(1, int(their_cyber or 0))
    ratio = my / their
    return clamp(50 * ratio, 5, 95)


@router.callback_query(F.data.startswith("g|wcyb|"))
async def cyber_ops_menu(call: CallbackQuery):
    defender_id = int(call.data.split("|")[2])
    if not await cyber_cooldown_ok(call.from_user.id, defender_id):
        return await call.answer("⏳ هر ۶ ساعت یک عملیات سایبری روی هر کشور", show_alert=True)
    d_country = await get_country(defender_id)
    _a, _d, my_cyber = await army_power(call.from_user.id)
    _a2, _d2, their_cyber = await army_power(defender_id)
    chance = cyber_chance(my_cyber, their_cyber)
    await call.answer()
    await call.message.edit_text(
        f"🕶 <b>عملیات سایبری علیه {d_country['flag']} {d_country['name']}</b>\n\n"
        f"🖥 قدرت سایبری شما: {fmt(my_cyber)}\n🖥 قدرت سایبری دشمن: {fmt(their_cyber)}\n"
        f"🎲 شانس موفقیت پایه: <b>{round(chance)}%</b>\n\nعملیات را انتخاب کنید:",
        reply_markup=kb([
            [("🎯 ترور رهبر (۱ ساعت فلج)", f"g|cy|assass|{defender_id}")],
            [("💸 دزدی از خزانه", f"g|cy|steal|{defender_id}")],
            [("📡 تداخل در سرور دشمن (۲ ساعت)", f"g|cy|jam|{defender_id}")],
            back_row("g|war"),
        ]),
    )


@router.callback_query(F.data.startswith("g|cy|"))
async def cyber_execute(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("|")
    if len(parts) < 4:
        return await call.answer("درخواست نامعتبر است", show_alert=True)
    op, defender_id = parts[2], int(parts[3])
    if not await cyber_cooldown_ok(call.from_user.id, defender_id):
        return await call.answer("⏳ هنوز زمان cooldown تمام نشده", show_alert=True)
    if op == "steal":
        await state.set_state(WarFSM.steal_amount)
        await state.update_data(defender_id=defender_id)
        victim = await db.fetchone("SELECT * FROM users WHERE id=?", (defender_id,))
        treasury = victim["money"]
        await call.answer()
        return await call.message.edit_text(
            f"💸 <b>دزدی از خزانه</b>\n\n💰 خزانه دشمن: <b>{fmt_money(treasury)}</b>\n\n"
            "چه مقدار می‌خواهید بدزدید؟ هرچه عدد بزرگ‌تر باشد شانس موفقیت کمتر است:\n برای انصراف /cancel"
        )
    _a, _d, my_cyber = await army_power(call.from_user.id)
    _a2, _d2, their_cyber = await army_power(defender_id)
    chance = cyber_chance(my_cyber, their_cyber)
    success = random.random() * 100 < chance
    d_country = await get_country(defender_id)
    await db.execute(
        "INSERT INTO cyber_ops(attacker_id, defender_id, kind, success) VALUES(?,?,?,?)",
        (call.from_user.id, defender_id, op, 1 if success else 0))
    if op == "assass":
        if success:
            await db.execute("UPDATE states SET leader_block_until=? WHERE user_id=?",
                             (add_hours(1), defender_id))
            msg = (f"🎯 ترور رهبر {d_country['flag']} {d_country['name']} <b>موفق</b> بود!\n"
                   "کشور دشمن ۱ ساعت نمی‌تواند حمله و دیپلماسی انجام دهد.")
            try:
                await dm(call.bot, defender_id, "🚫 رهبر شما ترور شد! ۱ ساعت حمله و دیپلماسی مسدود است.")
            except Exception:
                pass
        else:
            msg = "❌ عملیات ترور ناموفق بود — ردپای شما شناسایی شد!"
    else:  # jam
        if success:
            await db.execute("UPDATE states SET server_jam_until=? WHERE user_id=?",
                             (add_hours(2), defender_id))
            msg = (f"📡 تداخل در سرور {d_country['flag']} {d_country['name']} <b>موفق</b>!\n"
                   "کشور دشمن ۲ ساعت فقط می‌تواند بیانیه صادر کند.")
            try:
                await dm(call.bot, defender_id,
                                            "📡 سرورهای شما دچار اختلال شد! ۲ ساعت فقط بیانیه مجاز است.")
            except Exception:
                pass
        else:
            msg = "❌ عملیات اختلال سرور ناموفق بود!"
    await announce(call.bot, f"🕶 گزارش محرمانه: عملیات سایبری علیه {d_country['name']} انجام شد.",
                   section="cyber")
    await call.answer()
    await call.message.edit_text(msg, reply_markup=kb([back_row("g|war")]))


@router.message(WarFSM.steal_amount)
async def steal_input(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد بفرستید.")
    if amount <= 0:
        return await send_home(message, "❌ عدد باید مثبت باشد.")
    data = await state.get_data()
    defender_id = data["defender_id"]
    victim = await db.fetchone("SELECT * FROM users WHERE id=?", (defender_id,))
    if amount > victim["money"]:
        return await send_home(message, f"❌ خزانه دشمن فقط {fmt_money(victim['money'])} دارد.")
    await state.clear()
    _a, _d, my_cyber = await army_power(message.from_user.id)
    _a2, _d2, their_cyber = await army_power(defender_id)
    base = cyber_chance(my_cyber, their_cyber)
    chance = clamp(base * (0.5 * victim["money"]) / amount, 5, 95)
    success = random.random() * 100 < chance
    d_country = await get_country(defender_id)
    await db.execute(
        "INSERT INTO cyber_ops(attacker_id, defender_id, kind, success, amount) VALUES(?,?,?,?,?)",
        (message.from_user.id, defender_id, "steal", 1 if success else 0, amount if success else 0))
    if success:
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (amount, defender_id))
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (amount, message.from_user.id))
        msg = (f"💸 دزدی از خزانه {d_country['flag']} {d_country['name']} <b>موفق</b>!\n"
               f"💰 {fmt(amount)} به خزانه شما اضافه شد. (شانس: {round(chance)}%)")
        try:
            await dm(message.bot, defender_id, f"💸 هکری از خزانه شما {fmt(amount)} دزدیده شد!")
        except Exception:
            pass
    else:
        msg = f"❌ دزدی ناموفق بود! (شانس: {round(chance)}%)"
    from gamebot.common import kb
    await send_home(message, msg, reply_markup=kb([back_row("g|war")]))


# ─── بستن رای‌گیری‌های تمام‌شده ───


async def settle_votes(bot=None) -> None:
    """پایان رای‌گیری‌های سازمان ملل و اعمال نتیجه."""
    votes = await db.fetchall(
        "SELECT * FROM un_votes WHERE status='open' AND ends_at<=?", (iso(),))
    for v in votes:
        ballots = await db.fetchall("SELECT * FROM un_ballots WHERE vote_id=?", (v["id"],))
        tally = {}
        for b in ballots:
            tally[b["choice"]] = tally.get(b["choice"], 0) + b["weight"]
        await db.execute("UPDATE un_votes SET status='closed' WHERE id=?", (v["id"],))
        if v["kind"] == "war":
            yes = tally.get(0, 0)
            no = tally.get(1, 0)
            war = await db.fetchone("SELECT * FROM wars WHERE id=?", (v["subject_id"],))
            if war:
                # اگر هیچ کشوری رأی نداده باشد، مجوز به‌صورت خودکار صادر می‌شود
                auto = (yes + no) == 0
                if yes >= no:
                    await db.execute("UPDATE wars SET status='active' WHERE id=?", (war["id"],))
                    try:
                        from core.rescue import ensure_campaign
                        await ensure_campaign(war["id"])
                    except Exception:
                        pass
                    if bot:
                        try:
                            await dm(bot, war["attacker_id"],
                                     "🗳 سازمان ملل جنگ شما را تأیید کرد! حمله آزاد است."
                                     + ("\n(هیچ کشوری رأی نداد، بنابراین مجوز خودکار صادر شد.)" if auto else ""))
                            await dm(bot, war["defender_id"], "🗳 سازمان ملل به جنگ علیه شما مجوز داد!")
                        except Exception:
                            pass
                        if auto:
                            try:
                                await announce(bot, "🗳 سازمان ملل: هیچ رأیی در رای‌گیری مجوز جنگ ثبت نشد "
                                                    "و مجوز به‌صورت خودکار صادر شد.", section="un")
                            except Exception:
                                pass
                else:
                    await db.execute("UPDATE wars SET status='rejected' WHERE id=?", (war["id"],))
                    if bot:
                        try:
                            await dm(bot, war["attacker_id"],
                                     "🗳 سازمان ملل مجوز جنگ شما را رد کرد. می‌توانید دوباره "
                                     "«بدون مجوز» اعلان جنگ بدهید (ریسک ثبت جنایت جنگی).")
                        except Exception:
                            pass
        elif v["kind"] == "crime":
            crime_votes = tally.get(0, 0)
            not_crime = tally.get(1, 0)
            if crime_votes > not_crime:
                await db.execute("UPDATE wars SET war_crime=1 WHERE id=?", (v["subject_id"],))
        elif v["kind"] == "sanction":
            yes, no = tally.get(0, 0), tally.get(1, 0)
            if yes > no and v["subject_id"]:
                # subject_id = user_id هدف
                target = v["subject_id"]
                if v["title"].startswith("خلع سلاح"):
                    await db.execute("UPDATE states SET disarmed_until=? WHERE user_id=?",
                                     (add_hours(24 * 7), target))
                elif v["title"].startswith("لغو تجارت"):
                    await db.execute("UPDATE states SET trade_banned='[\"all\"]' WHERE user_id=?", (target,))
                elif v["title"].startswith("برکناری"):
                    await db.execute("UPDATE states SET leader_block_until=? WHERE user_id=?",
                                     (add_hours(24), target))

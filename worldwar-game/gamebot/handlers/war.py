"""اتاق جنگ: اعلان جنگ (با/بدون مجوز)، حمله (۶ نوع) و عملیات سایبری."""
import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting, set_setting
from core.economy import (announce, army_power, bump_progress, get_country,
                          get_state, has_project_named, is_disarmed,
                          is_jammed, is_leader_blocked, sub_asset, veto_users)
from core.utils import (fmt, fmt_money, add_hours, iso, hours_left, hours_ago, fmt_hm,
                        jloads, clamp)
from gamebot.common import back_row, blocked_banner, kb, send_home, dm

router = Router()

ATTACK_TYPES = {"sea": "⚓ دریایی", "air": "✈️ هوایی", "land": "🪖 زمینی",
                "missile": "🚀 موشکی", "space": "🛰️ فضایی", "mixed": "🔀 ترکیبی",
                "conquest": "⚔️ حمله به قصد تسخیر"}

CONQUEST_FORCE = "mixed"       # حملهٔ تسخیر از همهٔ نیروها استفاده می‌کند

ATTACK_CATS = {"sea": ["sea"], "air": ["air"], "land": ["land"],
               "missile": ["missile", "land"], "space": ["space"],
               "mixed": ["sea", "air", "land", "missile", "space"]}
ATTACK_CATS["conquest"] = ["sea", "air", "land", "missile", "space"]

ATTACK_RULES = {
    "sea": "کشور هدف باید دریا داشته باشد و شما نیروی دریایی داشته باشید",
    "air": "نیاز به تجهیزات هوایی + ناو هواپیمابر، پایگاه نزدیک یا هم‌منطقه بودن",
    "land": "هم‌منطقه بودن یا پایگاه در منطقه هدف + تجهیزات زمینی یا سرباز",
    "missile": "از هر فاصله‌ای — نیاز به موشک (کروز/بالستیک/ضدکشتی/راکت‌انداز)",
    "space": "از هرجای دنیا — فقط با تسلیحات فضایی",
    "mixed": "ترکیب دو یا چند نوع حمله",
    "conquest": "🏴 با پیروزی، یک استان از مدافع جدا و به شما اضافه می‌شود "
                "(حملهٔ عادی استان نمی‌گیرد)",
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
            # ⛓ میزان فرسایش طرف مقابل — بازیکن می‌بیند چقدر دشمن را در هم شکسته
            try:
                from core import attrition as _attr
                foe = w["defender_id"] if w["attacker_id"] == call.from_user.id else w["attacker_id"]
                foe_wear = (await _attr.get(foe))["wear"]
                if foe_wear > 0:
                    status += f" | ⛓ فرسایش دشمن {foe_wear}٪"
            except Exception:
                pass
            crime = " | ⚠️ جنایت جنگی" if w["war_crime"] else ""
            lines.append(
                f"{role} علیه {w['def_flag'] if w['attacker_id'] == call.from_user.id else w['atk_flag']} "
                f"{w['def_name'] if w['attacker_id'] == call.from_user.id else w['atk_name']} — {status}{crime}")
    else:
        lines.append("در حال حاضر در جنگی نیستید.")
    lines += ["\n" + blocked_banner(state)]
    # ⛓ وضعیت فرسایش کشور خودم (اگر در جنگ کوبیده شده‌ام)
    try:
        from core import attrition as _attr
        my_wear = await _attr.wear_line(call.from_user.id)
        if my_wear:
            lines.append("\n" + my_wear)
        else:
            lines.append("\n⛓ <b>امنیت کشور:</b> هیچ فرسایشی ندارید — زیرساخت‌ها سالم‌اند.")
    except Exception:
        pass
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("📢 اعلان جنگ", "g|wdec")],
        [("🗡 حمله (عادی / تسخیر)", "g|watk")],
        [("☢️ هدف قرار دادن تأسیسات هسته‌ای", "g|nuk")],
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
        "SELECT c.*, u.id AS player_id, '' AS full_name FROM users u "
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
    from core import attrition as _attr
    rows = []
    for c in countries:
        try:
            wear = (await _attr.get(c["owner_uid"]))["wear"]
        except Exception:
            wear = 0
        tag = f" ⛓{wear}٪" if wear > 0 else ""
        rows.append([(f"{c['flag']} {c['name']}{tag}", f"g|wdec|{c['owner_uid']}")])
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
    from core import attrition as _attr
    rows = []
    for w in wars:
        try:
            wear = (await _attr.get(w["defender_id"]))["wear"]
        except Exception:
            wear = 0
        tag = f" ⛓ فرسایش {wear}٪" if wear > 0 else ""
        rows.append([(f"🎯 {w['def_flag']} {w['def_name']}{tag}", f"g|watkc|{w['id']}")])
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
          "mixed": sum([sea_ok, air_ok, land_ok, missile_ok, space_ok]) >= 2,
          # تسخیر: با هر نیرویی که حمله را ممکن کند (دریایی/هوایی/زمینی/ترکیبی)
          "conquest": any([sea_ok, air_ok, land_ok]) or
                      sum([sea_ok, air_ok, land_ok, missile_ok, space_ok]) >= 2}

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
    if not ok["conquest"]:
        reason["conquest"] = ("برای تسخیر باید حملهٔ دریایی، هوایی یا زمینی ممکن باشد "
                              "(تجهیزات/سرباز و دسترسی به کشور هدف)")
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

    prov = await db.fetchone(
        "SELECT COUNT(*) c FROM provinces WHERE owner_id=?", (war["defender_id"],))
    lines = [f"🎯 حمله به {d_country['flag']} <b>{d_country['name']}</b>\n",
             "🅰️ <b>حملهٔ عادی</b> — فقط زیرساخت‌ها را می‌زند (رضایت، منابع، پدافند). "
             "استان نمی‌گیرد.",
             "🅱️ <b>حملهٔ تسخیر</b> — با پیروزی یک استان از دشمن جدا می‌شود و غارت ۲۰٪ بیشتر "
             f"است.\n🗺 استان‌های مدافع: <b>{fmt((prov or {}).get('c') or 0)}</b>\n"]
    for key, title in ATTACK_TYPES.items():
        prefix = "⚔️" if key == "conquest" else ("✅" if ok[key] else "❌")
        lines.append(f"{prefix} {title} — {ATTACK_RULES[key]}")
        if not ok[key] and reason.get(key):
            lines.append(f"     ↳ {reason[key]}")
    if not any(ok.values()):
        lines.append("\n💡 هیچ‌کدام از روش‌های حمله ممکن نیست. از 🎖 پادگان تجهیزات/سرباز بخرید "
                     "یا با کشوری هم‌منطقه بجنگید.")
    rows = []
    for key, title in ATTACK_TYPES.items():
        mark = "⚔️" if key == "conquest" else ("✅" if ok[key] else "❌")
        rows.append([(f"{mark} {title}", f"g|wtype|{war_id}|{key}")])
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
    lines.append("\n🧠 <b>استراتژی حمله</b> هنگام اجرا بر اساس ترکیب نیروهای اعزامی (زیردریایی/ناو/"
                 "سرباز/هوایی/موشکی) انتخاب می‌شود و همراه خسارات دو طرف در کانال اعلام می‌گردد.")

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


async def attack_cooldown_state(user_id: int) -> tuple[bool, int, str]:
    """آیا بازیکن می‌تواند حمله کند؟ → (آماده، ثانیه باقی‌مانده، متن خطا)"""
    minutes = 3.0
    try:
        minutes = max(0.0, float(await get_setting("attack_cooldown_minutes", "3")))
    except (TypeError, ValueError):
        minutes = 3.0
    if minutes <= 0:
        return True, 0, ""
    row = await db.fetchone("SELECT last_attack_at FROM states WHERE user_id=?", (user_id,))
    last = (row or {}).get("last_attack_at")
    if not last:
        return True, 0, ""
    from core.utils import now as _now, parse as _parse
    try:
        then = _parse(last)
        if then is None:
            return True, 0, ""
        elapsed = (_now() - then).total_seconds()
    except Exception:
        return True, 0, ""
    remaining = int(minutes * 60 - elapsed)
    if remaining <= 0:
        return True, 0, ""
    m, sec = divmod(remaining, 60)
    return False, remaining, (f"⏳ <b>نیروهای شما در حال بازسازی هستند</b>\n\n"
                              f"⏱ زمان باقی‌مانده: <b>{m}:{sec:02d}</b>\n"
                              "پس از این مدت می‌توانید دوباره حمله کنید.")


@router.callback_query(F.data == "g|wgo")
async def attack_confirm(call: CallbackQuery, state: FSMContext):
    """🛑 صفحهٔ تأیید نهایی حمله — نوع عملیات و نیروها یک‌بار دیگر نشان داده می‌شود."""
    ready, _remaining, _msg = await attack_cooldown_state(call.from_user.id)
    if not ready:
        return await call.answer("⏳ نیروها در حال بازسازی‌اند — کمی صبر کنید", show_alert=True)
    data = await state.get_data()
    plan = data.get("plan", {})
    atype = data.get("atype", "mixed")
    war = await db.fetchone("SELECT * FROM wars WHERE id=? AND attacker_id=? AND status='active'",
                            (data.get("war_id"), call.from_user.id))
    if not war:
        return await call.answer("جنگ فعال نیست — اول اعلان جنگ بدهید", show_alert=True)
    d_country = await get_country(war["defender_id"])
    conquest = atype == "conquest"
    prov = await db.fetchone("SELECT COUNT(*) c FROM provinces WHERE owner_id=?",
                             (war["defender_id"],))
    lines = [
        f"⚔️ <b>تأیید حمله به {d_country['flag']} {d_country['name']}</b>\n",
        f"🎯 نوع عملیات: <b>{ATTACK_TYPES.get(atype, atype)}</b>",
    ]
    if conquest:
        lines += [
            "🏴 <b>حمله به قصد تسخیر:</b> با پیروزی یک استان از دشمن جدا می‌شود "
            f"(مدافع الان {fmt((prov or {}).get('c') or 0)} استان دارد) و غارت ۲۰٪ بیشتر است.",
            "💥 اگر شکست بخورید، استان‌ها دست‌نخورده می‌مانند و شما تلفات می‌دهید.",
        ]
    else:
        lines += [
            "💥 <b>حملهٔ عادی:</b> زیرساخت‌ها (رضایت مردم، منابع، پدافند) آسیب می‌بینند "
            "اما <b>استانی گرفته نمی‌شود</b>.",
        ]
    if plan:
        eq_names = {}
        for eid in plan:
            e = await db.fetchone("SELECT emoji, name FROM equipment WHERE id=?", (int(eid),))
            if e:
                eq_names[eid] = f"{e['emoji']} {e['name']}"
        lines.append("\n📦 <b>نیروهای اعزامی:</b>")
        for eid, qty in list(plan.items())[:8]:
            lines.append(f"  {eq_names.get(eid, eid)} ×{fmt(qty)}")
    soldiers = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
        (call.from_user.id,))
    if soldiers and soldiers["c"]:
        lines.append(f"  🪖 {fmt(soldiers['c'])} سرباز")
    lines.append("\nآیا مطمئن هستید؟")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("✅ بله، حمله کن", "g|wgogo")],
        back_row("g|war", "🔴 انصراف"),
    ]))


@router.callback_query(F.data == "g|wgogo")
async def attack_go(call: CallbackQuery, state: FSMContext):
    ready, _remaining, msg = await attack_cooldown_state(call.from_user.id)
    if not ready:
        return await call.answer("⏳ نیروها در حال بازسازی‌اند — کمی صبر کنید", show_alert=True)
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
    from core import attrition as attr
    attacker_id, defender_id = war["attacker_id"], war["defender_id"]
    # ⚔️ «حمله به قصد تسخیر» یک حالت است نه یک نوع نیرو: نیروهای انتخاب‌شده
    # تعیین می‌کنند نبرد از چه طریقی انجام شود.
    conquest = atype == "conquest"
    if conquest:
        atype = CONQUEST_FORCE
    conquest = conquest or False
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

    # ─── استراتژی حمله بر اساس ترکیب واقعی نیروها ───
    from core import combat
    comp: dict = {}
    for eid, qty in plan.items():
        e = await db.fetchone(
            "SELECT e.subcategory AS sub, c.key AS cat_key FROM equipment e "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id WHERE e.id=?", (int(eid),))
        if e:
            key = e["cat_key"] or "land"
            if (e["sub"] or "").lower() == "submarine":
                key = "submarine"
            comp[key] = comp.get(key, 0) + qty
    my_soldiers = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
        (attacker_id,))
    if my_soldiers and my_soldiers["c"]:
        comp["soldier"] = int(my_soldiers["c"])
    strat = combat.pick_strategy(atype, comp, defender_has_navy=bool(def_equipment_list),
                                 allow_blockade=False)
    atk_power *= strat["atk"]
    d_def *= strat["def"]

    # ⛓ جنگ فرسایشی: کشور ضعیف‌شده بسیار راحت‌تر در هم می‌شکند
    wear_before = await attr.wear_of(defender_id)
    d_def *= await attr.defense_multiplier(defender_id)
    # 😞 روحیهٔ پایین مدافع، توان حمله مهاجم را هم بالا نمی‌برد ولی دفاع را می‌شکند
    if wear_before > 0:
        atk_power *= 1.0 + (wear_before / 100.0) * 0.25

    chance = combat.battle_chance(atk_power, d_def)
    won = random.random() < chance
    atk_loss, def_loss = combat.loss_ratios(chance, strat)

    # تلفات و غارت
    defender_user = await db.fetchone("SELECT * FROM users WHERE id=?", (defender_id,)) or {"money": 0}
    loot = 0
    if won:
        loot_pct = 0.10
        if conquest:
            # 💰 در حملهٔ تسخیر، غارت بیشتری نصیب مهاجم می‌شود
            loot_pct += float(await get_setting("conquest_loot_bonus", "20")) / 100 * 0.10
        loot = int((defender_user["money"] or 0) * loot_pct)
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (loot, defender_id))
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (loot, attacker_id))
    else:
        pass

    # ─── کسر تلفات واقعی از هر دو طرف (تجهیزات + سرباز) ───
    atk_rows = await combat.equipment_rows(attacker_id, only_ids=[int(i) for i in plan.keys()])
    atk_destroyed_names, atk_lost_units = await combat.apply_losses(
        attacker_id, atk_rows, atk_loss, "equipment")
    def_destroyed_names, def_lost_units = await combat.apply_losses(
        defender_id, def_equipment_list, def_loss * await attr.loss_multiplier(defender_id),
        "equipment")

    # سربازان دو طرف هم در نبرد کشته می‌شوند
    s_atk, s_atk_units = await combat.apply_soldier_losses(attacker_id, atk_loss * 0.7)
    if s_atk:
        atk_destroyed_names += s_atk
        atk_lost_units += s_atk_units
    s_def, s_def_units = await combat.apply_soldier_losses(
        defender_id, def_loss * 0.6 * await attr.loss_multiplier(defender_id))
    if s_def:
        def_destroyed_names += s_def
        def_lost_units += s_def_units

    # آسیب به زیرساخت‌ها در صورت برخورد موشک
    infrastructure_damage = ""
    if won and (missile_power > 0 or atype in ("air", "space", "mixed")):
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-4) WHERE user_id=?", (defender_id,))
        infrastructure_damage = "💥 <b>تخریب زیرساخت‌ها:</b> اصابت موشک‌ها و آتشباری هوایی به مراکز صنعتی (-۴٪ رضایت ملی دشمن)\n"

    await db.execute(
        "INSERT INTO battles(war_id, attacker_id, defender_id, atk_type, atk_power, def_power, result, loot, strategy) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (war["id"], attacker_id, defender_id, atype, round(atk_power), round(d_def),
         "win" if won else "lose", loot, strat["name"]))
    await bump_progress(attacker_id, "war")
    await bump_progress(defender_id, "war")

    atype_fa = ATTACK_TYPES.get(atype, atype)

    # ⛓ ثبت فرسایش و ریزش روحیه (اثر تجمعی حملات پشت‌سرهم)
    attrition_lines: list[str] = []
    try:
        res = await attr.apply_after_attack(attacker_id, defender_id, won)
        attrition_lines = res.get("lines") or []
    except Exception:
        log.exception("attrition apply failed")

    extra_lines = []
    extra_lines.extend(attrition_lines)
    if intercepted_missiles:
        extra_lines.append(
            f"🛡️ <b>پدافند هوایی مدافع:</b> {round(intercept_rate * 100)}٪ از موشک‌ها و راکت‌های شلیک‌شده "
            "در آسمان رهگیری و منهدم شدند.")
    elif missile_power > 0:
        extra_lines.append("🚀 <b>تخریب موشکی:</b> مدافع پوشش پدافندی موثر نداشت؛ موشک‌ها مستقیم اصابت کردند.")
    if won and loot:
        extra_lines.append(f"💰 غارت خزانه دشمن: <b>{fmt_money(loot)}</b>")
    if infrastructure_damage:
        extra_lines.append(infrastructure_damage.strip())
    if conquest:
        extra_lines.append("🏴 <b>حمله به قصد تسخیر:</b> با پیروزی، یک استان از دشمن جدا می‌شود "
                           "و غارت خزانه ۲۰٪ بیشتر است.")
    extra_lines.append(f"🎯 نوع عملیات: {atype_fa}" + (" (تسخیر)" if conquest else ""))

    # 🗺 استان‌ها و زیرساخت‌ها
    province_line = ""
    try:
        from core import provinces as prov
        if conquest:
            # ⚔️ فقط حملهٔ تسخیر استان می‌گیرد
            province_line = await prov.battle_province_effect(
                call.bot, attacker_id, defender_id,
                attacker_power=atk_power, defender_power=d_def,
                won=won, war_id=war.get("id"), conquest=True)
        elif won:
            # 💥 حملهٔ عادی فقط زیرساخت‌ها را می‌زند
            province_line = await prov.infrastructure_strike(
                call.bot, attacker_id, defender_id, atype, won,
                attacker_power=atk_power)
    except Exception:
        log.exception("province effect failed")
    if province_line:
        extra_lines.append(province_line.strip())

    # 🛡 کمک دفاعی متحدان (اتحاد)
    try:
        from core import alliances as al
        bonus = await al.defense_bonus(defender_id)
        if bonus["bonus"] > 0 and won:
            extra_lines.append(
                f"🤝 متحدان مدافع وارد شدند: {len(bonus['allies'])} متحد با "
                f"{bonus['percent']}٪ توان دفاعی")
    except Exception:
        pass

    # 📋 خلاصهٔ شفاف نتیجه برای کانال اطلاع‌رسانی
    if won:
        outcome = (f"🏆 <b>{a_country['name']} پیروز شد</b> — "
                   + ("یک استان از دشمن جدا شد." if conquest and "استان تصاحب شد" in province_line
                      else "زیرساخت‌های دشمن آسیب دید." if not conquest
                      else "اما پدافند دشمن استان را حفظ کرد."))
    else:
        outcome = f"🛡 <b>{d_country['name']} حمله را دفع کرد</b> — مالکیت و استان‌ها دست‌نخورده ماند."
    extra_lines.insert(0, outcome)


    result_text = combat.battle_report(
        strat=dict(strat, name=f"{strat['name']} ({atype_fa.strip()})"),
        atk_country=a_country, def_country=d_country,
        atk_power=atk_power, def_power=d_def, chance=chance, won=won,
        atk_losses=atk_destroyed_names, def_losses=def_destroyed_names,
        atk_units=atk_lost_units, def_units=def_lost_units,
        atk_ratio=atk_loss, def_ratio=def_loss,
        extra_lines=extra_lines, title=f"گزارش نبرد {atype_fa}")

    # ⏳ ثبت زمان حمله برای کول‌داون ۳ دقیقه‌ای
    try:
        await db.execute(
            "UPDATE states SET last_attack_at=? WHERE user_id=?", (iso(), attacker_id))
    except Exception:
        pass

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


async def cyber_cooldown_left(attacker_id: int, defender_id: int) -> int:
    """چند دقیقه تا آزاد شدن عملیات سایبری بعدی مانده (۰ = آزاد)."""
    minutes = float(await get_setting("cyber_cooldown_minutes", "20"))
    last = await db.fetchone(
        "SELECT created_at FROM cyber_ops WHERE attacker_id=? AND defender_id=? ORDER BY id DESC LIMIT 1",
        (attacker_id, defender_id))
    if not last:
        return 0
    elapsed = hours_ago(last["created_at"]) * 60          # دقیقه
    left = int(minutes - elapsed)
    return max(0, left)


async def cyber_cooldown_ok(attacker_id: int, defender_id: int) -> bool:
    """⏱ کول‌داون سایبری ۲۰ دقیقه‌ای (قبلاً ۶ ساعت بود)."""
    return await cyber_cooldown_left(attacker_id, defender_id) <= 0


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
    left = await cyber_cooldown_left(call.from_user.id, defender_id)
    if left > 0:
        return await call.answer(
            f"⏳ عملیات سایبری بعدی روی این کشور: {left} دقیقه دیگر", show_alert=True)
    d_country = await get_country(defender_id)
    from core.politics import active_revolution, country_leader
    leader = await country_leader(d_country)
    rev = await active_revolution(defender_id)
    _a, _d, my_cyber = await army_power(call.from_user.id)
    _a2, _d2, their_cyber = await army_power(defender_id)
    chance = cyber_chance(my_cyber, their_cyber)
    await call.answer()
    await call.message.edit_text(
        f"🕶 <b>عملیات سایبری علیه {d_country['flag']} {d_country['name']}</b>\n\n"
        f"{d_country['flag']} {leader['title']}: <b>{leader['name']}</b>\n"
        + (f"🔥 این کشور همین حالا در انقلاب است (شدت {rev['severity']}٪)\n" if rev else "")
        + f"🖥 قدرت سایبری شما: {fmt(my_cyber)}\n🖥 قدرت سایبری دشمن: {fmt(their_cyber)}\n"
        f"🎲 شانس موفقیت پایه: <b>{round(chance)}%</b>\n\nعملیات را انتخاب کنید:",
        reply_markup=kb([
            [("🎯 ترور رئیس‌جمهور (شروع انقلاب)", f"g|cy|assass|{defender_id}")],
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
    left = await cyber_cooldown_left(call.from_user.id, defender_id)
    if left > 0:
        return await call.answer(
            f"⏳ هنوز کول‌داون تمام نشده — {left} دقیقه مانده", show_alert=True)
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
    d_country = await get_country(defender_id)

    # ─── ترور رئیس‌جمهور: منطق کامل در core.politics (انقلاب + مهار) ───
    if op == "assass":
        from core.politics import assassinate
        _ok, msg = await assassinate(call.from_user.id, defender_id, call.bot)
        await call.answer()
        await call.message.edit_text(msg, reply_markup=kb([back_row("g|war")]))
        return

    _a, _d, my_cyber = await army_power(call.from_user.id)
    _a2, _d2, their_cyber = await army_power(defender_id)
    chance = cyber_chance(my_cyber, their_cyber)
    success = random.random() * 100 < chance
    await db.execute(
        "INSERT INTO cyber_ops(attacker_id, defender_id, kind, success) VALUES(?,?,?,?)",
        (call.from_user.id, defender_id, op, 1 if success else 0))
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
                elif v["title"].startswith("تحریم نفت"):
                    # 🏭 درآمد نفت و انرژی کشور هدف ۵۰٪ کاهش می‌یابد
                    try:
                        await set_setting(f"oil_sanction_{target}", add_hours(24 * 7))
                    except Exception:
                        pass
                # 🚫 «برکناری رهبر» به‌درخواست کاربر حذف شد — هیچ‌کس نمی‌تواند
                # رهبر کشور دیگری را برکنار کند.


# ═══════════ ☢️ هدف قرار دادن تأسیسات هسته‌ای ═══════════


@router.callback_query(F.data == "g|nuk")
async def nuclear_menu(call: CallbackQuery):
    """بخش هدف قرار دادن تأسیسات هسته‌ای: تأسیسات خودم + اهداف دشمن."""
    from core import nuclear

    if await is_disarmed(call.from_user.id):
        return await call.answer("🕊 خلع سلاح شده‌اید — حمله ممکن نیست!", show_alert=True)
    if await is_jammed(call.from_user.id):
        return await call.answer("📡 سرورهای شما اختلال دارند!", show_alert=True)

    ok, reason = await nuclear.can_target(call.from_user.id)
    mine = await nuclear.site_text(call.from_user.id)
    enemy_targets = await nuclear.targets(call.from_user.id)

    lines = [
        "☢️ <b>هدف قرار دادن تأسیسات هسته‌ای</b>\n",
        "🎯 <b>تأسیسات هسته‌ای دشمن</b> = هدفی که با موشک، بمب‌افکن یا تسلیحات فضایی "
        "زده می‌شود. با تخریب کامل، غنی‌سازی دشمن یک پله عقب می‌رود و سانتریفیوژهایش "
        "از بین می‌رود.\n",
        "📡 <b>کشورهای دارای تأسیسات فعال:</b>",
    ]
    rows = []
    if not enemy_targets:
        lines.append("— هیچ کشوری الان تأسیسات فعال ندارد —")
    for t in enemy_targets[:12]:
        lines.append(f"  {t['emoji'] or '☢️'} {t['flag']} <b>{t['name']}</b> — "
                     f"{t['kind']} | مرحلهٔ {t['stage']} | "
                     f"استحکام {t['hp']}/{t.get('max_hp') or 100}")
        rows.append([(f"☢️ حمله به تأسیسات {t['flag']} {t['name']}",
                      f"g|nukc|{t['user_id']}")])
    if not ok:
        lines.append("\n" + reason)
    lines.append("\n" + mine)
    rows.append([("🔧 بازسازی/تعمیر تأسیسات خودم", "g|nukfix")])
    rows.append(back_row("g|war"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|nukc|"))
async def nuclear_confirm(call: CallbackQuery):
    """صفحهٔ تأیید حمله به تأسیسات با پیش‌بینی شانس."""
    from core import nuclear
    defender_id = int(call.data.split("|")[2])
    if defender_id == call.from_user.id:
        return await call.answer("نمی‌توانید تأسیسات خودتان را هدف بگیرید", show_alert=True)
    ok, reason = await nuclear.can_target(call.from_user.id)
    if not ok:
        return await call.answer(reason[:190], show_alert=True)
    look = await nuclear.strike_outlook(call.from_user.id, defender_id)
    if not look["site"]:
        return await call.answer("این کشور تأسیسات هسته‌ای ندارد", show_alert=True)
    if look["hp"] <= 0:
        return await call.answer("تأسیسات این کشور از قبل از کار افتاده است", show_alert=True)
    left = await attack_cooldown_state_public(call.from_user.id)
    lines = [
        f"☢️ <b>حمله به تأسیسات هسته‌ای {look['site']['flag']} {look['site']['name']}</b>\n",
        f"🏭 هدف: {look['emoji']} <b>{look['kind']}</b> (مرحلهٔ {look['stage']})",
        f"🏗 استحکام: <b>{look['hp']}/{look['site'].get('max_hp') or 100}</b>",
        "",
        f"🚀 توان حملهٔ شما: <b>{fmt(look['atk_power'])}</b>",
        f"🛡 پدافند تأسیسات دشمن: <b>{fmt(look['shield'])}</b>",
        f"🎲 شانس موفقیت: <b>{look['chance']}%</b>",
        "",
        "💥 <b>در صورت موفقیت:</b> استحکام تأسیسات کم می‌شود، سانتریفیوژها منهدم "
        "می‌شوند و با ضربهٔ سنگین <b>غنی‌سازی دشمن یک پله عقب</b> می‌رود.",
        "☢️ در تخریب کامل، احتمال نشت رادیواکتیو و افت شدید رضایت مردم دشمن وجود دارد.",
        "🛡 <b>در صورت شکست:</b> پدافند دشمن حمله را دفع می‌کند و شما تلفات می‌دهید.",
        "⏱ این حمله کول‌داون ۳ دقیقه‌ای حمله را مصرف می‌کند.",
    ]
    if left > 0:
        lines.append(f"\n⏳ نیروها در حال بازسازی — {left} ثانیه دیگر آزاد می‌شوید.")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([
        [("☢️ شلیک کن!", f"g|nukgo|{defender_id}")],
        back_row("g|nuk", "🔴 انصراف"),
    ]))


async def attack_cooldown_state_public(user_id: int) -> int:
    """ثانیهٔ باقی‌ماندهٔ کول‌داون حمله (۰ = آزاد)."""
    ready, remaining, _msg = await attack_cooldown_state(user_id)
    return 0 if ready else remaining


@router.callback_query(F.data.startswith("g|nukgo|"))
async def nuclear_execute(call: CallbackQuery):
    from core import nuclear
    defender_id = int(call.data.split("|")[2])
    ready, _remaining, msg = await attack_cooldown_state(call.from_user.id)
    if not ready:
        return await call.answer("⏳ نیروها در حال بازسازی‌اند — کمی صبر کنید", show_alert=True)
    await call.answer("☢️ در حال اجرای حمله...")
    report = await nuclear.strike(call.bot, call.from_user.id, defender_id)
    try:
        await call.message.edit_text(report, reply_markup=kb([back_row("g|nuk")]))
    except Exception:
        await call.message.answer(report, reply_markup=kb([back_row("g|nuk")]))


@router.callback_query(F.data == "g|nukfix")
async def nuclear_rebuild(call: CallbackQuery):
    from core import nuclear
    ok, msg = await nuclear.rebuild(call.from_user.id)
    await call.answer("🔧" if ok else "❌", show_alert=not ok)
    await call.message.edit_text(msg, reply_markup=kb([back_row("g|nuk")]))

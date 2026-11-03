"""اتاق جنگ: اعلان جنگ (با/بدون مجوز)، حمله (۵ نوع) و عملیات سایبری."""
import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import (army_power, bump_progress, get_country,
                          get_state, has_project_named, is_disarmed,
                          is_jammed, is_leader_blocked, sub_asset, veto_users)
from core.images import announce_img
from core.utils import fmt, add_hours, iso, hours_left, fmt_hm, jloads, clamp
from gamebot.common import back_row, blocked_banner, kb, send_home, dm

router = Router()

ATTACK_TYPES = {"sea": "⚓ دریایی", "air": "✈️ هوایی", "land": "🪖 زمینی",
                "space": "🛰️ فضایی", "mixed": "🔀 ترکیبی"}


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


# ─── اعلان جنگ ───


@router.callback_query(F.data == "g|wdec")
async def declare_list(call: CallbackQuery):
    if await is_leader_blocked(call.from_user.id):
        return await call.answer("🚫 رهبر شما ترور شده — دیپلماسی مسدود است!", show_alert=True)
    countries = await db.fetchall(
        "SELECT c.*, u.full_name FROM countries c JOIN users u ON u.id=c.owner_id "
        "WHERE c.owner_id IS NOT NULL AND c.owner_id!=? ORDER BY c.name", (call.from_user.id,))
    if not countries:
        return await call.answer("کشور دیگری برای جنگ وجود ندارد", show_alert=True)
    rows = [[(f"{c['flag']} {c['name']}", f"g|wdec|{c['owner_id']}")] for c in countries]
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
        # رای‌گیری مجوز حمله در سازمان ملل
        hours = float(await get_setting("vote_duration_hours", "24"))
        vote_id = await db.execute(
            "INSERT INTO un_votes(title, kind, subject_id, options, ends_at, created_by) VALUES(?,?,?,?,?,?)",
            (f"مجوز جنگ {a_country['name']} علیه {d_country['name']}",
             "war", war_id, '["تایید","رد","بی‌طرف"]', add_hours(hours), attacker_id))
        await announce_img(bot,
                           f"🗳 سازمان ملل: درخواست <b>مجوز جنگ</b> {a_country['flag']} {a_country['name']} "
                           f"علیه {d_country['flag']} {d_country['name']}\nدلیل: {reason}\n"
                           "کشورها از بخش 🕊 سازمان ملل رأی می‌دهند.", "war")
    else:
        # جنگ فوری + بررسی جنایت جنگی
        hours = float(await get_setting("vote_duration_hours", "24"))
        await db.execute(
            "INSERT INTO un_votes(title, kind, subject_id, options, ends_at, created_by) VALUES(?,?,?,?,?,?)",
            (f"آیا جنگ {a_country['name']} علیه {d_country['name']} جنایت جنگی است؟",
             "crime", war_id, '["جنایت جنگی است","جنایت نیست","بی‌طرف"]', add_hours(hours), attacker_id))
        await announce_img(bot,
                           f"⚔️ {a_country['flag']} {a_country['name']} بدون مجوز سازمان ملل به "
                           f"{d_country['flag']} {d_country['name']} اعلان جنگ داد!", "war")
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
    # هر جنگی که در آن مهاجم یا مدافع باشم (حمله متقابل مدافع هم ممکن است)
    wars = await db.fetchall(
        "SELECT w.*, ca.name AS atk_name, ca.flag AS atk_flag, "
        "cd.name AS def_name, cd.flag AS def_flag, cd.has_sea, cd.id AS cid "
        "FROM wars w "
        "JOIN users ua ON ua.id=w.attacker_id JOIN countries ca ON ca.id=ua.country_id "
        "JOIN users ud ON ud.id=w.defender_id JOIN countries cd ON cd.id=ud.country_id "
        "WHERE (w.attacker_id=? OR w.defender_id=?) AND w.status='active' ORDER BY w.id DESC",
        (call.from_user.id, call.from_user.id))
    if not wars:
        return await call.answer("اول باید اعلان جنگ بدهید!", show_alert=True)
    rows = []
    for w in wars:
        if w["attacker_id"] == call.from_user.id:
            rows.append([(f"🎯 {w['def_flag']} {w['def_name']} — 🗡 مهاجم", f"g|watkc|{w['id']}")])
        else:
            rows.append([(f"⚔️ {w['atk_flag']} {w['atk_name']} — 🛡 حمله متقابل!", f"g|watkc|{w['id']}")])
    rows.append(back_row("g|war"))
    await call.answer()
    await call.message.edit_text("🗡 <b>حمله</b>\n\nجنگ فعال خود را انتخاب کنید "
                                 "(مدافع هم می‌تواند حمله متقابل به مهاجم بکند):", reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|watkc|"))
async def attack_type(call: CallbackQuery, state: FSMContext):
    war_id = int(call.data.split("|")[2])
    # هر دو طرف جنگ می‌توانند حمله کنند (مدافع = حمله متقابل)
    war = await db.fetchone(
        "SELECT * FROM wars WHERE id=? AND status='active' AND (attacker_id=? OR defender_id=?)",
        (war_id, call.from_user.id, call.from_user.id))
    if not war:
        return await call.answer("جنگ فعال نیست", show_alert=True)
    role = "attacker" if war["attacker_id"] == call.from_user.id else "defender"
    enemy_id = war["defender_id"] if role == "attacker" else war["attacker_id"]
    d_country = await get_country(enemy_id)
    a_country = await get_country(call.from_user.id)
    # بررسی قواعد هر نوع حمله
    my_equipment = await db.fetchall(
        "SELECT e.*, c.key AS cat_key, a.quantity FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0", (call.from_user.id,))
    has = lambda cat: any(e["cat_key"] == cat for e in my_equipment)
    has_carrier = any(e["name"] == "ناو هواپیمابر" for e in my_equipment)
    bases = await db.fetchall(
        "SELECT b.*, c.region FROM bases b JOIN countries c ON c.owner_id=b.host_id "
        "WHERE b.guest_id=? AND b.status='active'", (call.from_user.id,))
    base_near = any(b["region"] == d_country["region"] for b in bases)

    sea_ok = d_country["has_sea"] == 1 and has("sea")
    air_ok = has_carrier or base_near  # ناو هواپیمابر یا پایگاه نزدیک
    land_ok = (a_country["region"] == d_country["region"]) or base_near
    space_ok = has("space")
    mixed_ok = sum([sea_ok, air_ok, land_ok, space_ok]) >= 2

    rules_txt = {
        "sea": "فقط کشورهای دارای دریا (نیاز به نیروی دریایی)",
        "air": "نیاز به ناو هواپیمابر یا پایگاه نزدیک",
        "land": "نیاز به هم‌مرزی (هم‌منطقه) یا پایگاه در منطقه هدف",
        "space": "از هرجای دنیا — فقط با تسلیحات فضایی",
        "mixed": "ترکیب دو نوع حمله",
    }
    lines = [f"🎯 حمله به {d_country['flag']} <b>{d_country['name']}</b>\n"]
    for key, title in ATTACK_TYPES.items():
        ok = {"sea": sea_ok, "air": air_ok, "land": land_ok, "space": space_ok, "mixed": mixed_ok}[key]
        lines.append(f"{'✅' if ok else '❌'} {title} — {rules_txt[key]}")
    rows = []
    for key, title in ATTACK_TYPES.items():
        ok = {"sea": sea_ok, "air": air_ok, "land": land_ok, "space": space_ok, "mixed": mixed_ok}[key]
        if ok:
            rows.append([(f"{title}", f"g|wtype|{war_id}|{key}")])
    rows.append(back_row("g|watk"))
    await state.update_data(plan={}, role=role, enemy_id=enemy_id)
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|wtype|"))
async def attack_equipment(call: CallbackQuery, state: FSMContext):
    _, _, war_id, atype = call.data.split("|")
    await state.update_data(war_id=int(war_id), atype=atype, plan={})
    allowed_cats = {"sea": ["sea"], "air": ["air"], "land": ["land"], "space": ["space"],
                    "mixed": ["sea", "air", "land", "space"]}[atype]
    await _equip_picker(call, state, allowed_cats)


async def _equip_picker_payload(user_id: int, state: FSMContext, allowed_cats: list) -> tuple[str, list]:
    data = await state.get_data()
    plan = data.get("plan", {})
    my_equipment = await db.fetchall(
        "SELECT e.*, a.quantity, c.title AS cat_title, c.emoji AS cat_emoji, c.key AS cat_key FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0 AND c.key IN (%s) "
        "ORDER BY c.id, e.id" % ",".join("?" * len(allowed_cats)),
        (user_id, *allowed_cats))
    soldiers = await db.fetchall(
        "SELECT s.*, a.quantity FROM player_assets a JOIN soldier_types s ON s.id=a.item_id "
        "WHERE a.user_id=? AND a.item_type='soldier' AND a.quantity>0", (user_id,))
    lines = ["🗡 <b>انتخاب نیروی حمله</b>\n"]
    if plan:
        lines.append("📦 <b>نیروهای انتخاب‌شده:</b>")
        eq_names = {e["id"]: f"{e['emoji']} {e['name']}" for e in my_equipment}
        for eid, qty in plan.items():
            lines.append(f"  {eq_names.get(int(eid), eid)} ×{fmt(qty)}")
        lines.append("")
    if my_equipment:
        lines.append("برای افزودن تجهیزات، روی آن بزنید و تعداد را بنویسید:")
    else:
        lines.append("❌ تجهیز مناسب ندارید! اول از 🎖 پادگان خرید کنید.")
    if soldiers:
        total_soldiers = sum(s["quantity"] for s in soldiers)
        lines.append(f"\n🪖 <b>{fmt(total_soldiers)} سرباز</b> به‌طور خودکار در نبرد شرکت می‌کنند.")
    rows = [[(f"{e['emoji']} {e['name']} (موجود {fmt(e['quantity'])})",
              f"g|weq|{e['id']}")] for e in my_equipment]
    if plan:
        rows.append([("⚔️ حمله!", "g|wgo")])
    rows.append(back_row("g|watk"))
    return "\n".join(lines), rows


async def _equip_picker(call: CallbackQuery, state: FSMContext, allowed_cats: list):
    lines, rows = await _equip_picker_payload(call.from_user.id, state, allowed_cats)
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


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
        qty = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد بفرستید.")
    data = await state.get_data()
    e = await db.fetchone(
        "SELECT e.*, a.quantity FROM equipment e JOIN player_assets a ON a.item_id=e.id AND a.user_id=? "
        "AND a.item_type='equipment' WHERE e.id=?", (message.from_user.id, data["eq_id"]))
    if not e or qty <= 0 or qty > e["quantity"]:
        return await send_home(message, f"❌ عدد باید بین ۱ تا {fmt(e['quantity'] if e else 0)} باشد.")
    plan = data.get("plan", {})
    plan[str(data["eq_id"])] = qty
    await state.set_state(None)
    await state.update_data(plan=plan)
    allowed_cats = {"sea": ["sea"], "air": ["air"], "land": ["land"], "space": ["space"],
                    "mixed": ["sea", "air", "land", "space"]}[data.get("atype", "mixed")]
    # ⚠️ edit نکنید: پیام کاربر ویرایش‌ناپذیر است — picker را به‌عنوان پیام جدید می‌فریم
    lines, rows = await _equip_picker_payload(message.from_user.id, state, allowed_cats)
    await send_home(message, "\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data == "g|wgo")
async def attack_go(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    plan = data.get("plan", {})
    war = await db.fetchone(
        "SELECT * FROM wars WHERE id=? AND status='active' AND (attacker_id=? OR defender_id=?)",
        (data.get("war_id"), call.from_user.id, call.from_user.id))
    if not war or not plan:
        await state.clear()
        return await call.answer("جنگ یا نیروها نامعتبر!", show_alert=True)
    role = data.get("role", "attacker")
    await state.clear()
    await resolve_battle(call, war, plan, data.get("atype", "mixed"), role)


async def resolve_battle(call, war: dict, plan: dict, atype: str, role: str = "attacker"):
    # در حمله متقابل، مدافع خود را مهاجم نبرد می‌دانیم
    if role == "defender":
        attacker_id, defender_id = call.from_user.id, war["attacker_id"]
    else:
        attacker_id, defender_id = war["attacker_id"], war["defender_id"]
    a_country = await get_country(attacker_id)
    d_country = await get_country(defender_id)

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

    chance = clamp(atk_power / (atk_power + d_def), 0.05, 0.95) if (atk_power + d_def) > 0 else 0.5
    won = random.random() < chance

    # تلفات و غارت
    defender_user = await db.fetchone("SELECT * FROM users WHERE id=?", (defender_id,))
    loot = 0
    if won:
        loot = int((defender_user["money"] or 0) * 0.10)
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (loot, defender_id))
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (loot, attacker_id))
        def_loss, atk_loss = 0.30, 0.15
    else:
        def_loss, atk_loss = 0.10, 0.40
    # کاهش تجهیزات استفاده‌شده مهاجم
    for eid, qty in plan.items():
        await sub_asset(attacker_id, "equipment", int(eid), max(1, int(qty * atk_loss)))
    # تلفات مدافع
    for e in await db.fetchall(
            "SELECT a.item_id FROM player_assets a JOIN equipment e ON e.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0", (defender_id,)):
        row = await db.fetchone("SELECT quantity FROM player_assets WHERE user_id=? AND item_id=? AND item_type='equipment'",
                                (defender_id, e["item_id"]))
        if row:
            await sub_asset(defender_id, "equipment", e["item_id"], max(1, int(row["quantity"] * def_loss)))

    await db.execute(
        "INSERT INTO battles(war_id, attacker_id, defender_id, atk_type, atk_power, def_power, result, loot) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (war["id"], attacker_id, defender_id, atype, round(atk_power), round(d_def),
         "win" if won else "lose", loot))
    await bump_progress(attacker_id, "war")
    await bump_progress(defender_id, "war")

    atype_fa = ATTACK_TYPES.get(atype, atype)
    result_text = (
        f"⚔️ <b>نبرد {atype_fa}</b>: {a_country['flag']} {a_country['name']} ← {d_country['flag']} {d_country['name']}\n\n"
        f"🗡 قدرت حمله: {fmt(atk_power)}\n🛡 قدرت دفاع: {fmt(d_def)}\n"
        f"🎲 شانس پیروزی: {round(chance * 100)}%\n\n"
        + (f"🏆 <b>{a_country['name']} پیروز شد!</b>\n💰 غارت: {fmt(loot)}" if won
           else f"🛡 <b>{d_country['name']} دفاع کرد!</b>")
    )
    await announce_img(call.bot, result_text, "war")
    await call.answer()
    await call.message.edit_text(result_text + "\n\nتلفات مهاجم: " +
                                 ("۱۵٪" if won else "۴۰٪") + " | تلفات مدافع: " +
                                 ("۳۰٪" if won else "۱۰٪"), reply_markup=kb([back_row("g|war")]))
    try:
        await dm(call.bot, defender_id, result_text)
    except Exception:
        pass


# ─── سایبری ───


@router.callback_query(F.data == "g|wcyb")
async def cyber_enemy_list(call: CallbackQuery):
    if await is_leader_blocked(call.from_user.id):
        return await call.answer("🚫 رهبر شما ترور شده!", show_alert=True)
    countries = await db.fetchall(
        "SELECT c.* FROM countries c JOIN users u ON u.id=c.owner_id "
        "WHERE c.owner_id IS NOT NULL AND c.owner_id!=? ORDER BY c.name", (call.from_user.id,))
    rows = [[(f"{c['flag']} {c['name']}", f"g|wcyb|{c['owner_id']}")] for c in countries]
    rows.append(back_row("g|war"))
    await call.answer()
    await call.message.edit_text(
        "🕶 <b>عملیات سایبری (مخفیانه)</b>\n\nکشور هدف را انتخاب کنید.\n"
        "💡 اگر قدرت سایبری شما ۲ برابر دشمن باشد شانس ~۵۰٪ است و برای شانس ۱۰۰٪ باید ۳ برابر قدرت داشته باشید.",
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
    return clamp(50 * (my_cyber / max(1, their_cyber) - 1), 5, 95)


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
    _, _, op, defender_id = call.data.split("|")
    defender_id = int(defender_id)
    if not await cyber_cooldown_ok(call.from_user.id, defender_id):
        return await call.answer("⏳ هنوز زمان cooldown تمام نشده", show_alert=True)
    if op == "steal":
        await state.set_state(WarFSM.steal_amount)
        await state.update_data(defender_id=defender_id)
        victim = await db.fetchone("SELECT * FROM users WHERE id=?", (defender_id,))
        treasury = victim["money"]
        await call.answer()
        return await call.message.edit_text(
            f"💸 <b>دزدی از خزانه</b>\n\n💰 خزانه دشمن: <b>{fmt(treasury)}</b>\n\n"
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
    await announce_img(call.bot, f"🕶 گزارش محرمانه: عملیات سایبری علیت {d_country['name']} انجام شد.", "war")
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
        return await send_home(message, f"❌ خزانه دشمن فقط {fmt(victim['money'])} دارد.")
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
                if yes > no:
                    await db.execute("UPDATE wars SET status='active' WHERE id=?", (war["id"],))
                    try:
                        from core.rescue import ensure_campaign
                        await ensure_campaign(war["id"])
                    except Exception:
                        pass
                    if bot:
                        try:
                            await dm(bot, war["attacker_id"], "🗳 سازمان ملل جنگ شما را تأیید کرد! حمله آزاد است.")
                            await dm(bot, war["defender_id"], "🗳 سازمان ملل به جنگ علیه شما مجوز داد!")
                        except Exception:
                            pass
                else:
                    await db.execute("UPDATE wars SET status='rejected' WHERE id=?", (war["id"],))
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

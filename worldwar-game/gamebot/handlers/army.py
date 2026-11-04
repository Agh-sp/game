"""مدیریت کشور — ارتش: پایگاه نظامی و پادگان (تجهیزات/سربازان)."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db
from core.economy import (add_asset, assets_of, bump_progress, get_country,
                          project_done, settle_trainings)
from core.utils import fmt, hours_left, fmt_hm, iso, add_hours, clamp
from gamebot.common import back_row, kb, send_home, dm

router = Router()


class ArmyFSM(StatesGroup):
    eq_qty = State()
    train_qty = State()


@router.callback_query(F.data == "g|army")
async def army_menu(call: CallbackQuery):
    await settle_trainings(call.from_user.id)
    await call.answer()
    await call.message.edit_text(
        "🪖 <b>ارتش</b>\n\nبخش مورد نظر را انتخاب کنید:",
        reply_markup=kb([
            [("🚚 پایگاه نظامی", "g|base")],
            [("🎖 پادگان", "g|bar")],
            back_row("g|mg"),
        ]),
    )


# ─── پایگاه نظامی ───


async def base_list_text(user_id: int) -> tuple[str, list]:
    my_bases = await db.fetchall(
        "SELECT b.*, c.name AS host_name, c.flag AS host_flag, u2.id AS hid FROM bases b "
        "JOIN countries c ON c.owner_id=b.host_id "
        "LEFT JOIN users u2 ON u2.id=b.host_id "
        "WHERE b.guest_id=? AND b.status='active'", (user_id,))
    pending_out = await db.fetchall(
        "SELECT b.*, c.name AS host_name, c.flag AS host_flag FROM bases b "
        "JOIN countries c ON c.owner_id=b.host_id "
        "WHERE b.guest_id=? AND b.status='pending'", (user_id,))
    pending_in = await db.fetchall(
        "SELECT b.*, c.name AS guest_name, c.flag AS guest_flag FROM bases b "
        "JOIN countries c ON c.owner_id=b.guest_id "
        "WHERE b.host_id=? AND b.status='pending'", (user_id,))
    lines = ["🚚 <b>پایگاه نظامی</b>\n"]
    lines.append("📡 <b>پایگاه‌های فعال من در کشورهای دیگر:</b>")
    if my_bases:
        for b in my_bases:
            lines.append(f"✅ {b['host_flag']} {b['host_name']}")
    else:
        lines.append("— ندارید —")
    if pending_out:
        lines.append("\n⏳ <b>درخواست‌های ارسالی من:</b>")
        for b in pending_out:
            lines.append(f"⏳ {b['host_flag']} {b['host_name']}")
    if pending_in:
        lines.append("\n📨 <b>درخواست‌های دریافتی:</b>")
        lines.append("کشورهای دیگر اجازه ساخت پایگاه می‌خواهند. با تأیید، متحد نظامی می‌شوید و "
                     "دفاع شما قوی‌تر می‌شود.")
    rows = []
    for b in pending_in:
        rows.append([
            (f"✅ تأیید {b['guest_flag']} {b['guest_name']}", f"g|baseok|{b['id']}"),
            ("❌ رد", f"g|baseno|{b['id']}"),
        ])
    rows.append([("🤝 درخواست پایگاه جدید", "g|basereq")])
    rows.append(back_row("g|army"))
    return "\n".join(lines), rows


@router.callback_query(F.data == "g|base")
async def base_menu(call: CallbackQuery):
    text, rows = await base_list_text(call.from_user.id)
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|baseok|"))
async def base_approve(call: CallbackQuery):
    bid = int(call.data.split("|")[2])
    b = await db.fetchone("SELECT * FROM bases WHERE id=? AND host_id=? AND status='pending'",
                          (bid, call.from_user.id))
    if not b:
        return await call.answer("درخواست یافت نشد", show_alert=True)
    await db.execute("UPDATE bases SET status='active' WHERE id=?", (bid,))
    try:
        await dm(call.bot, b["guest_id"],
                                    "🤝 درخواست پایگاه نظامی شما تأیید شد! اکنون در آن کشور مستقر هستید.")
    except Exception:
        pass
    await call.answer("✅ تأیید شد")
    await base_menu(call)


@router.callback_query(F.data.startswith("g|baseno|"))
async def base_reject(call: CallbackQuery):
    bid = int(call.data.split("|")[2])
    b = await db.fetchone("SELECT * FROM bases WHERE id=? AND host_id=? AND status='pending'",
                          (bid, call.from_user.id))
    if not b:
        return await call.answer("درخواست یافت نشد", show_alert=True)
    await db.execute("DELETE FROM bases WHERE id=?", (bid,))
    try:
        await dm(call.bot, b["guest_id"], "❌ درخواست پایگاه نظامی شما رد شد.")
    except Exception:
        pass
    await call.answer("رد شد")
    await base_menu(call)


@router.callback_query(F.data == "g|basereq")
async def base_request_list(call: CallbackQuery):
    countries = await db.fetchall(
        "SELECT c.*, u.full_name FROM countries c JOIN users u ON u.id=c.owner_id "
        "WHERE c.owner_id IS NOT NULL AND c.owner_id!=? ORDER BY c.name",
        (call.from_user.id,))
    rows = [[(f"{c['flag']} {c['name']}", f"g|basereqr|{c['owner_id']}")] for c in countries]
    rows.append(back_row("g|base"))
    await call.answer()
    await call.message.edit_text(
        "🤝 <b>درخواست پایگاه نظامی</b>\n\nکشوری را برای مذاکره انتخاب کنید. اگر طرف مقابل تأیید کند، "
        "پایگاه شما در آن کشور ساخته می‌شود:\n"
        "• اگر به کشور میزبان حمله شود از آن دفاع می‌کنید\n"
        "• برای حمله زمینی از مرز آن کشور عبور می‌کنید",
        reply_markup=kb(rows),
    )


@router.callback_query(F.data.startswith("g|basereqr|"))
async def base_request_send(call: CallbackQuery):
    host_id = int(call.data.split("|")[2])
    exists = await db.fetchone(
        "SELECT id FROM bases WHERE guest_id=? AND host_id=? AND status IN ('pending','active')",
        (call.from_user.id, host_id))
    if exists:
        return await call.answer("قبلاً درخواست/پایگاه دارید", show_alert=True)
    await db.execute("INSERT INTO bases(host_id, guest_id, status) VALUES(?,?,'pending')",
                     (host_id, call.from_user.id))
    try:
        await dm(call.bot, 
            host_id,
            "📨 یک کشور درخواست ساخت <b>پایگاه نظامی</b> در سرزمین شما را دارد.\n"
            "برای تأیید یا رد، از مسیر: 🏛 مدیریت کشور ← 🪖 ارتش ← 🚚 پایگاه نظامی استفاده کنید.")
    except Exception:
        pass
    await call.answer("📨 درخواست ارسال شد")
    await base_menu(call)


# ─── پادگان ───


def barracks_rows() -> list:
    """دکمه‌های پادگان — هم برای ویرایش پیام و هم برای ارسال پیام تازه."""
    return [
        [("📋 تجهیزات و سربازان من", "g|eq")],
        [("🛒 خرید تجهیزات", "g|eqshop")],
        [("🎓 تعلیم سرباز", "g|train")],
        back_row("g|army"),
    ]


@router.callback_query(F.data == "g|bar")
async def barracks_menu(call: CallbackQuery):
    await settle_trainings(call.from_user.id)
    await call.answer()
    await call.message.edit_text(
        "🎖 <b>پادگان</b>\n\nگزینه مورد نظر را انتخاب کنید:",
        reply_markup=kb(barracks_rows()),
    )


@router.callback_query(F.data == "g|eq")
async def my_equipment(call: CallbackQuery):
    await settle_trainings(call.from_user.id)
    lines = ["📋 <b>تجهیزات و سربازان من</b>\n"]
    for cat in await db.fetchall("SELECT * FROM equipment_categories WHERE is_active=1 ORDER BY id"):
        items = await db.fetchall(
            "SELECT a.quantity, e.* FROM player_assets a JOIN equipment e ON e.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='equipment' AND e.category_id=?",
            (call.from_user.id, cat["id"]))
        if items:
            lines.append(f"\n{cat['emoji']} <b>{cat['title']}:</b>")
            for it in items:
                lines.append(
                    f"  {it['emoji']} {it['name']} ×{fmt(it['quantity'])} — "
                    f"⚔️{fmt(it['attack_power'])} 🛡{fmt(it['defense_power'])} ⚡{it['speed']}")
    soldiers = await assets_of(call.from_user.id, "soldier")
    lines.append("\n🪖 <b>سربازان:</b>")
    if soldiers:
        for s in soldiers:
            lines.append(f"  {s['soldier_emoji']} {s['soldier_name']} ×{fmt(s['quantity'])} — قدرت {fmt(s['power'])}")
    else:
        lines.append("  — ندارید —")
    trainings = await db.fetchall(
        "SELECT t.*, s.name, s.emoji FROM soldier_trainings t JOIN soldier_types s ON s.id=t.type_id "
        "WHERE t.user_id=?", (call.from_user.id,))
    if trainings:
        lines.append("\n🎓 <b>در حال آموزش:</b>")
        for t in trainings:
            lines.append(f"  {t['emoji']} {t['name']} ×{fmt(t['count'])} — {fmt_hm(hours_left(t['completes_at']))} مانده")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([back_row("g|bar")]))


@router.callback_query(F.data == "g|eqshop")
async def eq_shop(call: CallbackQuery):
    cats = await db.fetchall(
        "SELECT c.*, COUNT(e.id) n FROM equipment_categories c "
        "LEFT JOIN equipment e ON e.category_id=c.id AND e.is_active=1 "
        "WHERE c.is_active=1 GROUP BY c.id ORDER BY c.id")
    rows = [[(f"{c['emoji']} {c['title']}", f"g|eqcat|{c['id']}")] for c in cats]
    rows.append(back_row("g|bar"))
    await call.answer()
    await call.message.edit_text(
        "🛒 <b>خرید تجهیزات نظامی</b>\n\nدسته‌بندی را انتخاب کنید "
        "(تجهیزات فضایی فقط با 🪙 سکه شاهی هستند):",
        reply_markup=kb(rows),
    )


SUBCATS = {
    "air": [
        ("drone", "🛸 پهپادها و پهپادهای انتحاری"),
        ("fighter", "✈️ جنگنده‌ها و رهگیرها"),
        ("bomber", "💣 بمب‌افکن‌های استراتژیک"),
        ("air_defense", "🛡️ سامانه‌های پدافند هوایی"),
        ("transport", "🛬 هواپیماهای ترابری نظامی"),
    ],
    "land": [
        ("tank", "💥 تانک‌های اصلی میدان نبرد"),
        ("apc", "🚐 نفربرها و زره‌پوش‌های رزمی"),
        ("artillery", "🚀 توپخانه و راکت‌اندازها"),
    ],
    "sea": [
        ("speedboat", "🚤 قایق‌های تندرو موشک‌انداز"),
        ("frigate", "🚢 ناوچه‌ها و ناوشکن‌ها"),
        ("submarine", "🦈 زیردریایی‌های تهاجمی و اتمی"),
        ("carrier", "⛴️ ناوهای هواپیمابر"),
    ],
    "cyber": [
        ("malware", "👾 بدافزارها و ویروس‌های تهاجمی"),
        ("firewall", "🛡️ فایروال‌ها و مراکز پایش داده"),
        ("ew", "📡 سامانه‌های جنگ الکترونیک"),
    ],
    "missile": [
        ("cruise", "🚀 موشک‌های کروز"),
        ("ballistic", "☄️ موشک‌های بالستیک"),
        ("antiship", "🌊 موشک‌های ضدکشتی"),
        ("sam", "🛡️ سامانه‌های پدافند موشکی"),
    ],
}

SUB_FALLBACK_TITLE = "📦 سایر تجهیزات این دسته"


@router.callback_query(F.data.startswith("g|eqcat|"))
async def eq_category(call: CallbackQuery):
    cid = int(call.data.split("|")[2])
    cat = await db.fetchone("SELECT * FROM equipment_categories WHERE id=?", (cid,))
    if not cat:
        return await call.answer("یافت نشد", show_alert=True)
    
    # برای بخش فضایی مستقیماً موارد را نشان بده (طبق خواسته کاربر)
    if cat["key"] == "space":
        items = await db.fetchall(
            "SELECT e.*, p.name AS req_name FROM equipment e "
            "LEFT JOIN buildings p ON p.id=e.requires_project_id "
            "WHERE e.category_id=? AND e.is_active=1 ORDER BY e.price_money, e.price_coins", (cid,))
        lines = [f"{cat['emoji']} <b>تجهیزات تسلیحات {cat['title']}</b>\n"]
        rows = []
        for e in items:
            price = f"🪙 {fmt(e['price_coins'])} سکه شاهی" if e["price_coins"] else f"💰 {fmt(e['price_money'])}"
            lines.append(f"{e['emoji']} <b>{e['name']}</b>: {price} — ⚔️{fmt(e['attack_power'])} ⚡سرعت {e['speed']}")
            rows.append([(f"{e['emoji']} {e['name']}", f"g|eqbuy|{e['id']}")])
        rows.append(back_row("g|eqshop"))
        await call.answer()
        return await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))

    # برای سایر رسته‌ها: نمایش زیردسته‌ها (مانند پهپاد، جنگنده، تانک و ...)
    known = dict(SUBCATS.get(cat["key"], []))
    # زیردسته‌های واقعی موجود در دیتابیس — تا تجهیزاتی که ادمین دستی/جمعی ساخته هم دیده شوند
    present = [r["subcategory"] or "" for r in await db.fetchall(
        "SELECT DISTINCT subcategory FROM equipment WHERE category_id=? AND is_active=1", (cid,))]
    ordered: list[tuple[str, str]] = []
    for key, title in SUBCATS.get(cat["key"], []):
        if key in present:
            ordered.append((key, title))
    for key in present:
        if key and key not in known:
            ordered.append((key, f"📦 سایر ({key})"))
    if "" in present:
        ordered.append(("", SUB_FALLBACK_TITLE))

    # اگر فقط یک گروه وجود دارد، مستقیم تجهیزات را نشان بده
    if len(ordered) <= 1 and ordered:
        sub_key = ordered[0][0]
        items = await db.fetchall(
            "SELECT e.*, p.name AS req_name FROM equipment e "
            "LEFT JOIN buildings p ON p.id=e.requires_project_id "
            "WHERE e.category_id=? AND COALESCE(e.subcategory,'')=? AND e.is_active=1 "
            "ORDER BY e.price_money, e.price_coins", (cid, sub_key))
        lines = [f"{cat['emoji']} <b>تجهیزات {cat['title']}</b>\n"]
        rows = []
        for e in items:
            price = f"🪙 {fmt(e['price_coins'])} سکه" if e["price_coins"] else f"💰 {fmt(e['price_money'])}"
            lines.append(f"{e['emoji']} <b>{e['name']}</b>: {price} — ⚔️{fmt(e['attack_power'])} "
                         f"🛡{fmt(e['defense_power'])} ⚡{e['speed']}"
                         + (f"\n   🔒 {e['requires_text']}" if e["requires_text"] else ""))
            rows.append([(f"{e['emoji']} {e['name']}", f"g|eqbuy|{e['id']}")])
        rows.append(back_row("g|eqshop"))
        await call.answer()
        return await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))

    lines = [
        f"{cat['emoji']} <b>دسته‌بندی تجهیزات {cat['title']}</b>\n",
        "زیرشاخه مورد نظر را انتخاب کنید تا انواع تجهیزات پایه و پیشرفته آن را مشاهده کنید:\n",
    ]
    rows = []
    for sub_key, sub_title in ordered:
        count = (await db.fetchone(
            "SELECT COUNT(*) c FROM equipment WHERE category_id=? AND COALESCE(subcategory,'')=? AND is_active=1",
            (cid, sub_key)))["c"]
        rows.append([(f"{sub_title} ({count})", f"g|eqsub|{cid}|{sub_key or '-'}")])
    rows.append(back_row("g|eqshop"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|eqsub|"))
async def eq_subcategory_items(call: CallbackQuery):
    _, _, cid, sub_key = call.data.split("|")
    cid = int(cid)
    sub_key = "" if sub_key == "-" else sub_key
    cat = await db.fetchone("SELECT * FROM equipment_categories WHERE id=?", (cid,))
    items = await db.fetchall(
        "SELECT e.*, p.name AS req_name FROM equipment e "
        "LEFT JOIN buildings p ON p.id=e.requires_project_id "
        "WHERE e.category_id=? AND COALESCE(e.subcategory,'')=? AND e.is_active=1 "
        "ORDER BY e.price_money, e.price_coins",
        (cid, sub_key),
    )
    sub_name_dict = dict(SUBCATS.get(cat["key"], [])) if cat else {}
    sub_title = sub_name_dict.get(sub_key, SUB_FALLBACK_TITLE if not sub_key else f"📦 سایر ({sub_key})")
    lines = [f"{cat['emoji']} <b>{sub_title}</b>\n"]
    rows = []
    for e in items:
        if e["price_coins"]:
            price = f"🪙 {fmt(e['price_coins'])} سکه"
        else:
            price = f"💰 {fmt(e['price_money'])}"
        stats = []
        if e["attack_power"]:
            stats.append(f"⚔️ {fmt(e['attack_power'])}")
        if e["defense_power"]:
            stats.append(f"🛡 {fmt(e['defense_power'])}")
        if e["cyber_power"]:
            stats.append(f"🖥 {fmt(e['cyber_power'])}")
        if e["speed"]:
            stats.append(f"⚡ سرعت {e['speed']}")
        req = f"\n   🔒 {e['requires_text']}" if e["requires_text"] else ""
        lines.append(f"{e['emoji']} <b>{e['name']}</b>: {price} — {' | '.join(stats)}{req}")
        rows.append([(f"{e['emoji']} {e['name']}", f"g|eqbuy|{e['id']}")])
    rows.append(back_row(f"g|eqcat|{cid}"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|eqbuy|"))
async def eq_buy(call: CallbackQuery, state: FSMContext):
    eid = int(call.data.split("|")[2])
    e = await db.fetchone("SELECT * FROM equipment WHERE id=?", (eid,))
    if not e:
        return await call.answer("یافت نشد", show_alert=True)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if e["requires_project_id"] and not await project_done(user["id"], e["requires_project_id"]):
        return await call.answer(f"🔒 {e['requires_text'] or 'پیش‌نیاز لازم است'}", show_alert=True)
    if e["price_coins"] and user["royal_coins"] < e["price_coins"]:
        return await call.answer("❌ سکه شاهی کافی ندارید", show_alert=True)
    if e["price_money"] and user["money"] < e["price_money"]:
        return await call.answer("❌ بودجه کافی ندارید", show_alert=True)
    await state.set_state(ArmyFSM.eq_qty)
    await state.update_data(eq_id=eid)
    await call.answer()
    price = f"🪙 {fmt(e['price_coins'])} سکه" if e["price_coins"] else f"💰 {fmt(e['price_money'])}"
    await call.message.edit_text(
        f"{e['emoji']} <b>{e['name']}</b> — {price} برای هر عدد\n\n"
        f"💰 موجودی پول شما: <b>{fmt(user['money'])}</b>\n"
        f"🪙 موجودی سکه شاهی: <b>{fmt(user['royal_coins'])}</b>\n"
        + (f"🔒 پیش‌نیاز: {e['requires_text']}\n" if e["requires_text"] else "")
        + "\nتعداد مورد نیاز برای خرید را بنویسید:\n برای انصراف /cancel"
    )


@router.message(ArmyFSM.eq_qty)
async def eq_qty_input(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    if qty <= 0 or qty > 100000:
        return await send_home(message, "❌ عدد باید بین ۱ تا ۱۰۰هزار باشد.")
    data = await state.get_data()
    e = await db.fetchone("SELECT * FROM equipment WHERE id=?", (data["eq_id"],))
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (message.from_user.id,))
    total_money = (e["price_money"] or 0) * qty
    total_coins = (e["price_coins"] or 0) * qty
    if total_coins and user["royal_coins"] < total_coins:
        await state.clear()
        return await send_home(message, f"❌ سکه شاهی کافی نیست — نیاز: {fmt(total_coins)}")
    if total_money and user["money"] < total_money:
        await state.clear()
        return await send_home(message, f"❌ بودجه کافی نیست — نیاز: {fmt(total_money)}")
    await state.clear()
    if total_coins:
        await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?", (total_coins, user["id"]))
    if total_money:
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (total_money, user["id"]))
    await add_asset(user["id"], "equipment", e["id"], qty)
    await bump_progress(user["id"], "bought", qty)
    price = f" + 🪙 {fmt(total_coins)} سکه" if total_coins else ""
    await send_home(
        message,
        f"✅ <b>{fmt(qty)} × {e['name']}</b> به زرادخانه اضافه شد! (💰 {fmt(total_money)}{price})\n\n"
        "🎖 <b>پادگان</b> — گزینه بعدی را انتخاب کنید:",
        reply_markup=kb(barracks_rows()),
    )


# ─── تعلیم سرباز ───


@router.callback_query(F.data == "g|train")
async def train_menu(call: CallbackQuery):
    country = await get_country(call.from_user.id)
    pop = country["population"] if country else 0
    types = await db.fetchall("SELECT * FROM soldier_types WHERE is_active=1 ORDER BY cost_per_unit")
    lines = [
        "🎓 <b>تعلیم سرباز</b>\n",
        f"👥 جمعیت کشور: {fmt(pop)} — حداکثر قابل آموزش همزمان: {fmt(pop * 5 // 100)} (۵٪ جمعیت)",
        "هرچه مدت تعلیم و قیمت بالاتر، سرباز قوی‌تر:\n",
    ]
    rows = []
    for t in types:
        lines.append(f"{t['emoji']} {t['name']} — قدرت {fmt(t['power'])} | "
                     f"💰 {fmt(t['cost_per_unit'])}/نفر | ⏱ {fmt_hm(t['train_hours'])}")
        rows.append([(f"{t['emoji']} {t['name']}", f"g|trn|{t['id']}")])
    rows.append(back_row("g|bar"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|trn|"))
async def train_start(call: CallbackQuery, state: FSMContext):
    tid = int(call.data.split("|")[2])
    t = await db.fetchone("SELECT * FROM soldier_types WHERE id=?", (tid,))
    if not t:
        return await call.answer("یافت نشد", show_alert=True)
    await state.set_state(ArmyFSM.train_qty)
    await state.update_data(train_type=tid)
    await call.answer()
    await call.message.edit_text(
        f"🎓 تعلیم <b>{t['name']}</b>\n💰 هزینه هر نفر: {fmt(t['cost_per_unit'])} | "
        f"⏱ مدت: {fmt_hm(t['train_hours'])}\n\n"
        "تعداد سرباز را بنویسید (بین ۱ تا ۵٪ جمعیت کشور):\n برای انصراف /cancel"
    )


@router.message(ArmyFSM.train_qty)
async def train_qty_input(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    if count <= 0:
        return await send_home(message, "❌ عدد باید مثبت باشد.")
    data = await state.get_data()
    t = await db.fetchone("SELECT * FROM soldier_types WHERE id=?", (data["train_type"],))
    country = await get_country(message.from_user.id)
    max_count = max(1, (country["population"] if country else 1) * 5 // 100)
    if count > max_count:
        return await send_home(message, f"❌ حداکثر {fmt(max_count)} نفر (۵٪ جمعیت) همزمان می‌توانید آموزش دهید.")
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (message.from_user.id,))
    cost = count * (t["cost_per_unit"] or 0)
    if user["money"] < cost:
        await state.clear()
        return await send_home(message, f"❌ بودجه کافی نیست — نیاز: {fmt(cost)}")
    await state.clear()
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user["id"]))
    await db.execute(
        "INSERT INTO soldier_trainings(user_id, type_id, count, completes_at) VALUES(?,?,?,?)",
        (user["id"], t["id"], count, add_hours(t["train_hours"] or 24)),
    )
    await bump_progress(user["id"], "trained", count)
    await send_home(message,
        f"🎓 آموزش <b>{fmt(count)} × {t['name']}</b> آغاز شد!\n"
        f"⏱ پایان: {fmt_hm(t['train_hours'])} دیگر\n💰 هزینه: {fmt(cost)}\n\n"
        "🎖 <b>پادگان</b> — گزینه بعدی را انتخاب کنید:",
        reply_markup=kb(barracks_rows()),
    )

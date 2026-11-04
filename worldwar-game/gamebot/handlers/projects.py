"""مدیریت کشور — پروژه ملی (تفریحی/علمی/احداث شرکت) و شرکت‌های من."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db
from core.economy import announce, bump_progress, satisfaction_recompute
from core.utils import fmt, fmt_money, hours_left, fmt_hm, iso, add_hours
from gamebot.common import back_row, kb, send_home

router = Router()


class ProjectFSM(StatesGroup):
    name = State()
    height = State()
    company_type = State()
    company_name = State()


@router.callback_query(F.data == "g|prj")
async def projects_menu(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        "🏗 <b>پروژه ملی</b>\n\nکدام بخش را می‌سازید؟",
        reply_markup=kb([
            [("🎡 مراکز تفریحی", "g|prjs|fun")],
            [("🔬 مراکز علمی", "g|prjs|science")],
            [("🏢 احداث شرکت", "g|prjc")],
            back_row("g|mg"),
        ]),
    )


@router.callback_query(F.data.startswith("g|prjs|"))
async def project_list(call: CallbackQuery):
    sector = call.data.split("|")[2]
    title = "🎡 مراکز تفریحی" if sector == "fun" else "🔬 مراکز علمی"
    buildings = await db.fetchall(
        "SELECT * FROM buildings WHERE sector=? AND is_active=1 ORDER BY cost_money", (sector,))
    lines = [f"<b>{title}</b>\n", "نام پروژه را بعداً از شما می‌پرسیم؛ خبر احداث در کانال اعلام می‌شود.\n"]
    rows = []
    for b in buildings:
        cost = f"🪙 {fmt(b['cost_coins'])} سکه" if b["cost_coins"] else f"💰 {fmt_money(b['cost_money'])}"
        dur = f" | ⏱ {fmt_hm(b['duration_hours'])} ساخت" if b["duration_hours"] else ""
        req = f"\n   🔒 {b['requires_text']}" if b["requires_text"] else ""
        lines.append(f"{b['emoji']} {b['name']}: {cost}{dur}{req}")
        rows.append([(f"{b['emoji']} {b['name']}", f"g|prjbuy|{b['id']}")])
    rows.append(back_row("g|prj"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|prjbuy|"))
async def project_buy(call: CallbackQuery, state: FSMContext):
    bid = int(call.data.split("|")[2])
    b = await db.fetchone("SELECT * FROM buildings WHERE id=?", (bid,))
    if not b:
        return await call.answer("یافت نشد", show_alert=True)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if b["cost_coins"] and user["royal_coins"] < b["cost_coins"]:
        return await call.answer("❌ سکه شاهی کافی ندارید", show_alert=True)
    if b["cost_money"] and user["money"] < b["cost_money"]:
        return await call.answer("❌ بودجه کافی ندارید", show_alert=True)
    await state.set_state(ProjectFSM.name)
    await state.update_data(building_id=bid)
    await call.answer()
    await call.message.edit_text(
        f"{b['emoji']} <b>{b['name']}</b>\n\n📝 لطفاً <b>نام</b> پروژه را بنویسید "
        "(مثلاً نام برج، موزه یا موجود شما):\n برای انصراف /cancel"
    )


@router.message(ProjectFSM.name)
async def project_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or len(name) > 40:
        return await send_home(message, "❌ نام باید بین ۱ تا ۴۰ حرف باشد.")
    data = await state.get_data()
    b = await db.fetchone("SELECT * FROM buildings WHERE id=?", (data["building_id"],))
    if b and b["name"] == "برج ملی":
        await state.set_state(ProjectFSM.height)
        await state.update_data(prj_name=name)
        return await send_home(message, 
            "🗼 ارتفاع برج را به متر بنویسید (۱۰۰ تا ۱۰۰۰):\n"
            "💡 هر متر ارتفاع ۴ میلیون هزینه اضافه دارد."
        )
    await state.clear()
    await create_project(message, b, name, height=None)


@router.message(ProjectFSM.height)
async def project_height(message: Message, state: FSMContext):
    try:
        height = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ لطفاً عدد (متر) بفرستید.")
    if not 100 <= height <= 1000:
        return await send_home(message, "❌ ارتفاع باید بین ۱۰۰ تا ۱۰۰۰ متر باشد.")
    data = await state.get_data()
    b = await db.fetchone("SELECT * FROM buildings WHERE id=?", (data["building_id"],))
    await state.clear()
    await create_project(message, b, data["prj_name"], height)


async def create_project(message: Message, b: dict, name: str, height: int | None):
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (message.from_user.id,))
    state = await db.fetchone("SELECT * FROM states WHERE user_id=?", (message.from_user.id,))
    mat_cost = 150
    if (state or {}).get("materials", 0) < mat_cost:
        return await send_home(
            message,
            f"❌ <b>مصالح ساختمانی کافی ندارید!</b>\n"
            f"برای اجرای پروژه ملی به <b>{mat_cost}</b> واحد مصالح نیاز است.\n"
            f"موجودی فعلی شما: <b>{(state or {}).get('materials', 0)}</b> واحد.\n"
            "می‌توانید با احداث «شرکت مصالح‌سازی» روزانه مصالح بسازید یا از کشورهای دیگر خریداری کنید."
        )

    extra = (height or 0) * 4_000_000
    cost_money = (b["cost_money"] or 0) + extra
    if b["cost_coins"] and user["royal_coins"] < b["cost_coins"]:
        return await send_home(message, "❌ سکه شاهی کافی ندارید.")
    if cost_money and user["money"] < cost_money:
        return await send_home(message, f"❌ بودجه کافی نیست. نیاز: {fmt_money(cost_money)}")
    if b["cost_coins"]:
        await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?", (b["cost_coins"], user["id"]))
    if cost_money:
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost_money, user["id"]))

    # کسر مصالح ساختمانی و مصرف آب، برق و گاز مورد نیاز اجرای پروژه
    await db.execute(
        "UPDATE states SET materials=MAX(0,materials-?), energy=MAX(0,energy-300), "
        "water=MAX(0,water-300), gas=MAX(0,gas-200) WHERE user_id=?",
        (mat_cost, user["id"])
    )

    duration = b["duration_hours"] or 0.25
    await db.execute(
        "INSERT INTO player_projects(user_id, building_id, name, completes_at, cost_money, cost_coins) "
        "VALUES(?,?,?,?,?,?)",
        (user["id"], b["id"], name, add_hours(duration), cost_money, b["cost_coins"]),
    )
    await bump_progress(user["id"], "built")
    country = await db.fetchone(
        "SELECT c.* FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?", (user["id"],))
    height_txt = f" ({fmt(height)} متر)" if height else ""
    await announce(message.bot,
                   f"🏗 آغاز ساخت «{name}» ({b['name']}{height_txt}) در کشور {country['flag'] if country else ''} {country['name'] if country else ''}",
                   section="project")
    await send_home(message, 
        f"✅ ساخت «<b>{name}</b>» آغاز شد!\n"
        f"⏱ زمان ساخت: <b>{fmt_hm(duration)}</b>\n"
        f"🧱 مصالح مصرف‌شده: <b>{mat_cost}</b> واحد\n"
        f"💰 هزینه: {fmt_money(cost_money)}" + (f" + 🪙 {fmt(b['cost_coins'])} سکه" if b["cost_coins"] else "")
    )
    await projects_menu(_FakeCall(message))


class _FakeCall:
    def __init__(self, message: Message):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot

    async def answer(self, *_a, **_k):
        pass


# ─── احداث شرکت ───


@router.callback_query(F.data == "g|prjc")
async def company_types_menu(call: CallbackQuery):
    types = await db.fetchall("SELECT * FROM company_types WHERE is_active=1 ORDER BY base_income")
    # هر شرکت در یک سطر کامل و مجزا قرار می‌گیرد تا نام و درآمد کاملاً واضح و خوانا باشد
    rows = [[(f"🏢 {t['emoji']} {t['title']} | 💰 {fmt(t['base_income'])}/روز", f"g|prjct|{t['id']}")] for t in types]
    rows.append(back_row("g|prj"))
    await call.answer()
    await call.message.edit_text(
        "🏢 <b>احداث شرکت</b>\n\nنوع شرکت را انتخاب کنید. پس از انتخاب نام دلخواه، "
        "شرکت تاسیس و سود روزانه تولید می‌کند.\n\n"
        "🏗 <b>شرکت مصالح‌سازی:</b> روزانه علاوه بر درآمد، مصالح ساختمانی برای پروژه‌ها و سازه‌ها تولید می‌کند.",
        reply_markup=kb(rows),
    )


@router.callback_query(F.data.startswith("g|prjct|"))
async def company_buy(call: CallbackQuery, state: FSMContext):
    tid = int(call.data.split("|")[2])
    t = await db.fetchone("SELECT * FROM company_types WHERE id=?", (tid,))
    if not t:
        return await call.answer("یافت نشد", show_alert=True)
    # هزینه تأسیس = ۱۰ برابر درآمد روزانه
    cost = (t["base_income"] or 0) * 10
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if user["money"] < cost:
        return await call.answer(f"❌ بودجه کافی نیست — نیاز: {fmt_money(cost)}", show_alert=True)
    await state.set_state(ProjectFSM.company_name)
    await state.update_data(company_type=tid, cost=cost)
    await call.answer()
    await call.message.edit_text(
        f"{t['emoji']} <b>شرکت {t['title']}</b>\n\n💰 هزینه تأسیس: {fmt_money(cost)}\n"
        "📝 نام شرکت را بنویسید:\n برای انصراف /cancel"
    )


@router.message(ProjectFSM.company_name)
async def company_create(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or len(name) > 40:
        return await send_home(message, "❌ نام باید بین ۱ تا ۴۰ حرف باشد.")
    data = await state.get_data()
    t = await db.fetchone("SELECT * FROM company_types WHERE id=?", (data["company_type"],))
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (message.from_user.id,))
    if user["money"] < data["cost"]:
        await state.clear()
        return await send_home(message, "❌ بودجه کافی نیست.")
    await state.clear()
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (data["cost"], user["id"]))
    await db.execute(
        "INSERT INTO companies(owner_id, type_id, name, income_daily, announced) VALUES(?,?,?,?,1)",
        (user["id"], t["id"], name, t["base_income"]),
    )
    country = await db.fetchone(
        "SELECT c.* FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?", (user["id"],))
    await announce(message.bot,
                   f"🏢 تاسیس شرکت «{name}» ({t['title']}) در کشور {country['flag'] if country else ''} {country['name'] if country else ''}",
                   section="project")
    await bump_progress(user["id"], "built")
    await send_home(message, 
        f"✅ شرکت «<b>{name}</b>» تاسیس شد!\n💰 درآمد روزانه: {fmt(t['base_income'])}\n"
        "از بخش «شرکت‌های من» درآمد را برداشت کنید."
    )
    await companies_menu(_FakeCall(message))


# ─── شرکت‌های من ───


@router.callback_query(F.data == "g|comp")
async def companies_menu(call: CallbackQuery):
    companies = await db.fetchall(
        "SELECT c.*, t.title, t.emoji, t.key FROM companies c "
        "JOIN company_types t ON t.id=c.type_id WHERE c.owner_id=? ORDER BY c.id",
        (call.from_user.id,),
    )
    if not companies:
        await call.answer()
        return await call.message.edit_text(
            "🏢 <b>شرکت‌های من</b>\n\nهنوز شرکتی ندارید. از «پروژه ملی ← احداث شرکت» یکی بسازید.",
            reply_markup=kb([back_row("g|mg")]),
        )
    lines = ["🏢 <b>شرکت‌های من</b>\n"]
    rows = []
    for c in companies:
        ready = not c["last_withdraw"] or hours_left(c["last_withdraw"]) <= 0
        status = "✅" if ready else f"⏳ {fmt_hm(hours_left(c['last_withdraw']))}"
        lines.append(f"{c['emoji']} {c['name']} ({c['title']}) — درآمد {fmt(c['income_daily'])} {status}")
        rows.append([(f"{c['emoji']} {c['name']}", f"g|compv|{c['id']}")])
    rows.append(back_row("g|mg"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|compv|"))
async def company_view(call: CallbackQuery):
    cid = int(call.data.split("|")[2])
    c = await db.fetchone(
        "SELECT c.*, t.title, t.emoji, t.key FROM companies c "
        "JOIN company_types t ON t.id=c.type_id WHERE c.id=? AND c.owner_id=?",
        (cid, call.from_user.id),
    )
    if not c:
        return await call.answer("یافت نشد", show_alert=True)
    sell_price = (c["income_daily"] or 0) * 30
    materials = ""
    if c["key"] == "materials":
        qty = await db.fetchone(
            "SELECT quantity FROM player_assets WHERE user_id=? AND item_type='material' AND item_id=?",
            (call.from_user.id, c["id"]))
        materials = f"\n🧱 مصالح انباشته: {fmt(qty['quantity'] if qty else 0)}"
    await call.answer()
    await call.message.edit_text(
        f"{c['emoji']} <b>{c['name']}</b>\n"
        f"نوع: {c['title']}\n"
        f"💰 درآمد روزانه: {fmt(c['income_daily'])}\n"
        f"📅 تاسیس: {c['founded_at'][:10]}{materials}\n"
        f"💵 ارزش فروش به دولت: {fmt(sell_price)}",
        reply_markup=kb([
            [("💰 برداشت درآمد", f"g|compwd|{cid}")],
            [("💸 فروش شرکت به دولت", f"g|compsell|{cid}")],
            back_row("g|comp"),
        ]),
    )


@router.callback_query(F.data.startswith("g|compwd|"))
async def company_withdraw(call: CallbackQuery):
    cid = int(call.data.split("|")[2])
    c = await db.fetchone(
        "SELECT c.*, t.key FROM companies c JOIN company_types t ON t.id=c.type_id "
        "WHERE c.id=? AND c.owner_id=?", (cid, call.from_user.id))
    if not c:
        return await call.answer("یافت نشد", show_alert=True)
    if c["last_withdraw"] and hours_left(c["last_withdraw"]) > 0:
        return await call.answer(f"⏳ {fmt_hm(hours_left(c['last_withdraw']))} دیگر", show_alert=True)
    income = c["income_daily"] or 0
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (income, call.from_user.id))
    await db.execute("UPDATE companies SET last_withdraw=? WHERE id=?", (iso(), cid))
    msg = f"✅ درآمد روزانه شرکت «{c['name']}» به مبلغ {fmt(income)} برداشت شد."
    if c["key"] == "materials":
        produced = income // 1000
        await db.execute(
            "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?, 'material', ?, ?) "
            "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
            (call.from_user.id, cid, produced, produced),
        )
        msg += f"\n🧱 {fmt(produced)} واحد مصالح ساختمانی هم تولید شد."
    await call.answer("✅ برداشت شد")
    await send_home(call.message, msg)
    await company_view(call)


@router.callback_query(F.data.startswith("g|compsell|"))
async def company_sell(call: CallbackQuery):
    cid = int(call.data.split("|")[2])
    c = await db.fetchone(
        "SELECT c.*, t.title FROM companies c JOIN company_types t ON t.id=c.type_id "
        "WHERE c.id=? AND c.owner_id=?", (cid, call.from_user.id))
    if not c:
        return await call.answer("یافت نشد", show_alert=True)
    price = (c["income_daily"] or 0) * 30
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (price, call.from_user.id))
    await db.execute("DELETE FROM companies WHERE id=?", (cid,))
    await call.answer("💸 فروخته شد")
    await send_home(call.message, f"💸 شرکت «{c['name']}» به دولت فروخته شد — {fmt_money(price)} به خزانه اضافه شد.")
    await companies_menu(call)

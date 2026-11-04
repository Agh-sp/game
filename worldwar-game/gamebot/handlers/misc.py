"""ماموریت روزانه، سکه شاهی و پشتیبانی."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import bump_progress, get_progress
from core.utils import fmt, day_str, iso, tehran
from gamebot.common import back_row, kb, main_menu_kb, send_home

router = Router()


class CoinFSM(StatesGroup):
    amount = State()


class SupFSM(StatesGroup):
    text = State()
    photo = State()


# ─── ماموریت روزانه ───


@router.callback_query(F.data == "g|mis")
async def missions_menu(call: CallbackQuery):
    missions = await db.fetchall("SELECT * FROM missions WHERE is_active=1 ORDER BY id")
    progress = await get_progress(call.from_user.id)
    day = day_str()
    lines = ["🎯 <b>ماموریت روزانه</b>\n"]
    rows = []
    for m in missions:
        claimed = await db.fetchone(
            "SELECT 1 FROM mission_claims WHERE user_id=? AND mission_id=? AND day=?",
            (call.from_user.id, m["id"], day))
        current = int(progress.get(m["target_type"] or "login", 0))
        done = current >= (m["target_value"] or 1)
        rewards = []
        if m["reward_money"]:
            rewards.append(f"💰 {fmt(m['reward_money'])}")
        if m["reward_coins"]:
            rewards.append(f"🪙 {fmt(m['reward_coins'])}")
        status = "✅ گرفته شده" if claimed else ("🟢 آماده" if done else f"⚙️ {fmt(current)}/{fmt(m['target_value'])}")
        lines.append(
            f"{'🎯' if not claimed else '☑'} <b>{m['title']}</b>\n"
            f"   {m['description']}\n   پاداش: {' + '.join(rewards)} | {status}")
        if not claimed:
            rows.append([(f"{'🎁' if done else '⏳'} {m['title']}", f"g|misc|{m['id']}")])
    rows.append(back_row("g|main"))
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|misc|"))
async def mission_claim(call: CallbackQuery):
    mid = int(call.data.split("|")[2])
    m = await db.fetchone("SELECT * FROM missions WHERE id=? AND is_active=1", (mid,))
    if not m:
        return await call.answer("یافت نشد", show_alert=True)
    day = day_str()
    claimed = await db.fetchone(
        "SELECT 1 FROM mission_claims WHERE user_id=? AND mission_id=? AND day=?",
        (call.from_user.id, mid, day))
    if claimed:
        return await call.answer("قبلاً گرفته‌اید!", show_alert=True)
    progress = await get_progress(call.from_user.id)
    current = int(progress.get(m["target_type"] or "login", 0))
    if current < (m["target_value"] or 1):
        return await call.answer(
            f"⏳ هنوز کامل نشده — {fmt(current)}/{fmt(m['target_value'])}", show_alert=True)
    await db.execute(
        "INSERT INTO mission_claims(user_id, mission_id, day) VALUES(?,?,?)",
        (call.from_user.id, mid, day))
    if m["reward_money"]:
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (m["reward_money"], call.from_user.id))
    if m["reward_coins"]:
        await db.execute("UPDATE users SET royal_coins=royal_coins+? WHERE id=?",
                         (m["reward_coins"], call.from_user.id))
    await call.answer("🎁 پاداش گرفته شد!")
    await missions_menu(call)


# ─── سکه شاهی ───


@router.callback_query(F.data == "g|coin")
async def coins_menu(call: CallbackQuery):
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    price = int(await get_setting("coin_price_toman", "1000"))
    rate = int(await get_setting("coins_to_money_rate", "5000000"))
    card = await get_setting("c2c_card", "—")
    holder = await get_setting("c2c_holder", "—")
    packages = await db.fetchall("SELECT * FROM coin_packages WHERE is_active=1 ORDER BY coins")
    pkg_lines = "\n".join(
        f"📦 {fmt(p['coins'])} سکه — {fmt(p['price_toman'])} تومان"
        + (f" (تخفیف {round(p['discount_percent'])}٪)" if p["discount_percent"] else "")
        for p in packages)
    await call.answer()
    await call.message.edit_text(
        f"🪙 <b>سکه شاهی</b>\n\n"
        f"موجودی شما: <b>{fmt(user['royal_coins'])} سکه</b>\n"
        f"💵 قیمت هر سکه: <b>{fmt(price)} تومان</b>\n"
        f"🔄 نرخ تبدیل به پول پایه: هر سکه = {fmt(rate)}\n\n"
        f"💳 کارت به کارت:\n<code>{card}</code>\n👤 {holder}\n\n{pkg_lines}\n\n"
        "سکه شاهی برای: کشورهای ویژه، تجهیزات فضایی و ساختمان‌های خاص.",
        reply_markup=kb([
            [("🛒 خرید سکه (سفارشی)", "g|coinbuy")],
            [("📦 خرید پکیج", "g|coinpkg")],
            [("🔄 تبدیل به پول پایه", "g|coinconv")],
            [("🧾 فیش‌های من", "g|coinhist")],
            back_row("g|main"),
        ]),
    )


@router.callback_query(F.data == "g|coinbuy")
async def coins_buy(call: CallbackQuery, state: FSMContext):
    await state.set_state(CoinFSM.amount)
    await state.update_data(mode="buy")
    price = int(await get_setting("coin_price_toman", "1000"))
    await call.answer()
    await call.message.edit_text(
        f"🛒 <b>خرید سکه شاهی</b>\n\n💵 قیمت هر سکه: <b>{fmt(price)} تومان</b>\n\n"
        "تعداد سکه مورد نظر را بنویسید (هر تعدادی که بخواهید):\n برای انصراف /cancel"
    )


@router.callback_query(F.data == "g|coinpkg")
async def coins_packages(call: CallbackQuery):
    packages = await db.fetchall("SELECT * FROM coin_packages WHERE is_active=1 ORDER BY coins")
    rows = [[(f"📦 {fmt(p['coins'])} سکه — {fmt(p['price_toman'])} تومان", f"g|coinpkgo|{p['id']}")]
            for p in packages]
    rows.append(back_row("g|coin"))
    await call.answer()
    await call.message.edit_text("📦 <b>پکیج‌های سکه شاهی</b>\nپکیج را انتخاب کنید:", reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|coinpkgo|"))
async def package_receipt_flow(call: CallbackQuery, state: FSMContext):
    pid = int(call.data.split("|")[2])
    p = await db.fetchone("SELECT * FROM coin_packages WHERE id=? AND is_active=1", (pid,))
    if not p:
        return await call.answer("یافت نشد", show_alert=True)
    from gamebot.handlers.start import CashFSM
    card = await get_setting("c2c_card", "—")
    holder = await get_setting("c2c_holder", "—")
    await state.set_state(CashFSM.photo)
    await state.update_data(kind="coins", coins=p["coins"], toman=p["price_toman"])
    await call.answer()
    await call.message.edit_text(
        f"📦 <b>پکیج {fmt(p['coins'])} سکه شاهی</b>\n\n"
        f"💰 مبلغ قابل پرداخت: <b>{fmt(p['price_toman'])} تومان</b>\n"
        f"💳 شماره کارت: <code>{card}</code>\n👤 به نام: {holder}\n\n"
        "مبلغ را کارت به کارت کنید و <b>عکس فیش</b> را ارسال کنید.\n"
        "پس از تأیید ادمین سکه‌ها اضافه می‌شوند.\n برای انصراف /cancel",
        reply_markup=kb([[("❌ انصراف", "g|cancel")]]),
    )


@router.message(CoinFSM.amount)
async def coins_amount_input(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
    except (ValueError, TypeError):
        return await send_home(message, "❌ فقط عدد بفرستید.")
    if amount <= 0 or amount > 1_000_000:
        return await send_home(message, "❌ عدد باید بین ۱ تا ۱میلیون باشد.")
    data = await state.get_data()
    if data.get("mode") == "buy":
        price = int(await get_setting("coin_price_toman", "1000"))
        total = amount * price
        card = await get_setting("c2c_card", "—")
        holder = await get_setting("c2c_holder", "—")
        from gamebot.handlers.start import CashFSM
        await state.set_state(CashFSM.photo)
        await state.update_data(kind="coins", coins=amount, toman=total)
        await send_home(message, 
            f"🛒 سفارش <b>{fmt(amount)} سکه شاهی</b>\n\n"
            f"💰 مبلغ قابل پرداخت: <b>{fmt(total)} تومان</b>\n"
            f"💳 شماره کارت: <code>{card}</code>\n👤 به نام: {holder}\n\n"
            "مبلغ را کارت به کارت کنید و <b>عکس فیش</b> را ارسال کنید.\n"
            "پس از تأیید ادمین سکه‌ها اضافه می‌شوند.\n برای انصراف /cancel",
            reply_markup=kb([[("❌ انصراف", "g|cancel")]]),
        )
    else:  # تبدیل به پول پایه
        rate = int(await get_setting("coins_to_money_rate", "5000000"))
        user = await db.fetchone("SELECT * FROM users WHERE id=?", (message.from_user.id,))
        if user["royal_coins"] < amount:
            await state.clear()
            return await send_home(message, f"❌ سکه کافی ندارید — موجودی: {fmt(user['royal_coins'])}")
        await state.clear()
        await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?", (amount, message.from_user.id))
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (amount * rate, message.from_user.id))
        await send_home(message, 
            f"✅ <b>{fmt(amount)} سکه شاهی</b> به <b>{fmt(amount * rate)}</b> پول پایه تبدیل شد.")


@router.callback_query(F.data == "g|coinconv")
async def coins_convert(call: CallbackQuery, state: FSMContext):
    await state.set_state(CoinFSM.amount)
    await state.update_data(mode="convert")
    rate = int(await get_setting("coins_to_money_rate", "5000000"))
    await call.answer()
    await call.message.edit_text(
        f"🔄 <b>تبدیل سکه شاهی به پول پایه</b>\n\nنرخ فعلی: هر سکه = <b>{fmt(rate)}</b>\n\n"
        "تعداد سکه برای تبدیل را بنویسید:\n برای انصراف /cancel"
    )


@router.callback_query(F.data == "g|coinhist")
async def coins_history(call: CallbackQuery):
    receipts = await db.fetchall(
        "SELECT * FROM receipts WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,))
    if not receipts:
        await call.answer()
        return await call.message.edit_text("🧾 فیشی ندارید.", reply_markup=kb([back_row("g|coin")]))
    lines = ["🧾 <b>فیش‌های من</b>\n"]
    for r in receipts:
        status = {"pending": "⏳ در انتظار", "approved": "✅ تأیید شد", "rejected": "❌ رد شد"}[r["status"]]
        what = (f"کشور (#{r['country_id']})" if r["kind"] == "country" else f"{fmt(r['coins'])} سکه")
        lines.append(f"#{r['id']} — {what} — {fmt(r['toman'])} تومان — {status} — {tehran(r['created_at'])}")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([back_row("g|coin")]))


# ─── پشتیبانی ───


SUP_KINDS = {"complaint": "😠 شکایت از کشور دیگر", "idea": "💡 ارسال ایده", "bug": "🐞 گزارش باگ و ارور"}


@router.callback_query(F.data == "g|sup")
def support_rows() -> list:
    rows = [[(title, f"g|sup|{key}")] for key, title in SUP_KINDS.items()]
    rows.append([("🧾 تیکت‌های من", "g|suphist")])
    rows.append(back_row("g|main"))
    return rows


async def support_menu(call: CallbackQuery):
    rows = support_rows()
    await call.answer()
    await call.message.edit_text(
        "🛟 <b>پشتیبانی</b>\n\nیکی از موارد را انتخاب کنید:", reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|sup|"))
async def support_kind(call: CallbackQuery, state: FSMContext):
    kind = call.data.split("|")[2]
    if kind not in SUP_KINDS:
        return await call.answer("یافت نشد", show_alert=True)
    await state.set_state(SupFSM.text)
    await state.update_data(sup_kind=kind)
    await call.answer()
    await call.message.edit_text(
        f"{SUP_KINDS[kind]}\n\nمورد خود را کامل توضیح بدهید:\n برای انصراف /cancel"
    )


@router.message(SupFSM.text)
async def support_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 1500:
        return await send_home(message, "❌ متن باید بین ۱ تا ۱۵۰۰ حرف باشد.")
    await state.update_data(sup_text=text)
    await state.set_state(SupFSM.photo)
    await send_home(message, 
        "📎 اگر عکس مرتبط دارید ارسال کنید، وگرنه دکمه زیر را بزنید:",
        reply_markup=kb([[("⏭ بدون عکس ثبت کن", "g|supok")]]),
    )


@router.message(SupFSM.photo, F.photo)
async def support_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await db.execute(
        "INSERT INTO tickets(user_id, kind, text, photo_file_id) VALUES(?,?,?,?)",
        (message.from_user.id, data["sup_kind"], data["sup_text"], message.photo[-1].file_id))
    await send_home(
        message,
        "✅ تیکت شما ثبت شد و برای پشتیبانی ارسال شد. پاسخ به‌زودی دریافت می‌کنید. 🙏\n\n"
        "🛟 <b>پشتیبانی</b>",
        reply_markup=kb(support_rows()),
    )


@router.message(SupFSM.photo)
async def support_photo_invalid(message: Message):
    await send_home(message, "📸 لطفاً عکس بفرستید یا «بدون عکس ثبت کن» را بزنید.")


@router.callback_query(F.data == "g|supok")
async def support_no_photo(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await db.execute(
        "INSERT INTO tickets(user_id, kind, text) VALUES(?,?,?)",
        (call.from_user.id, data["sup_kind"], data["sup_text"]))
    await call.answer("✅ ثبت شد")
    await call.message.edit_text("✅ تیکت شما ثبت شد و برای پشتیبانی ارسال شد. پاسخ به‌زودی دریافت می‌کنید. 🙏")
    await support_menu(call)


@router.callback_query(F.data == "g|suphist")
async def support_history(call: CallbackQuery):
    tickets = await db.fetchall(
        "SELECT * FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,))
    if not tickets:
        await call.answer()
        return await call.message.edit_text("🧾 تیکتی ندارید.", reply_markup=kb([back_row("g|sup")]))
    lines = ["🧾 <b>تیکت‌های من</b>\n"]
    for t in tickets:
        status = {"open": "⏳ باز", "answered": "✅ پاسخ داده شد", "closed": "🔒 بسته"}[t["status"]]
        lines.append(f"#{t['id']} {SUP_KINDS.get(t['kind'], t['kind'])} — {status} — {tehran(t['created_at'])}")
        if t["reply"]:
            lines.append(f"   💬 پاسخ: {t['reply'][:200]}")
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb([back_row("g|sup")]))


# ─── عکس بدون سفارش فعال ───


@router.message(F.photo)
async def photo_without_order(message: Message, state: FSMContext):
    """اگر بازیکن خارج از هر مرحله‌ای عکس (فیش) بفرستد، راهنمایی شود نه اینکه پیامش نادیده بماند."""
    await state.clear()
    await send_home(
        message,
        "📸 عکس شما دریافت شد، اما هیچ سفارش فعالی برای ثبت فیش پیدا نشد.\n\n"
        "برای ثبت فیش: 🪙 <b>سکه شاهی</b> → خرید سکه/پکیج → سپس عکس فیش را بفرستید.\n"
        "برای خرید کشور هم از 🏳 <b>کشورهای ویژه</b> → پرداخت با پول واقعی اقدام کنید.",
        reply_markup=main_menu_kb(),
    )

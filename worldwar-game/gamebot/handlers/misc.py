"""ماموریت روزانه، سکه شاهی و پشتیبانی."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_setting
from core.economy import bump_progress, get_progress
from core.utils import fmt, fmt_money, day_str, iso, tehran
from gamebot.common import back_row, kb, main_menu_kb, send_home

router = Router()


class CoinFSM(StatesGroup):
    amount = State()
    sell = State()


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
            rewards.append(f"💰 {fmt_money(m['reward_money'])}")
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


async def sales_support() -> str:
    """آیدی پشتیبانی فروش سکه (از تنظیمات ادمین یا کانفیگ)."""
    from core import config as cfg
    return (await get_setting("sales_support", "") or cfg.SALES_SUPPORT).strip()


async def coin_packages_text() -> str:
    """فهرست قیمت پکیج‌های سکه شاهی."""
    packages = await db.fetchall("SELECT * FROM coin_packages WHERE is_active=1 ORDER BY coins")
    if not packages:
        return "📦 در حال حاضر پکیجی تعریف نشده است."
    return "\n".join(
        f"📦 {fmt(p['coins'])} سکه — {fmt(p['price_toman'])} تومان"
        + (f" (تخفیف {round(p['discount_percent'])}٪)" if p["discount_percent"] else "")
        for p in packages)


async def sell_rate() -> int:
    """مبلغ پول پایه‌ای که بابت فروش هر یک سکه شاهی به بازیکن داده می‌شود."""
    try:
        rate = int(float(await get_setting("coin_sell_rate", "0")))
    except (TypeError, ValueError):
        rate = 0
    if rate <= 0:
        # اگر تنظیم نشده بود، از نرخ تبدیل داخلی استفاده کن
        try:
            rate = int(float(await get_setting("coins_to_money_rate", "5000000")))
        except (TypeError, ValueError):
            rate = 5_000_000
    return max(1_000_000, rate)


async def coin_shop_text(user: dict | None = None, *, include_sell: bool = True) -> str:
    """متن فروشگاه سکه شاهی — قیمت‌ها، آیدی پشتیبانی و نرخ فروش سکه."""
    support = await sales_support()
    handle = support if support.startswith("@") else f"@{support}"
    link = f"https://t.me/{handle.lstrip('@')}"
    lines = ["🪙 <b>سکه شاهی</b>", ""]
    if user:
        lines += [f"موجودی شما: <b>{fmt(user['royal_coins'])} سکه</b>", ""]
    lines += [await coin_packages_text(), ""]
    lines += [f"🛒 برای خرید به {handle} پیام بدید:", f'<a href="{link}">{handle}</a>']
    if include_sell:
        rate = await sell_rate()
        lines += ["", "💱 <b>فروش سکه به بازی</b>",
                  f"هر سکه = <b>{fmt_money(rate)}</b> پول پایه",
                  "با دکمهٔ «💰 فروش سکه» می‌توانید سکه‌هایتان را یکی‌یکی بفروشید."]
    lines.append("")
    lines.append("💡 سکه شاهی برای: کشورهای ویژه، تجهیزات فضایی و ساختمان‌های خاص.")
    return "\n".join(lines)


def coin_menu_rows() -> list:
    """دکمه‌های بخش سکه شاهی (خرید از پشتیبانی + فروش سکه)."""
    return [
        [("💰 فروش سکه", "g|coinsell")],
        [("💱 تبدیل به پول پایه", "g|coinconv")],
    ]


@router.callback_query(F.data == "g|coin")
async def coins_menu(call: CallbackQuery):
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    await call.answer()
    await call.message.edit_text(await coin_shop_text(user),
                                 reply_markup=kb(coin_menu_rows()))


@router.callback_query(F.data.in_({"g|coinbuy", "g|coinpkg"}))
async def coins_buy_redirect(call: CallbackQuery):
    """خرید سکه فقط از طریق پشتیبانی انجام می‌شود (کارت به کارت حذف شد)."""
    await call.answer()
    await call.message.edit_text(await coin_shop_text(), reply_markup=kb(coin_menu_rows()))


# ─── فروش سکه شاهی (دونه‌ای) ───


async def _sell_coins(user_id: int, amount: int) -> tuple[bool, str]:
    """فروش `amount` سکه به بازی و افزودن پول پایه به خزانه."""
    rate = await sell_rate()
    user = await db.fetchone("SELECT royal_coins, money FROM users WHERE id=?", (user_id,))
    if not user:
        return False, "❌ کاربر یافت نشد."
    have = int(user["royal_coins"] or 0)
    if have < amount:
        return False, (f"❌ سکه کافی ندارید.\n🪙 موجودی شما: <b>{fmt(have)}</b> سکه\n"
                       f"درخواست: {fmt(amount)} سکه")
    gain = rate * amount
    await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?",
                     (amount, user_id))
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (gain, user_id))
    try:
        await db.execute(
            "INSERT INTO coin_sales(user_id, coins, rate, gain) VALUES(?,?,?,?)",
            (user_id, amount, rate, gain))
    except Exception:
        pass
    new_coins = have - amount
    new_money = int(user["money"] or 0) + gain
    return True, (
        f"✅ <b>{fmt(amount)} سکه شاهی فروخته شد</b>\n\n"
        f"💵 دریافتی: <b>{fmt_money(gain)}</b> پول پایه\n"
        f"📊 نرخ: هر سکه {fmt_money(rate)}\n\n"
        f"🪙 موجودی سکه: <b>{fmt(new_coins)}</b>\n"
        f"💰 خزانه: <b>{fmt_money(new_money)}</b>")


@router.callback_query(F.data == "g|coinsell")
async def coins_sell_menu(call: CallbackQuery):
    """منوی فروش سکه: فروش دونه‌ای یا تعداد دلخواه."""
    user = await db.fetchone("SELECT royal_coins FROM users WHERE id=?",
                             (call.from_user.id,))
    have = int((user or {}).get("royal_coins") or 0)
    rate = await sell_rate()
    await call.answer()
    if have <= 0:
        return await call.message.edit_text(
            "💰 <b>فروش سکه شاهی</b>\n\n"
            "❌ شما هیچ سکه شاهی ندارید.\n"
            f"💡 هر سکه {fmt_money(rate)} پول پایه می‌ارزد — "
            "اول از پشتیبانی سکه بخرید.",
            reply_markup=kb([[('🛒 خرید سکه', "g|coin")],
                             back_row("g|coin", "◀️ بازگشت")]))
    text = (
        f"💰 <b>فروش سکه شاهی</b>\n\n"
        f"🪙 موجودی شما: <b>{fmt(have)}</b> سکه\n"
        f"💱 نرخ فروش هر سکه: <b>{fmt_money(rate)}</b>\n"
        f"📈 اگر همهٔ سکه‌هایتان را بفروشید: <b>{fmt_money(rate * have)}</b>\n\n"
        "چه تعداد سکه می‌خواهید بفروشید؟"
    )
    rows = [
        [("1️⃣ فروش ۱ سکه", "g|coinselln|1"),
         ("5️⃣ فروش ۵ سکه", "g|coinselln|5")],
        [("🔟 فروش ۱۰ سکه", "g|coinselln|10"),
         ("📦 فروش ۵۰ سکه", "g|coinselln|50")],
        [("✍️ تعداد دلخواه", "g|coinsellq")],
    ]
    if have > 50:
        rows.insert(2, [("💯 فروش ۱۰۰ سکه", "g|coinselln|100"),
                        (f"🏦 فروش همه ({fmt(have)})", f"g|coinselln|{have}")])
    rows.append(back_row("g|coin", "◀️ بازگشت"))
    await call.message.edit_text(text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|coinselln|"))
async def coins_sell_amount(call: CallbackQuery):
    amount = int(call.data.split("|")[2])
    ok, msg = await _sell_coins(call.from_user.id, amount)
    if not ok:
        return await call.answer(msg[:190], show_alert=True)
    await call.answer(f"✅ {fmt(amount)} سکه فروخته شد")
    await call.message.edit_text(msg, reply_markup=kb([
        [("💰 فروش سکهٔ دیگر", "g|coinsell")],
        back_row("g|coin", "◀️ بخش سکه شاهی"),
    ]))


@router.callback_query(F.data == "g|coinsellq")
async def coins_sell_prompt(call: CallbackQuery, state: FSMContext):
    user = await db.fetchone("SELECT royal_coins FROM users WHERE id=?",
                             (call.from_user.id,))
    have = int((user or {}).get("royal_coins") or 0)
    await state.set_state(CoinFSM.sell)
    await call.answer()
    await call.message.edit_text(
        f"✍️ <b>فروش تعداد دلخواه سکه</b>\n\n"
        f"🪙 موجودی شما: <b>{fmt(have)}</b> سکه\n"
        f"💱 هر سکه: <b>{fmt_money(await sell_rate())}</b>\n\n"
        "تعداد سکه‌ای که می‌خواهید بفروشید را بنویسید:\n"
        "برای انصراف /cancel",
        reply_markup=kb([back_row("g|coinsell", "◀️ بازگشت")]))


@router.message(CoinFSM.sell)
async def coins_sell_input(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace(",", "").replace("٬", "")
    try:
        amount = int(raw)
    except (TypeError, ValueError):
        return await send_home(message, "❌ لطفاً فقط عدد بفرستید.")
    if amount <= 0:
        return await send_home(message, "❌ تعداد باید بیشتر از صفر باشد.")
    await state.clear()
    ok, msg = await _sell_coins(message.from_user.id, amount)
    await send_home(message, msg, reply_markup=kb([
        [("💰 فروش سکهٔ دیگر", "g|coinsell")],
        back_row("g|coin", "◀️ بخش سکه شاهی"),
    ]))


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
        # خرید کارت به کارت حذف شده است — فقط پشتیبانی
        await state.clear()
        await send_home(message, await coin_shop_text())
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


@router.callback_query(F.data.in_({"g|coinconv", "g|coinhist"}))
async def coins_removed(call: CallbackQuery):
    """بخش‌های تبدیل و فیش از منوی سکه شاهی حذف شده‌اند."""
    await call.answer("این بخش در دسترس نیست", show_alert=False)
    await call.message.edit_text(await coin_shop_text(), reply_markup=kb([]))


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
        reply_markup=await main_menu_kb(),
    )

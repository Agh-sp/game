"""شروع بازی: عضویت اجباری، انتخاب کشور و خرید کشور (سکه شاهی / فیش)."""
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.db import db, get_initial_money, get_setting
from core.economy import bump_progress, get_state
from core.utils import fmt, fmt_hm, iso
from core.provinces import BASE_PROVINCES, ensure_country_provinces
from gamebot.common import check_membership, join_keyboard, kb, main_menu_kb, send_home

router = Router()
PAGE_SIZE = 8


class CashFSM(StatesGroup):
    photo = State()


# ─── استارت ───


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    await db.execute(
        "INSERT OR IGNORE INTO users(id, username, full_name, money) VALUES(?,?,?,?)",
        (user.id, user.username or "", user.full_name or "", await get_initial_money()),
    )
    await db.execute("UPDATE users SET username=?, full_name=? WHERE id=?",
                     (user.username or "", user.full_name or "", user.id))
    if await get_setting("bot_off", "0") == "1":
        return await send_home(message, "🔴 بازی موقتاً خاموش است. کمی بعد دوباره امتحان کنید.")
    row = await db.fetchone("SELECT * FROM users WHERE id=?", (user.id,))
    if row["banned"]:
        return await send_home(message, "⛔️ شما از بازی اخراج شده‌اید.")
    if not await check_membership(message.bot, user.id):
        text = await get_setting("start_text", "")
        if not text:
            text = (
                "🌍 <b>به بازی «جنگ جهانی ۳» خوش آمدید!</b>\n\n"
                "برای ورود به بازی در گروه و کانال رسمی زیر عضو شوید و سپس دکمه «🔍 بررسی عضویت» را بزنید:\n"
                "👥 گپ بازی: @WordWarWord\n"
                "📢 کانال خبری: @Jangjhani313"
            )
        return await send_home(message, text, reply_markup=await join_keyboard())
    if row["country_id"]:
        await bump_progress(user.id, "login")
        is_admin = bool(await db.fetchone("SELECT id FROM admins WHERE id=?", (user.id,)))
        return await send_home(message, 
            f"🌍 به امپراطوری خود خوش آمدید، فرمانده! (جنگ جهانی ۳)",
            reply_markup=await main_menu_kb(is_admin),
        )
    await country_selection(message)


async def country_selection(message: Message, user_id: int | None = None):
    uid = user_id or (message.chat.id if getattr(message, "chat", None) else (message.from_user.id if getattr(message, "from_user", None) else 0))
    row = await db.fetchone("SELECT royal_coins c FROM users WHERE id=?", (uid,))
    coins = row["c"] if row else 0
    text = (
        "🌍 <b>انتخاب کشور</b>\n\n"
        "کشورهای دنیا را انتخاب کنید:\n"
        "• 🆓 <b>رایگان</b> — بلافاصله به شما داده می‌شود\n"
        "• 👑 <b>ویژه</b> — خرید با 🪙 سکه شاهی یا 💳 پول واقعی (فیش)\n\n"
        f"🪙 موجودی سکه شاهی شما: <b>{fmt(coins)}</b>"
    )
    await send_home(message, text, reply_markup=kb([
        [("🆓 کشورهای رایگان", "g|cnt|f|0")],
        [("👑 کشورهای ویژه", "g|cnt|s|0")],
    ]))


@router.callback_query(F.data == "g|chk")
async def on_check(call: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await check_membership(call.bot, call.from_user.id):
        return await call.answer("❌ هنوز عضو همه کانال‌ها نشده‌اید!", show_alert=True)
    await call.answer("✅ عضویت تأیید شد")
    row = await db.fetchone("SELECT country_id FROM users WHERE id=?", (call.from_user.id,))
    if row and row["country_id"]:
        await bump_progress(call.from_user.id, "login")
        await call.message.edit_text("🌍 به امپراطوری خود خوش آمدید، فرمانده! (جنگ جهانی ۳)", reply_markup=await main_menu_kb())
    else:
        await call.message.delete()
        await country_selection(call.message)


# ─── لیست کشورها ───


@router.callback_query(F.data.startswith("g|cnt|"))
async def country_list(call: CallbackQuery):
    _, _, mode, page = call.data.split("|")
    page = int(page)
    special = 1 if mode == "s" else 0
    total = (await db.fetchone(
        "SELECT COUNT(*) c FROM countries WHERE is_active=1 AND is_special=? AND owner_id IS NULL",
        (special,)))["c"]
    rows = await db.fetchall(
        "SELECT * FROM countries WHERE is_active=1 AND is_special=? AND owner_id IS NULL "
        "ORDER BY population DESC LIMIT ? OFFSET ?",
        (special, PAGE_SIZE, page * PAGE_SIZE),
    )
    title = "👑 کشورهای ویژه (پرداخت دار)" if special else "🆓 کشورهای رایگان"
    lines = [f"<b>{title}</b> — صفحه {page + 1} از {max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)}\n"]
    buttons = []
    for r in rows:
        price = f" — 🪙 {fmt(r['coin_price'])} سکه / 💳 {fmt(r['toman_price'])} تومان" if special else ""
        lines.append(f"{r['flag']} {r['name']} — 👥 {fmt(r['population'])}{price}")
        buttons.append([(f"{r['flag']} {r['name']}", f"g|cntc|{r['id']}")])
    if not rows:
        lines.append("— همه گرفته شده‌اند! —")
    nav = []
    if page > 0:
        nav.append(("‹ قبلی", f"g|cnt|{mode}|{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(("بعدی ›", f"g|cnt|{mode}|{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([("🗂 نوع کشور", "g|cntsel")])
    await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))


@router.callback_query(F.data == "g|cntsel")
async def country_mode_select(call: CallbackQuery):
    await call.message.edit_text("🌍 <b>انتخاب کشور</b>", reply_markup=kb([
        [("🆓 کشورهای رایگان", "g|cnt|f|0")],
        [("👑 کشورهای ویژه", "g|cnt|s|0")],
    ]))


# ─── کارت کشور و خرید ───


@router.callback_query(F.data.startswith("g|cntc|"))
async def country_card(call: CallbackQuery):
    cid = int(call.data.split("|")[2])
    c = await db.fetchone("SELECT * FROM countries WHERE id=?", (cid,))
    if not c or not c["is_active"]:
        return await call.answer("کشور یافت نشد", show_alert=True)
    if c["owner_id"]:
        return await call.answer("❌ این کشور همین الان گرفته شد!", show_alert=True)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    sea = "دارد ✅" if c["has_sea"] else "ندارد ❌"
    text = (
        f"{c['flag']} <b>{c['name']}</b>\n\n"
        f"👥 جمعیت: {fmt(c['population'])}\n"
        f"🌊 دسترسی به دریا: {sea}\n"
        f"🗺 منطقه: {c['region']}\n"
    )
    if c["is_special"]:
        text += (
            f"\n👑 <b>کشور ویژه</b>\n"
            f"🪙 قیمت با سکه شاهی: {fmt(c['coin_price'])}\n"
            f"💳 قیمت با پول واقعی: {fmt(c['toman_price'])} تومان\n"
            f" موجودی شما: 🪙 {fmt(user['royal_coins'])}"
        )
        rows = [
            [("🪙 خرید با سکه شاهی", f"g|cntcoin|{cid}")],
            [("💳 خرید با پول واقعی", f"g|cntcash|{cid}")],
            [("◀️ بازگشت", f"g|cnt|{'s' if c['is_special'] else 'f'}|0")],
        ]
    else:
        text += "\n🆓 این کشور <b>رایگان</b> است."
        rows = [
            [("✅ انتخاب این کشور", f"g|cnttake|{cid}")],
            [("◀️ بازگشت", f"g|cnt|f|0")],
        ]
    await call.message.edit_text(text, reply_markup=kb(rows))
    # 🏳 عکس واقعی پرچم: اول از فایل اختصاصی تلگرام، وگرنه لینک عکس واقعی باکیفیت FlagCDN
    try:
        from core.images import get_country_flag_photo
        flag_photo = await get_country_flag_photo(c)
        if flag_photo:
            await call.message.answer_photo(flag_photo, caption=f"🏳️ پرچم رسمی {c['name']} {c['flag']}")
    except Exception:
        pass


async def assign_country(user_id: int, country: dict, notify_text: str, bot=None) -> bool:
    """تخصیص کشور به کاربر (اگر آزاد باشد و حذف قطعی از لیست دیگران)."""
    cur = await db.fetchone("SELECT owner_id FROM countries WHERE id=?", (country["id"],))
    if not cur or cur["owner_id"]:
        return False
    rows = await db.execute(
        "UPDATE countries SET owner_id=?, collapsed=0, province_count=? "
        "WHERE id=? AND (owner_id IS NULL OR owner_id=0)",
        (user_id, BASE_PROVINCES, country["id"])
    )
    await db.execute("UPDATE users SET country_id=?, country_taken_at=? WHERE id=?",
                     (country["id"], iso(), user_id))
    await get_state(user_id)  # ساخت ردیف states
    # 🗺 استان‌های کشور فوراً به بازیکن داده می‌شوند (وگرنه تا راه‌اندازی بعدی
    #    «کشور شما سقوط کرده» نمایش داده می‌شد — باگ گزارش‌شده توسط کاربر)
    try:
        await ensure_country_provinces(country["id"], user_id, normalize=True)
    except Exception:
        pass
    currency = country.get("currency") or country["name"]
    await db.execute(
        "UPDATE states SET currency_name=?, materials=1000, energy=5000, water=5000, gas=5000 "
        "WHERE user_id=?",
        (currency, user_id)
    )
    # 📰 خبر عمومی در کانال: کشوری فرمانده پیدا کرد
    if bot:
        try:
            from core.config import GAME_NAME
            from core.economy import announce
            await announce(
                bot,
                f"🏳 <b>فرمانده جدید در {GAME_NAME}</b>\n\n"
                f"{country['flag']} کشور <b>{country['name']}</b> توسط یک فرمانده جدید "
                f"تحت کنترل گرفته شد.\n⏳ زمان حمله به آن آزاد است — سریع‌تر باشید!",
                section="flag",
            )
        except Exception:
            pass
    return True


async def reset_country_data(user_id: int) -> None:
    """ریست دارایی‌های وابسته به کشور (در تغییر کشور)."""
    await db.execute("DELETE FROM player_assets WHERE user_id=?", (user_id,))
    await db.execute("DELETE FROM player_projects WHERE user_id=?", (user_id,))
    await db.execute("DELETE FROM soldier_trainings WHERE user_id=?", (user_id,))
    await db.execute("DELETE FROM companies WHERE owner_id=?", (user_id,))
    await db.execute("DELETE FROM bases WHERE guest_id=? OR host_id=?", (user_id, user_id))
    await db.execute(
        "UPDATE states SET satisfaction=50, religion_id=NULL, government_id=NULL, chosen_laws='{}', "
        "subsidy_daily=0, tax_rate=0, blackout_power=0, blackout_water=0, blackout_gas=0, "
        "leader_block_until=NULL, server_jam_until=NULL, disarmed_until=NULL, trade_banned='[]', "
        "last_income=NULL, cyber_power=10000, oil_stock=0, energy=5000, water=5000, gas=5000, materials=1000, diplomacy=50 "
        "WHERE user_id=?",
        (user_id,),
    )


@router.callback_query(F.data.startswith("g|cnttake|"))
async def take_free(call: CallbackQuery):
    cid = int(call.data.split("|")[2])
    c = await db.fetchone("SELECT * FROM countries WHERE id=?", (cid,))
    if not c or c["owner_id"]:
        await call.answer("❌ این کشور پیش‌تر توسط بازیکن دیگری انتخاب شده است!", show_alert=True)
        return await country_mode_select(call)
    ok = await assign_country(call.from_user.id, c, "", bot=call.bot)
    if not ok:
        await call.answer("❌ این کشور قبلاً گرفته شده است!", show_alert=True)
        return await country_mode_select(call)
    await call.answer("🟢 کشور انتخاب شد")
    # هدایت فوری به تعیین نوع حکومت و دین
    await prompt_onboard_gov(call, c)


@router.callback_query(F.data.startswith("g|cntcoin|"))
async def buy_with_coins(call: CallbackQuery):
    cid = int(call.data.split("|")[2])
    c = await db.fetchone("SELECT * FROM countries WHERE id=?", (cid,))
    if not c or c["owner_id"]:
        await call.answer("❌ این کشور پیش‌تر توسط بازیکن دیگری انتخاب شده است!", show_alert=True)
        return await country_mode_select(call)
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if user["royal_coins"] < c["coin_price"]:
        need = c["coin_price"] - user["royal_coins"]
        return await call.answer(
            f"🪙 سکه شاهی کافی ندارید! {fmt(need)} سکه کم دارید. از بخش «سکه شاهی» خرید کنید.",
            show_alert=True)
    await db.execute("UPDATE users SET royal_coins=royal_coins-? WHERE id=?", (c["coin_price"], user["id"]))
    ok = await assign_country(user["id"], c, "", bot=call.bot)
    if not ok:
        await db.execute("UPDATE users SET royal_coins=royal_coins+? WHERE id=?", (c["coin_price"], user["id"]))
        return await call.answer("❌ کشور گرفته شد! سکه‌ها برگشت داده شد.", show_alert=True)
    await call.answer("🟢 خرید موفق")
    # هدایت فوری به تعیین نوع حکومت و دین
    await prompt_onboard_gov(call, c)


async def prompt_onboard_gov(call: CallbackQuery, country: dict):
    """گام اول شروع: تعیین نوع حکومت."""
    govs = await db.fetchall("SELECT * FROM governments WHERE is_active=1 ORDER BY id")
    rows = [[(f"🏛 {g['emoji']} {g['name']}", f"g|ogov|{g['id']}")] for g in govs]
    await call.message.edit_text(
        f"{country['flag']} تبریک! کشور <b>{country['name']}</b> به شما واگذار شد.\n\n"
        "📜 <b>گام ۱ از ۲: تعیین نوع حکومت</b>\n"
        "نوع نظام سیاسی امپراطوری خود را مشخص کنید:\n",
        reply_markup=kb(rows),
    )


@router.callback_query(F.data.startswith("g|ogov|"))
async def set_onboard_gov(call: CallbackQuery):
    gid = int(call.data.split("|")[2])
    g = await db.fetchone("SELECT * FROM governments WHERE id=?", (gid,))
    if not g:
        return await call.answer("حکومت یافت نشد", show_alert=True)
    await db.execute("UPDATE states SET government_id=? WHERE user_id=?", (gid, call.from_user.id))
    await call.answer(f"🏛 حکومت {g['name']} انتخاب شد")
    # گام دوم: تعیین دین
    rels = await db.fetchall("SELECT * FROM religions WHERE is_active=1 ORDER BY id")
    rows = [[(f"⛪ {r['emoji']} {r['name']}", f"g|orel|{r['id']}")] for r in rels]
    await call.message.edit_text(
        f"🏛 نوع حکومت: <b>{g['name']}</b>\n\n"
        "📜 <b>گام ۲ از ۲: تعیین دین رسمی</b>\n"
        "دین رسمی کشور خود را مشخص کنید:\n",
        reply_markup=kb(rows),
    )


@router.callback_query(F.data.startswith("g|orel|"))
async def set_onboard_rel(call: CallbackQuery):
    rid = int(call.data.split("|")[2])
    r = await db.fetchone("SELECT * FROM religions WHERE id=?", (rid,))
    if not r:
        return await call.answer("دین یافت نشد", show_alert=True)
    await db.execute("UPDATE states SET religion_id=? WHERE user_id=?", (rid, call.from_user.id))
    from core.economy import satisfaction_recompute, get_country
    await satisfaction_recompute(call.from_user.id)
    c = await get_country(call.from_user.id)
    await call.answer(f"⛪ دین {r['name']} انتخاب شد")
    is_admin = bool(await db.fetchone("SELECT id FROM admins WHERE id=?", (call.from_user.id,)))
    await call.message.edit_text(
        f"{c['flag']} <b>امپراطوری {c['name']} پایه‌گذاری شد!</b>\n\n"
        f"✅ دین رسمی: <b>{r['name']}</b>\n"
        "✅ ذخیره منابع پایه: ۱,۰۰۰ واحد مصالح، ۵,۰۰۰ واحد برق، ۵,۰۰۰ واحد آب و گاز به خزانه شما اضافه شد.\n\n"
        "فرمانده، اکنون وارد مرکز فرماندهی امپراطوری شوید 🌍",
        reply_markup=await main_menu_kb(is_admin),
    )


@router.callback_query(F.data.startswith("g|cntcash|"))
async def buy_with_cash(call: CallbackQuery, state: FSMContext):
    cid = int(call.data.split("|")[2])
    c = await db.fetchone("SELECT * FROM countries WHERE id=?", (cid,))
    if not c or c["owner_id"]:
        await call.answer("❌ این کشور پیش‌تر توسط بازیکن دیگری انتخاب شده است!", show_alert=True)
        return await country_mode_select(call)
    from core import config as cfg
    support = (await get_setting("sales_support", "") or cfg.SALES_SUPPORT).strip()
    handle = support if support.startswith("@") else f"@{support}"
    link = f"https://t.me/{handle.lstrip('@')}"
    await call.answer()
    await call.message.edit_text(
        f"👑 <b>خرید {c['flag']} {c['name']}</b>\n\n"
        f"💰 مبلغ: <b>{fmt(c['toman_price'])} تومان</b>\n\n"
        f"🛒 برای خرید به {handle} پیام بدید:\n"
        f'<a href="{link}">{handle}</a>',
        reply_markup=kb([[("🔴 بازگشت به انتخاب کشور", "g|cancel")]]),
    )


@router.callback_query(F.data == "g|cancel")
async def cancel_flow(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("🔴 عملیات لغو شد")
    user = await db.fetchone("SELECT country_id FROM users WHERE id=?", (call.from_user.id,))
    if user and user["country_id"]:
        await call.message.edit_text("❌ عملیات لغو شد.", reply_markup=await main_menu_kb())
    else:
        # وقتی هنوز کشوری ندارد یا خرید را لغو کرد، مستقیماً به کشورگیری بازگردد نه امپراطوری من!
        await country_mode_select(call)


@router.message(CashFSM.photo, F.photo)
async def cash_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    file_id = message.photo[-1].file_id
    if data.get("kind") == "country":
        c = await db.fetchone("SELECT * FROM countries WHERE id=?", (data["country_id"],))
        await db.execute(
            "INSERT INTO receipts(user_id, kind, country_id, coins, toman, photo_file_id) VALUES(?,?,?,?,?,?)",
            (message.from_user.id, "country", data["country_id"], 0, c["toman_price"], file_id),
        )
        await send_home(message, 
            "🧾 فیش شما ثبت شد و برای <b>ادمین</b> ارسال شد.\n"
            "پس از تأیید، کشور به شما واگذار می‌شود. 🙏",
            reply_markup=await main_menu_kb(),
        )
    else:  # خرید سکه
        await db.execute(
            "INSERT INTO receipts(user_id, kind, coins, toman, photo_file_id) VALUES(?,?,?,?,?)",
            (message.from_user.id, "coins", data.get("coins", 0), data.get("toman", 0), file_id),
        )
        await send_home(message, 
            "🧾 فیش شما ثبت شد و برای <b>ادمین</b> ارسال شد.\n"
            f"پس از تأیید، 🪙 <b>{fmt(data.get('coins', 0))} سکه شاهی</b> به حساب شما اضافه می‌شود. 🙏",
            reply_markup=await main_menu_kb(),
        )


@router.message(CashFSM.photo)
async def cash_receipt_invalid(message: Message):
    await send_home(message, "📸 لطفاً <b>عکس فیش</b> را ارسال کنید یا /cancel بزنید.")


# ─── تغییر کشور ───


@router.callback_query(F.data == "g|cchg")
async def change_country(call: CallbackQuery):
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if not user["country_id"]:
        return await country_selection(call.message)
    if not user["country_taken_at"]:
        hours = 0
    else:
        from datetime import datetime
        taken = datetime.strptime(user["country_taken_at"][:19], "%Y-%m-%d %H:%M:%S")
        from core.utils import now
        hours = (now() - taken).total_seconds() / 3600
    need = float(await get_setting("country_change_hours", "8"))
    if hours < need:
        left = need - hours
        return await call.answer(
            f"⏳ تا تغییر کشور {fmt_hm(left)} دیگر زمان دارید (قانون ۸ ساعت).",
            show_alert=True,
        )
    await call.message.edit_text(
        "🔄 <b>تغییر کشور</b>\n\n"
        "⚠️ هشدار: با تغییر کشور، <b>ساختمان‌ها، ارتش، پروژه‌ها و شرکت‌های شما ریست می‌شوند</b>. "
        "سکه شاهی و پول پایه محفوظ می‌ماند.\n\nادامه می‌دهید؟",
        reply_markup=kb([
            [("✅ بله، کشور را رها می‌کنم", "g|cchg2")],
            [("◀️ بازگشت", "g|main")],
        ]),
    )
    await call.answer()


@router.callback_query(F.data == "g|cchg2")
async def change_country_confirm(call: CallbackQuery):
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    if user["country_id"]:
        await db.execute("UPDATE countries SET owner_id=NULL, collapsed=0, province_count=5 "
                         "WHERE owner_id=?", (user["id"],))
        # 🗺 استان‌های کشور رهاشده آزاد می‌شوند تا نفر بعدی «سقوط‌کرده» نبیند
        await db.execute("UPDATE provinces SET owner_id=NULL, captured_at=NULL "
                         "WHERE owner_id=? OR country_id=?", (user["id"], user["country_id"]))
        await db.execute("UPDATE users SET country_id=NULL, country_taken_at=NULL WHERE id=?", (user["id"],))
        await reset_country_data(user["id"])
    await call.answer()
    await country_selection(call.message, user_id=call.from_user.id)

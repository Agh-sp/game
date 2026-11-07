"""اقتصاد: قیمت سکه، کارت به کارت، فیش‌ها (تأیید/رد) و پکیج‌ها."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import cd, kb
from adminbot.tools import log_action, notify_user, safe_edit
from core.db import db, get_setting, set_setting
from core.utils import fmt, tehran

router = Router()
PAGE = 6


class EcoFSM(StatesGroup):
    price = State()
    card = State()
    holder = State()
    rate = State()


@router.message(Command("receipts"))
async def cmd_receipts(message: Message, perms: set):
    if not has(perms, "economy"):
        return await message.answer("⛔️ دسترسی ندارید")
    await message.answer(**await receipts_page("pending", 0))


@router.callback_query(F.data == "a|eco")
async def eco_menu(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    price = int(await get_setting("coin_price_toman", "1000"))
    rate = int(await get_setting("coins_to_money_rate", "5000000"))
    card = await get_setting("c2c_card", "")
    holder = await get_setting("c2c_holder", "")
    pending = (await db.fetchone("SELECT COUNT(*) c FROM receipts WHERE status='pending'"))["c"]
    await call.answer()
    await call.message.edit_text(
        "🪙 <b>اقتصاد و سکه شاهی</b>\n\n"
        f"💵 قیمت هر سکه شاهی: <b>{fmt(price)} تومان</b>\n"
        f"🔄 نرخ تبدیل به پول پایه: <b>{fmt(rate)}</b>\n"
        f"💳 کارت: <code>{card or '—'}</code> ({holder or '—'})\n"
        f"🧾 فیش‌های در انتظار: <b>{pending}</b>",
        reply_markup=kb([
            [("💵 قیمت هر سکه", "a|eprice")],
            [("💳 کارت به کارت", "a|ecard")],
            [("🔄 نرخ تبدیل", "a|erate")],
            [("🏳 قیمت کشورها", "a|prices")],
            [("💵 درخواست‌های ارز", "a|cur")],
            [("🧾 فیش‌ها", "a|rcp|pending|0")],
            [("📦 پکیج‌های سکه", cd("pkg", "p", 0))],
            [("🤝 معاملات بازار", cd("trd", "p", 0))],
            [("🪙 ریست پول و سکه شاهی همه کاربران", "a|reset_wealth_prompt")],
            [("◀️ بازگشت", "a|root")],
        ]))


@router.callback_query(F.data == "a|eprice")
async def eco_price(call: CallbackQuery, state: FSMContext):
    await state.set_state(EcoFSM.price)
    await call.answer()
    price = int(await get_setting("coin_price_toman", "1000"))
    await call.message.edit_text(
        f"💵 قیمت فعلی هر سکه: <b>{fmt(price)} تومان</b>\n\n"
        "قیمت جدید را بفرستید (مثلاً 34000000):\n برای انصراف /cancel")


@router.message(EcoFSM.price)
async def eco_price_input(message: Message, state: FSMContext):
    try:
        v = int((message.text or "").replace(",", "").strip())
    except ValueError:
        return await message.answer("❌ فقط عدد بفرستید.")
    if v < 0:
        return await message.answer("❌ عدد نامعتبر")
    await state.clear()
    await set_setting("coin_price_toman", str(v))
    await log_action(message.from_user.id, "اقتصاد", f"قیمت سکه = {v}")
    await message.answer(f"✅ قیمت هر سکه شاهی روی <b>{fmt(v)} تومان</b> تنظیم شد.")


@router.callback_query(F.data == "a|ecard")
async def eco_card(call: CallbackQuery, state: FSMContext):
    await state.set_state(EcoFSM.card)
    await call.answer()
    await call.message.edit_text(
        "💳 شماره کارت جدید را بفرستید:\n برای انصراف /cancel")


@router.message(EcoFSM.card)
async def eco_card_input(message: Message, state: FSMContext):
    card = (message.text or "").strip()
    if not card or len(card) > 30:
        return await message.answer("❌ شماره کارت نامعتبر")
    await state.set_state(EcoFSM.holder)
    await state.update_data(card=card)
    await message.answer("👤 نام صاحب کارت را بفرستید:")


@router.message(EcoFSM.holder)
async def eco_holder_input(message: Message, state: FSMContext):
    holder = (message.text or "").strip()
    if not holder or len(holder) > 50:
        return await message.answer("❌ نام نامعتبر")
    data = await state.get_data()
    await state.clear()
    await set_setting("c2c_card", data["card"])
    await set_setting("c2c_holder", holder)
    await log_action(message.from_user.id, "اقتصاد", f"کارت = {data['card']}")
    await message.answer(f"✅ کارت به کارت آپدیت شد:\n<code>{data['card']}</code>\n👤 {holder}")


@router.callback_query(F.data == "a|erate")
async def eco_rate(call: CallbackQuery, state: FSMContext):
    await state.set_state(EcoFSM.rate)
    await call.answer()
    rate = int(await get_setting("coins_to_money_rate", "5000000"))
    await call.message.edit_text(
        f"🔄 نرخ فعلی تبدیل: هر سکه = <b>{fmt(rate)}</b> پول پایه\n\n"
        "نرخ جدید را بفرستید:\n برای انصراف /cancel")


@router.message(EcoFSM.rate)
async def eco_rate_input(message: Message, state: FSMContext):
    try:
        v = int((message.text or "").replace(",", "").strip())
    except ValueError:
        return await message.answer("❌ فقط عدد بفرستید.")
    if v < 1:
        return await message.answer("❌ عدد نامعتبر")
    await state.clear()
    await set_setting("coins_to_money_rate", str(v))
    await log_action(message.from_user.id, "اقتصاد", f"نرخ تبدیل = {v}")
    await message.answer(f"✅ نرخ تبدیل هر سکه به <b>{fmt(v)}</b> پول پایه تنظیم شد.")


# ─── فیش‌ها ───


async def receipts_page(status: str, page: int) -> dict:
    total = (await db.fetchone("SELECT COUNT(*) c FROM receipts WHERE status=?", (status,)))["c"]
    rows = await db.fetchall(
        "SELECT r.*, u.full_name, u.username, c.name AS country_name, c.flag AS country_flag "
        "FROM receipts r LEFT JOIN users u ON u.id=r.user_id "
        "LEFT JOIN countries c ON c.id=r.country_id "
        "WHERE r.status=? ORDER BY r.id DESC LIMIT ? OFFSET ?",
        (status, PAGE, page * PAGE))
    fa = {"pending": "⏳ در انتظار", "approved": "✅ تأییدشده", "rejected": "❌ ردشده"}
    lines = [f"🧾 <b>فیش‌ها — {fa.get(status, status)}</b> ({fmt(total)})\n"]
    buttons = []
    for r in rows:
        if r["kind"] == "country":
            what = f"خرید کشور {r['country_flag'] or ''} {r['country_name'] or ('#' + str(r['country_id']))}"
        else:
            what = f"خرید {fmt(r['coins'])} سکه شاهی"
        who = r["full_name"] or str(r["user_id"])
        lines.append(f"#{r['id']} — {who} — {what} — {fmt(r['toman'])} تومان — {tehran(r['created_at'])}")
        row_btns = [(f"🧾 #{r['id']} {who[:16]}", f"a|rcpo|{r['id']}")]
        if r["status"] == "pending":
            row_btns.append((f"✅ تأیید #{r['id']}", f"a|rcpok|{r['id']}"))
            row_btns.append((f"❌ رد #{r['id']}", f"a|rcpno|{r['id']}"))
        buttons.append(row_btns)
    if not rows:
        lines.append("<i>— خالی —</i>")
    tabs = [("⏳ در انتظار", f"a|rcp|pending|0"), ("✅ تأییدشده", f"a|rcp|approved|0"),
            ("❌ ردشده", f"a|rcp|rejected|0")]
    nav = list(tabs)
    if page > 0:
        nav.append(("‹ قبلی", f"a|rcp|{status}|{page - 1}"))
    if (page + 1) * PAGE < total:
        nav.append(("بعدی ›", f"a|rcp|{status}|{page + 1}"))
    all_rows = [list(b) for b in buttons] + [nav, [("◀️ بازگشت", "a|eco")]]
    return {"text": "\n".join(lines), "reply_markup": kb(all_rows)}


@router.callback_query(F.data.startswith("a|rcp|"))
async def receipts_list(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    _, _, status, page = call.data.split("|")
    payload = await receipts_page(status, int(page))
    await call.answer()
    await safe_edit(call, payload["text"], payload["reply_markup"])


@router.callback_query(F.data.startswith("a|rcpo|"))
async def receipt_open(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    rid = int(call.data.split("|")[2])
    r = await db.fetchone(
        "SELECT r.*, u.full_name, u.username, c.name AS country_name, c.flag AS country_flag "
        "FROM receipts r LEFT JOIN users u ON u.id=r.user_id "
        "LEFT JOIN countries c ON c.id=r.country_id WHERE r.id=?", (rid,))
    if not r:
        return await call.answer("یافت نشد", show_alert=True)
    user = await db.fetchone("SELECT royal_coins, money FROM users WHERE id=?", (r["user_id"],))
    if r["kind"] == "country":
        what = f"خرید کشور {r['country_flag'] or ''} <b>{r['country_name']}</b>"
        country = await db.fetchone("SELECT * FROM countries WHERE id=?", (r["country_id"],))
        free = "✅ آزاد است" if country and not country["owner_id"] else "❌ گرفته شده!"
    else:
        what = f"خرید <b>{fmt(r['coins'])} سکه شاهی</b>"
        free = ""
    text = (
        f"🧾 <b>فیش #{r['id']}</b>\n\n"
        f"👤 کاربر: {r['full_name'] or '—'} <code>{r['user_id']}</code>"
        + (f" (@{r['username']})" if r["username"] else "") + "\n"
        f"📋 نوع: {what}\n"
        f"💵 مبلغ: <b>{fmt(r['toman'])} تومان</b>\n"
        f"📅 زمان: {tehran(r['created_at'])}\n"
        f"📌 وضعیت: {r['status']}\n"
        + (f"\n🏳 وضعیت کشور: {free}\n" if free else "")
        + f"\n🪙 سکه فعلی کاربر: {fmt(user['royal_coins']) if user else '—'}"
        + (f" | 💰 پول: {fmt(user['money'])}" if user else ""))
    # ارسال عکس فیش
    if r["photo_file_id"]:
        try:
            await call.message.answer_photo(r["photo_file_id"], caption=f"🧾 عکس فیش #{r['id']}")
        except Exception:
            try:
                await call.bot.send_photo(call.from_user.id, r["photo_file_id"],
                                          caption=f"🧾 عکس فیش #{r['id']}")
            except Exception:
                pass
    buttons = []
    if r["status"] == "pending":
        buttons.append([("✅ تأیید و اعمال", f"a|rcpok|{rid}"), ("❌ رد کردن", f"a|rcpno|{rid}")])
    buttons.append([("👤 پروفایل کاربر", f"a|ucard|{r['user_id']}")])
    buttons.append([("✏️ ویرایش خام", cd("rcp", "r", rid))])
    buttons.append([(f"◀️ بازگشت", f"a|rcp|{r['status']}|0")])
    await call.answer()
    await safe_edit(call, text, kb(buttons))


async def apply_receipt(r: dict, admin_id: int) -> str:
    """تأیید و اعمال یک فیش (کشور یا سکه شاهی) — خروجی: متن نتیجه."""
    from core.utils import iso
    rid = r["id"]
    await db.execute(
        "UPDATE receipts SET status='approved', reviewed_by=?, reviewed_at=? WHERE id=?",
        (admin_id, iso(), rid))
    if r["kind"] == "country":
        country = await db.fetchone("SELECT * FROM countries WHERE id=?", (r["country_id"],))
        cur_owner = country.get("owner_id") if country else None
        # کشور در صورتی قابل واگذاری است که بدون مالک (None یا 0) یا متعلق به خود کاربر باشد
        if country and (not cur_owner or cur_owner == 0 or cur_owner == r["user_id"]):
            await db.execute("UPDATE countries SET owner_id=?, collapsed=0, province_count=5 "
                             "WHERE id=?", (r["user_id"], country["id"]))
            await db.execute("UPDATE users SET country_id=?, country_taken_at=? WHERE id=?",
                             (country["id"], iso(), r["user_id"]))
            from core.economy import get_state
            await get_state(r["user_id"])
            # 🗺 استان‌های کشور به خریدار داده می‌شود (وگرنه «سقوط‌کرده» می‌بیند)
            try:
                from core.provinces import ensure_country_provinces
                await ensure_country_provinces(country["id"], r["user_id"], normalize=True)
            except Exception:
                pass
            currency = country.get("currency") or country["name"]
            await db.execute(
                "UPDATE states SET currency_name=?, materials=COALESCE(materials, 0)+1000, "
                "energy=COALESCE(energy, 0)+5000, water=COALESCE(water, 0)+5000, "
                "gas=COALESCE(gas, 0)+5000 WHERE user_id=?",
                (currency, r["user_id"]))
            await notify_user(
                r["user_id"],
                f"✅ پرداخت شما تأیید شد! کشور {country['flag']} <b>{country['name']}</b> "
                "به شما واگذار شد. 🎉\n\nهم‌اکنون با دستور /start وارد مرکز فرماندهی امپراتوری شوید 🌍")
            result = "✅ فیش تأیید شد و کشور به بازیکن واگذار شد."
        else:
            await notify_user(
                r["user_id"],
                "⚠️ پرداخت شما تأیید شد اما کشور انتخابی هم‌اکنون به بازیکن دیگری واگذار شده است. "
                "با پشتیبانی تماس بگیرید تا کشور دیگری یا سکه شاهی معادل دریافت کنید.")
            result = "⚠️ کشور در این فاصله به بازیکن دیگری واگذار شده بود؛ به بازیکن اطلاع داده شد."
    else:
        coins_to_add = int(r.get("coins") or 0)
        if coins_to_add <= 0 and (r.get("toman") or 0) > 0:
            price = int(await get_setting("coin_price_toman", "1000")) or 1
            coins_to_add = max(1, int(r["toman"] // price))
        await db.execute("UPDATE users SET royal_coins=COALESCE(royal_coins, 0)+? WHERE id=?",
                         (coins_to_add, r["user_id"]))
        await notify_user(
            r["user_id"],
            f"✅ پرداخت شما تأیید شد! 🪙 <b>{fmt(coins_to_add)} سکه شاهی</b> به حساب شما اضافه شد. 🎉")
        result = f"✅ فیش تأیید شد و {fmt(coins_to_add)} سکه به بازیکن اضافه شد."
    await log_action(admin_id, "فیش", f"تأیید فیش #{rid} کاربر {r['user_id']}")
    return result


async def reject_receipt(r: dict, admin_id: int) -> str:
    from core.utils import iso
    await db.execute(
        "UPDATE receipts SET status='rejected', reviewed_by=?, reviewed_at=? WHERE id=?",
        (admin_id, iso(), r["id"]))
    await notify_user(
        r["user_id"],
        "❌ فیش پرداخت شما رد شد. در صورت هرگونه سوال با پشتیبانی در ارتباط باشید.")
    await log_action(admin_id, "فیش", f"رد فیش #{r['id']} کاربر {r['user_id']}")
    return "❌ فیش رد شد."


@router.callback_query(F.data.startswith("a|rcpok|"))
async def receipt_approve(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    rid = int(call.data.split("|")[2])
    r = await db.fetchone("SELECT * FROM receipts WHERE id=? AND status='pending'", (rid,))
    if not r:
        return await call.answer("این فیش در انتظار نیست (قبلاً بررسی شده)", show_alert=True)
    result = await apply_receipt(r, call.from_user.id)
    await call.answer(result[:190], show_alert=True)
    payload = await receipts_page("pending", 0)
    await safe_edit(call, payload["text"], payload["reply_markup"])


@router.callback_query(F.data.startswith("a|rcpno|"))
async def receipt_reject(call: CallbackQuery, perms: set):
    if not has(perms, "economy"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    rid = int(call.data.split("|")[2])
    r = await db.fetchone("SELECT * FROM receipts WHERE id=? AND status='pending'", (rid,))
    if not r:
        return await call.answer("این فیش در انتظار نیست (قبلاً بررسی شده)", show_alert=True)
    result = await reject_receipt(r, call.from_user.id)
    await call.answer(result, show_alert=True)
    payload = await receipts_page("pending", 0)
    await safe_edit(call, payload["text"], payload["reply_markup"])


@router.message(Command("approve", "reject"))
async def cmd_receipt_action(message: Message, perms: set):
    """تأیید/رد سریع فیش با دستور: /approve 12 یا /reject 12"""
    if not has(perms, "economy"):
        return await message.answer("⛔️ دسترسی ندارید")
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("استفاده: <code>/approve 12</code> یا <code>/reject 12</code>")
    rid = int(parts[1])
    r = await db.fetchone("SELECT * FROM receipts WHERE id=? AND status='pending'", (rid,))
    if not r:
        return await message.answer("❌ فیشی با این شماره در انتظار تأیید نیست.")
    if parts[0].lower().startswith("/approve"):
        result = await apply_receipt(r, message.from_user.id)
    else:
        result = await reject_receipt(r, message.from_user.id)
    await message.answer(result + "\n\n🧾 برای دیدن لیست فیش‌ها: /receipts")

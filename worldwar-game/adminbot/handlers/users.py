"""ابزارهای مدیریت کاربران: پروفایل، سکه/پول، بن، حذف کشور/پژوهش/تجهیزات، ریست، پیام."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import cd, kb
from adminbot.tools import log_action, notify_user
from core.db import db, get_initial_money
from core.economy import army_power, get_country
from core.utils import fmt, fmt_money, tehran

router = Router()
PAGE = 8


class UserFSM(StatesGroup):
    search = State()
    amount = State()
    message = State()


@router.message(Command("u"))
async def cmd_user(message: Message, state: FSMContext, perms: set):
    if not has(perms, "users"):
        return await message.answer("⛔️ دسترسی ندارید")
    await state.set_state(UserFSM.search)
    await message.answer(
        "👥 <b>جستجوی کاربر</b>\n\nآیدی عددی، یوزرنیم یا نام کاربر را بفرستید:\n برای انصراف /cancel",
        reply_markup=kb([[("◀️ بازگشت به منوی کاربران", "a|usr")]]))


@router.message(Command("users"))
async def cmd_users_menu(message: Message, state: FSMContext, perms: set):
    if not has(perms, "users"):
        return await message.answer("⛔️ دسترسی ندارید")
    await state.clear()
    text, markup = await build_users_menu_payload()
    await message.answer(text, reply_markup=markup)


async def build_users_menu_payload() -> tuple[str, any]:
    u_total = (await db.fetchone("SELECT COUNT(*) c FROM users"))["c"]
    u_active = (await db.fetchone("SELECT COUNT(*) c FROM users WHERE country_id IS NOT NULL"))["c"]
    u_banned = (await db.fetchone("SELECT COUNT(*) c FROM users WHERE banned=1"))["c"]
    coins = (await db.fetchone("SELECT COALESCE(SUM(royal_coins),0) c FROM users"))["c"]
    money = (await db.fetchone("SELECT COALESCE(SUM(money),0) c FROM users"))["c"]

    text = (
        "👥 <b>مدیریت بازیکنان و کاربران بازی</b>\n\n"
        f"📊 <b>آمار بازیکنان:</b>\n"
        f"• تعداد کل کاربران: <b>{fmt(u_total)}</b> نفر\n"
        f"• دارای کشور فعال: <b>{fmt(u_active)}</b> نفر\n"
        f"• مسدود شده (بن): <b>{fmt(u_banned)}</b> نفر\n"
        f"• مجموع سکه شاهی همه: <b>{fmt(coins)}</b> 🪙\n"
        f"• مجموع پول خزانه‌ها: <b>{fmt(money)}</b> 💰\n\n"
        "یکی از عملیات زیر را انتخاب کنید:"
    )
    markup = kb([
        [("🔍 جستجوی کاربر", "a|usr|search"), ("📋 فهرست بازیکنان", "a|usr|list|0")],
        [("🪙 ریست پول و سکه شاهی همه کاربران", "a|reset_wealth_prompt")],
        [("♻️ ریست همه بازیکنان (کشورها و پیشرفت)", "a|reset_players_prompt")],
        [("◀️ بازگشت به پنل اصلی", "a|root")],
    ])
    return text, markup


@router.callback_query(F.data == "a|usr")
async def user_menu_callback(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.clear()
    text, markup = await build_users_menu_payload()
    await call.answer()
    await call.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "a|usr|search")
async def user_search(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.set_state(UserFSM.search)
    await call.answer()
    await call.message.edit_text(
        "👥 <b>جستجوی کاربر</b>\n\nآیدی عددی، یوزرنیم یا نام کاربر را بفرستید:\n برای انصراف /cancel",
        reply_markup=kb([[("◀️ بازگشت به منوی کاربران", "a|usr")]]))


@router.callback_query(F.data.startswith("a|usr|list|"))
async def users_list_page(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    page = int(call.data.split("|")[3])
    per_page = 8
    offset = page * per_page
    total = (await db.fetchone("SELECT COUNT(*) c FROM users"))["c"]
    rows = await db.fetchall(
        "SELECT u.*, c.name as country_name, c.flag as country_flag "
        "FROM users u LEFT JOIN countries c ON c.id=u.country_id "
        "ORDER BY u.id DESC LIMIT ? OFFSET ?", (per_page, offset)
    )
    lines = [f"📋 <b>فهرست بازیکنان (صفحه {page + 1})</b>\nکل: {fmt(total)} کاربر\n"]
    buttons = []
    if not rows:
        lines.append("— کاربری یافت نشد —")
    for r in rows:
        flag = r["country_flag"] or "👤"
        c_title = f" [{r['country_name']}]" if r["country_name"] else ""
        lines.append(f"• {flag} <b>{r['full_name']}</b>{c_title} — 🪙 {fmt(r['royal_coins'])} | 💰 {fmt(r['money'])}")
        buttons.append([(f"{flag} {r['full_name'][:18]} (ID: {r['id']})", f"a|ucard|{r['id']}")])

    nav = []
    if page > 0:
        nav.append(("◀️ صفحه قبل", f"a|usr|list|{page - 1}"))
    if offset + per_page < total:
        nav.append(("صفحه بعد ▶️", f"a|usr|list|{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([("◀️ بازگشت به منوی کاربران", "a|usr")])
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))


@router.message(UserFSM.search)
async def user_search_input(message: Message, state: FSMContext):
    q = (message.text or "").strip().lstrip("@")
    like = f"%{q}%"
    if q.isdigit():
        rows = await db.fetchall(
            "SELECT * FROM users WHERE id=? OR full_name LIKE ? OR username LIKE ? LIMIT 10",
            (int(q), like, like))
    else:
        rows = await db.fetchall(
            "SELECT * FROM users WHERE full_name LIKE ? OR username LIKE ? LIMIT 10", (like, like))
    if not rows:
        return await message.answer("❌ کاربری یافت نشد. دوباره بفرستید یا /cancel")
    if len(rows) == 1:
        await state.clear()
        fake = _FakeCall(message)
        return await user_card(fake, rows[0]["id"])
    lines = ["👥 <b>نتایج جستجو</b>"]
    buttons = []
    for r in rows:
        country = await db.fetchone("SELECT flag, name FROM countries WHERE id=?", (r["country_id"],)) \
            if r["country_id"] else None
        c_txt = f" {country['flag']}{country['name']}" if country else ""
        lines.append(f"• {r['full_name']} <code>{r['id']}</code>{c_txt}")
        buttons.append([(f"{r['full_name']} ({fmt(r['id'])})", f"a|ucard|{r['id']}")])
    buttons.append([("◀️ بازگشت", "a|root")])
    await message.answer("\n".join(lines), reply_markup=kb(buttons))


async def user_card_text(uid: int) -> tuple[str, dict | None]:
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (uid,))
    if not user:
        return "❌ کاربر یافت نشد", None
    country = await get_country(uid)
    atk, dfn, cyb = await army_power(uid)
    state = await db.fetchone("SELECT * FROM states WHERE user_id=?", (uid,))
    assets = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=?", (uid,))
    projects = await db.fetchone(
        "SELECT COUNT(*) c FROM player_projects WHERE user_id=?", (uid,))
    companies = await db.fetchone(
        "SELECT COUNT(*) c FROM companies WHERE owner_id=?", (uid,))
    receipts = await db.fetchone(
        "SELECT COUNT(*) c FROM receipts WHERE user_id=?", (uid,))
    text = (
        f"👤 <b>{user['full_name']}</b>"
        + (f" (@{user['username']})" if user["username"] else "") + "\n"
        f"🆔 <code>{user['id']}</code>\n\n"
        f"🏳 کشور: {country['flag'] + ' ' + country['name'] if country else '—'}\n"
        f"🪙 سکه شاهی: <b>{fmt(user['royal_coins'])}</b>\n"
        f"💰 پول پایه: <b>{fmt(user['money'])}</b>\n"
        + (f"😊 رضایت: <b>{round(state['satisfaction'] or 0)}/100</b>\n" if state else "")
        + f"⚔️ ارتش: حمله {fmt(atk)} | دفاع {fmt(dfn)} | سایبر {fmt(cyb)}\n"
        f"📦 دارایی‌ها: {fmt(assets['c'])} | 🔬 پروژه/پژوهش: {fmt(projects['c'])} | "
        f"🏢 شرکت: {fmt(companies['c'])}\n"
        f"🧾 فیش‌ها: {fmt(receipts['c'])}\n"
        f"🚫 اخراج: {'بله' if user['banned'] else 'خیر'} | 📅 عضویت: {tehran(user['joined_at'])}")
    return text, user


def user_card_kb(uid: int, banned: int) -> list:
    return [
        [("🪙 + سکه شاهی", f"a|ucoin|{uid}|p"), ("🪙 − سکه شاهی", f"a|ucoin|{uid}|m")],
        [("💰 + پول", f"a|umon|{uid}|p"), ("💰 − پول", f"a|umon|{uid}|m")],
        [("🗑 برداشتن کشورش", f"a|ucountry|{uid}")],
        [("🧹 حذف پژوهش‌هایش", f"a|ures|{uid}"), ("🧹 حذف تجهیزاتش", f"a|ueq|{uid}")],
        [("♻️ ریست کامل", f"a|ureset|{uid}")],
        [("✏️ ویرایش خام ردیف", cd("usr", "r", uid))],
        [("✉️ پیام خصوصی", f"a|umsg|{uid}")],
        [("🚫 بن" if not banned else "✅ لغو بن", f"a|uban|{uid}")],
        [("🧾 فیش‌های او", f"a|urcp|{uid}")],
        [("◀️ بازگشت", "a|root")],
    ]


async def user_card(call, uid: int):
    text, user = await user_card_text(uid)
    if not user:
        return await call.answer("کاربر یافت نشد", show_alert=True)
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(user_card_kb(uid, user["banned"])))


@router.callback_query(F.data.startswith("a|ucard|"))
async def on_user_card(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    await user_card(call, uid)


@router.callback_query(F.data.startswith("a|ucoin|"))
async def user_coin(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    _, _, uid, sign = call.data.split("|")
    await state.set_state(UserFSM.amount)
    await state.update_data(op="coin", uid=int(uid), sign=sign)
    await call.answer()
    await call.message.edit_text(
        f"🪙 مقدار {'افزایش' if sign == 'p' else 'کاهش'} سکه شاهی را بفرستید:\n برای انصراف /cancel")


@router.callback_query(F.data.startswith("a|umon|"))
async def user_money(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    _, _, uid, sign = call.data.split("|")
    await state.set_state(UserFSM.amount)
    await state.update_data(op="money", uid=int(uid), sign=sign)
    await call.answer()
    await call.message.edit_text(
        f"💰 مقدار {'افزایش' if sign == 'p' else 'کاهش'} پول پایه را بفرستید:\n برای انصراف /cancel")


@router.message(UserFSM.amount)
async def user_amount_input(message: Message, state: FSMContext):
    try:
        amount = int((message.text or "").strip().replace(",", ""))
    except ValueError:
        return await message.answer("❌ فقط عدد بفرستید.")
    if amount < 0:
        return await message.answer("❌ عدد نمی‌تواند منفی باشد.")
    data = await state.get_data()
    await state.clear()
    uid, op, sign = data["uid"], data["op"], data["sign"]
    col = "royal_coins" if op == "coin" else "money"
    if sign == "m":
        user = await db.fetchone(f"SELECT {col} AS v FROM users WHERE id=?", (uid,))
        amount = min(amount, user["v"] if user else 0)
        await db.execute(f"UPDATE users SET {col}={col}-? WHERE id=?", (amount, uid))
    else:
        await db.execute(f"UPDATE users SET {col}={col}+? WHERE id=?", (amount, uid))
    label = "سکه شاهی" if op == "coin" else "پول پایه"
    await log_action(message.from_user.id, "کاربر",
                     f"{label} {'+' if sign == 'p' else '-'}{amount} برای {uid}")
    await message.answer(f"✅ {label} کاربر <code>{uid}</code> "
                         f"{'+' if sign == 'p' else '-'}<b>{fmt(amount)}</b> شد.")
    await notify_user(uid, f"🔔 {label} شما توسط ادمین "
                           f"{'افزایش' if sign == 'p' else 'کاهش'} یافت: {fmt(amount)}.")
    await user_card(_FakeCall(message), uid)


@router.callback_query(F.data.startswith("a|uban|"))
async def user_ban(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (uid,))
    if not user:
        return await call.answer("کاربر یافت نشد", show_alert=True)
    new = 0 if user["banned"] else 1
    await db.execute("UPDATE users SET banned=? WHERE id=?", (new, uid))
    await log_action(call.from_user.id, "کاربر", f"بن={new} برای {uid}")
    await notify_user(uid, "🚫 شما توسط ادمین از بازی اخراج شدید." if new else
                      "✅ حکم اخراج شما لغو شد — welcome back!")
    await call.answer("✅ اعمال شد")
    await user_card(call, uid)


@router.callback_query(F.data.startswith("a|ucountry|"))
async def user_remove_country(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (uid,))
    if not user or not user["country_id"]:
        return await call.answer("کشوری ندارد", show_alert=True)
    await db.execute("UPDATE countries SET owner_id=NULL WHERE owner_id=?", (uid,))
    await db.execute("UPDATE users SET country_id=NULL, country_taken_at=NULL WHERE id=?", (uid,))
    await db.execute("DELETE FROM player_assets WHERE user_id=?", (uid,))
    await db.execute("DELETE FROM player_projects WHERE user_id=?", (uid,))
    await db.execute("DELETE FROM soldier_trainings WHERE user_id=?", (uid,))
    await db.execute("DELETE FROM companies WHERE owner_id=?", (uid,))
    await db.execute("DELETE FROM bases WHERE guest_id=? OR host_id=?", (uid, uid))
    await log_action(call.from_user.id, "کاربر", f"برداشتن کشور {user['country_id']} از {uid}")
    await notify_user(uid, "🏳 کشور شما توسط ادمین برداشته شد.")
    await call.answer("✅ کشور آزاد شد")
    await user_card(call, uid)


@router.callback_query(F.data.startswith("a|ures|"))
async def user_clear_research(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    await db.execute("DELETE FROM player_projects WHERE user_id=?", (uid,))
    await log_action(call.from_user.id, "کاربر", f"حذف پژوهش‌های {uid}")
    await notify_user(uid, "🔬 پروژه‌ها و پژوهش‌های شما توسط ادمین حذف شد.")
    await call.answer("✅ پژوهش‌ها حذف شد")
    await user_card(call, uid)


@router.callback_query(F.data.startswith("a|ueq|"))
async def user_clear_equip(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    await db.execute("DELETE FROM player_assets WHERE user_id=? AND item_type='equipment'", (uid,))
    await db.execute("DELETE FROM player_assets WHERE user_id=? AND item_type='soldier'", (uid,))
    await log_action(call.from_user.id, "کاربر", f"حذف تجهیزات {uid}")
    await notify_user(uid, "🪖 تجهیزات و سربازان شما توسط ادمین حذف شد.")
    await call.answer("✅ تجهیزات حذف شد")
    await user_card(call, uid)


@router.callback_query(F.data.startswith("a|ureset|"))
async def user_reset(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (uid,))
    if not user:
        return await call.answer("کاربر یافت نشد", show_alert=True)
    if user["country_id"]:
        await db.execute("UPDATE countries SET owner_id=NULL WHERE owner_id=?", (uid,))
    await db.execute(
        "UPDATE users SET country_id=NULL, country_taken_at=NULL, royal_coins=0, money=?, banned=0 "
        "WHERE id=?", (await get_initial_money(), uid))
    await db.execute("DELETE FROM player_assets WHERE user_id=?", (uid,))
    await db.execute("DELETE FROM player_projects WHERE user_id=?", (uid,))
    await db.execute("DELETE FROM soldier_trainings WHERE user_id=?", (uid,))
    await db.execute("DELETE FROM companies WHERE owner_id=?", (uid,))
    await db.execute("DELETE FROM bases WHERE guest_id=? OR host_id=?", (uid, uid))
    await db.execute("DELETE FROM states WHERE user_id=?", (uid,))
    await log_action(call.from_user.id, "کاربر", f"ریست کامل {uid}")
    await notify_user(uid, "♻️ اکانت شما توسط ادمین کامل ریست شد.")
    await call.answer("♻️ ریست شد")
    await user_card(call, uid)


@router.callback_query(F.data.startswith("a|umsg|"))
async def user_message(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    await state.set_state(UserFSM.message)
    await state.update_data(uid=uid)
    await call.answer()
    await call.message.edit_text(
        f"✉️ پیام خصوصی برای کاربر <code>{uid}</code> را بفرستید (متن):\n برای انصراف /cancel")


@router.message(UserFSM.message)
async def user_message_input(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    text = (message.text or "").strip()
    if not text:
        return await message.answer("❌ متن خالی است.")
    ok = await notify_user(data["uid"], f"📬 پیام از پشتیبانی:\n\n{text}")
    await log_action(message.from_user.id, "کاربر", f"پیام به {data['uid']}")
    await message.answer("✅ ارسال شد." if ok else
                         "⚠️ ارسال نشد — کاربر ربات اصلی را استارت نکرده یا بلاکش کرده.")
    await user_card(_FakeCall(message), data["uid"])


@router.callback_query(F.data.startswith("a|urcp|"))
async def user_receipts(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    rows = await db.fetchall(
        "SELECT * FROM receipts WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
    lines = [f"🧾 <b>فیش‌های کاربر {uid}</b>\n"]
    if not rows:
        lines.append("— ندارد —")
    buttons = []
    for r in rows:
        what = f"کشور(#{r['country_id']})" if r["kind"] == "country" else f"{fmt(r['coins'])} سکه"
        lines.append(f"#{r['id']} {what} — {fmt(r['toman'])} تومان — {r['status']} — "
                     f"{tehran(r['created_at'])}")
        if r["status"] == "pending" and has(perms, "economy"):
            buttons.append([(f"✅ تأیید فیش #{r['id']}", f"a|rcpok|{r['id']}"),
                            (f"❌ رد #{r['id']}", f"a|rcpno|{r['id']}")])
    buttons.append([("◀️ پروفایل کاربر", f"a|ucard|{uid}")])
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))


# ─── ریست پول و سکه شاهی همه کاربران ───


@router.message(Command("reset_wealth"))
async def cmd_reset_wealth(message: Message, perms: set):
    if not (has(perms, "economy") or has(perms, "users")):
        return await message.answer("⛔️ دسترسی ندارید")
    text, markup = await build_reset_wealth_payload()
    await message.answer(text, reply_markup=markup)


async def build_reset_wealth_payload() -> tuple[str, any]:
    u_total = (await db.fetchone("SELECT COUNT(*) c FROM users"))["c"]
    coins = (await db.fetchone("SELECT COALESCE(SUM(royal_coins),0) c FROM users"))["c"]
    money = (await db.fetchone("SELECT COALESCE(SUM(money),0) c FROM users"))["c"]

    text = (
        "🪙 <b>ریست دارایی نقدی (پول و سکه شاهی) همه کاربران</b>\n\n"
        "از این بخش می‌توانید موجودی پول پایه یا سکه شاهی تمام بازیکنان را یکجا بازنشانی نمایید:\n\n"
        f"📊 <b>وضعیت کنونی دارایی‌های کل:</b>\n"
        f"• تعداد کل کاربران: <b>{fmt(u_total)}</b> نفر\n"
        f"• مجموع کل سکه شاهی: <b>{fmt(coins)}</b> 🪙\n"
        f"• مجموع کل پول خزانه‌ها: <b>{fmt(money)}</b> 💰\n\n"
        "عملیات مورد نظر خود را با دقت انتخاب نمایید:"
    )
    markup = kb([
        [(f"🔥 ریست کامل هر دو (سکه=۰ | پول={fmt_money(await get_initial_money())})",
          "a|conf_reset_wealth|both_default")],
        [("🪙 فقط صفر کردن سکه شاهی همه (۰ سکه)", "a|conf_reset_wealth|coins_zero")],
        [(f"💰 فقط ریست پول همه به {fmt_money(await get_initial_money())} پایه",
          "a|conf_reset_wealth|money_default")],
        [("🚫 فقط صفر کردن موجودی پول همه (۰ تومان)", "a|conf_reset_wealth|money_zero")],
        [("◀️ بازگشت به منوی کاربران", "a|usr"), ("◀️ پنل اصلی", "a|root")],
    ])
    return text, markup


@router.callback_query(F.data == "a|reset_wealth_prompt")
async def reset_wealth_prompt(call: CallbackQuery, perms: set):
    if not (has(perms, "economy") or has(perms, "users")):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    text, markup = await build_reset_wealth_payload()
    await call.answer()
    await call.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("a|conf_reset_wealth|"))
async def reset_wealth_confirm_step(call: CallbackQuery, perms: set):
    if not (has(perms, "economy") or has(perms, "users")):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    mode = call.data.split("|")[2]
    u_total = (await db.fetchone("SELECT COUNT(*) c FROM users"))["c"]

    mode_titles = {
        "both_default": "ریست همزمان: سکه شاهی همه ۰ و پول پایه همه ۵۰٬۰۰۰٬۰۰۰ شود",
        "coins_zero": "فقط صفر کردن سکه شاهی تمام کاربران (۰ سکه شاهی)",
        "money_default": "فقط ریست موجودی پول همه کاربران به ۵۰٬۰۰۰٬۰۰۰",
        "money_zero": "فقط صفر کردن کل موجودی پول همه کاربران (۰)",
    }
    title = mode_titles.get(mode, mode)

    text = (
        "⚠️ <b>تأیید نهایی ریست مالی کاربران</b>\n\n"
        f"عملیات انتخابی: <b>{title}</b>\n"
        f"تعداد کاربران تحت تأثیر: <b>{fmt(u_total)}</b> نفر\n\n"
        "آیا از انجام این عملیات روی حساب <b>تمام کاربران بازی</b> اطمینان کامل دارید؟\n"
        "این عملیات بلافاصله در دیتابیس اعمال می‌شود و غیرقابل بازگشت است!"
    )
    markup = kb([
        [(f"✅ بله، مطمئنم — اعمال ریست", f"a|exec_reset_wealth|{mode}")],
        [("❌ خیر، انصراف", "a|reset_wealth_prompt")],
    ])
    await call.answer()
    await call.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("a|exec_reset_wealth|"))
async def reset_wealth_execute(call: CallbackQuery, perms: set):
    if not (has(perms, "economy") or has(perms, "users")):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    mode = call.data.split("|")[2]
    u_total = (await db.fetchone("SELECT COUNT(*) c FROM users"))["c"]

    if mode == "both_default":
        initial = await get_initial_money()
        await db.execute("UPDATE users SET royal_coins=0, money=?", (initial,))
        desc = f"ریست کامل پول به {fmt(initial)} و سکه شاهی به ۰ برای همه کاربران"
    elif mode == "coins_zero":
        await db.execute("UPDATE users SET royal_coins=0")
        desc = "صفر کردن سکه شاهی تمام کاربران"
    elif mode == "money_default":
        initial = await get_initial_money()
        await db.execute("UPDATE users SET money=?", (initial,))
        desc = f"ریست پول پایه همه کاربران به {fmt(initial)}"
    elif mode == "money_zero":
        await db.execute("UPDATE users SET money=0")
        desc = "صفر کردن موجودی پول همه کاربران"
    else:
        return await call.answer("حالت نامعتبر", show_alert=True)

    # Sync to Firebase if connected
    try:
        from core.firebase import fb
        await fb.push_table("users")
    except Exception:
        pass

    # Log action
    from core.events import log_event
    await log_action(call.from_user.id, "اقتصاد", desc)
    await log_event("economy", f"{desc} توسط ادمین")

    coins_new = (await db.fetchone("SELECT COALESCE(SUM(royal_coins),0) c FROM users"))["c"]
    money_new = (await db.fetchone("SELECT COALESCE(SUM(money),0) c FROM users"))["c"]

    text = (
        "✅ <b>عملیات ریست مالی با موفقیت انجام شد!</b>\n\n"
        f"• عنوان عملیات: <b>{desc}</b>\n"
        f"• تعداد کاربران به‌روزرسانی شده: <b>{fmt(u_total)}</b> نفر\n"
        f"• مجموع جدید سکه شاهی کل: <b>{fmt(coins_new)}</b> 🪙\n"
        f"• مجموع جدید پول خزانه‌ها: <b>{fmt(money_new)}</b> 💰"
    )
    markup = kb([
        [("👥 منوی کاربران", "a|usr")],
        [("🪙 منوی اقتصاد", "a|eco")],
        [("📊 پنل اصلی", "a|root")],
    ])
    await call.answer("✅ با موفقیت اعمال شد", show_alert=True)
    await call.message.edit_text(text, reply_markup=markup)


# ─── ریست کلی تمام بازیکنان (شروع مجدد / سیزن جدید) ───


@router.message(Command("reset_players"))
async def cmd_reset_players(message: Message, perms: set):
    if not has(perms, "users"):
        return await message.answer("⛔️ دسترسی ندارید")
    text, markup = await build_reset_players_payload()
    await message.answer(text, reply_markup=markup)


async def build_reset_players_payload() -> tuple[str, any]:
    u_total = (await db.fetchone("SELECT COUNT(*) c FROM users"))["c"]
    c_taken = (await db.fetchone("SELECT COUNT(*) c FROM users WHERE country_id IS NOT NULL"))["c"]
    assets_c = (await db.fetchone("SELECT COUNT(*) c FROM player_assets"))["c"]
    projects_c = (await db.fetchone("SELECT COUNT(*) c FROM player_projects"))["c"]
    companies_c = (await db.fetchone("SELECT COUNT(*) c FROM companies"))["c"]

    text = (
        "♻️ <b>ریست همگانی تمام بازیکنان بازی</b>\n\n"
        "⚠️ <b>هشدار بسیار مهم:</b>\n"
        "این عملیات بازی را برای تمام بازیکنان از نو آغاز می‌کند (شروع دوره یا سیزن جدید):\n\n"
        f"• مالکیت تمام <b>{fmt(c_taken)}</b> کشور اشغال‌شده لغو و همه کشورها آزاد خواهند شد.\n"
        f"• تمام <b>{fmt(assets_c)}</b> دارایی نظامی، سربازان و تجهیزات کاربران حذف می‌شوند.\n"
        f"• تمام <b>{fmt(projects_c)}</b> پروژه و آموزش نظامی پاکسازی خواهند شد.\n"
        f"• تمام <b>{fmt(companies_c)}</b> شرکت خصوصی، پایگاه و پیمان پاک می‌شوند.\n"
        "• پول پایه تمام کاربران به ۵۰٬۰۰۰٬۰۰۰ و سکه شاهی به ۰ بازنشانی می‌شود.\n"
        "• وضعیت‌های سیاسی، خزانه‌ها، رضایت، دین و قوانین ریست می‌شوند.\n"
        "• حکم محرومیت (بن) تمام کاربران لغو می‌گردد.\n"
        "• حساب‌های تلگرام بازیکنان (<b>" + fmt(u_total) + "</b> نفر) باقی می‌ماند تا بلافاصله بتوانند کشور انتخاب کنند.\n\n"
        "آیا از ریست کامل تمام بازیکنان اطمینان کامل دارید؟"
    )
    markup = kb([
        [("⚠️ بله، تمام بازیکنان و کشورها را ریست کن", "a|exec_reset_all_players")],
        [("❌ خیر، انصراف و بازگشت", "a|usr")],
    ])
    return text, markup


@router.callback_query(F.data == "a|reset_players_prompt")
async def reset_players_prompt(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    text, markup = await build_reset_players_payload()
    await call.answer()
    await call.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "a|exec_reset_all_players")
async def reset_all_players_execute(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)

    u_total = (await db.fetchone("SELECT COUNT(*) c FROM users"))["c"]
    c_taken = (await db.fetchone("SELECT COUNT(*) c FROM countries WHERE owner_id IS NOT NULL"))["c"]

    # 1. Free all countries
    await db.execute("UPDATE countries SET owner_id=NULL")

    # 2. Reset users table
    await db.execute(
        "UPDATE users SET country_id=NULL, country_taken_at=NULL, royal_coins=0, money=?, banned=0",
        (await get_initial_money(),),
    )

    # 3. Clean all gameplay dependent tables
    dependent_tables = [
        "player_assets",
        "player_projects",
        "soldier_trainings",
        "companies",
        "bases",
        "states",
        "treaties",
        "strait_blockades",
        "wars",
        "war_alliances",
        "market_orders",
        "currency_requests",
    ]
    for tbl in dependent_tables:
        try:
            await db.execute(f"DELETE FROM {tbl}")
        except Exception:
            pass

    # 4. Sync snapshot to Firebase if enabled
    try:
        from core.firebase import fb
        await fb.push_snapshot()
    except Exception:
        pass

    # 5. Log actions & event
    from core.events import log_event
    await log_action(call.from_user.id, "ریست", f"ریست همگانی تمام {u_total} بازیکن و آزادسازی {c_taken} کشور")
    await log_event("season", "دنیای بازی توسط ادمین به طور کامل ریست شد و تمامی کشورها آزاد گردیدند")

    text = (
        "🎉 <b>ریست همگانی تمام بازیکنان با موفقیت انجام شد!</b>\n\n"
        f"• وضعیت تمام <b>{fmt(u_total)}</b> بازیکن صفر و آماده شروع نو شد.\n"
        f"• تمام <b>{fmt(c_taken)}</b> کشور قبلاً اشغال‌شده آزاد شدند.\n"
        "• تمام تجهیزات، ساختمان‌ها، ارتش، شرکت‌ها و جنگ‌ها پاکسازی شدند.\n"
        "• پول همه کاربران ۵۰٬۰۰۰٬۰۰۰ و سکه شاهی ۰ شد.\n"
        "• بازی اکنون در وضعیت کاملاً آماده برای شروع سیزن جدید قرار دارد."
    )
    markup = kb([
        [("👥 منوی کاربران", "a|usr")],
        [("🏳 کشورها و قیمت‌ها", "a|grp|countries")],
        [("📊 پنل اصلی", "a|root")],
    ])
    await call.answer("🎉 تمام بازیکنان با موفقیت ریست شدند", show_alert=True)
    await call.message.edit_text(text, reply_markup=markup)


class _FakeCall:
    def __init__(self, message: Message):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot

    async def answer(self, *_a, **_k):
        pass

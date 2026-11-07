"""پنل مدیریت سریع داخل ربات اصلی بازی — دستور /panel.

فقط برای ادمین‌های ثبت‌شده (و سوپرادمین‌های ثابت کانفیگ) باز است و همهٔ کارهای
اداری پرکاربرد را بدون رفتن به ربات ادمین در دسترس می‌گذارد:
واریز/برداشت پول و سکه شاهی، رضایت، تجهیزات، دکل نفتی، مسدودی، آزادکردن قفل‌ها،
تأیید فیش‌ها، پیام همگانی و تنظیمات سریع.

⚠️ سیاست لاگ: **دادن/گرفتن پول و سکه، رضایت، تجهیزات، بن، آزادسازی قفل، تنظیمات
و مدیریت ادمین‌ها هیچ لاگی نمی‌سازند**؛ فقط دو نوع رکورد در «لاگ ادمین‌ها» می‌ماند:
تأیید/رد **فیش** و عملیات مربوط به **کاربران عادی** (که از ربات ادمین ثبت می‌شود).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.admins import is_admin, is_super_admin
from core.db import db, get_setting, set_setting
from core.utils import fmt, fmt_money, iso
from gamebot.common import home_row, kb, send_home

router = Router()


class PanelFSM(StatesGroup):
    target = State()      # گرفتن آیدی/یوزرنیم کاربر هدف
    amount = State()      # گرفتن مبلغ/تعداد
    eq_qty = State()      # تعداد تجهیز انتخاب‌شده
    text = State()        # متن پیام همگانی
    value = State()       # مقدار تنظیمات


OP_LABELS = {
    "money_add": "💰 واریز پول به خزانه",
    "money_sub": "💸 برداشت پول از خزانه",
    "coin_add": "🪙 دادن سکه شاهی",
    "coin_sub": "🔻 گرفتن سکه شاهی",
    "sat_add": "📈 افزایش رضایت",
    "sat_sub": "📉 کاهش رضایت",
    "eq_add": "🎖 افزودن تجهیزات",
    "rig_add": "🏗 افزودن دکل نفتی",
    "ban": "🚫 مسدودکردن کاربر",
    "unban": "✅ رفع مسدودی",
    "unlock": "🔓 آزادکردن قفل‌ها",
    "card": "🔍 کارت کاربر",
}

INSTANT_OPS = {"ban", "unban", "unlock", "card"}

QUICK_SETTINGS = {
    "initial_money": "💰 بودجهٔ اولیهٔ بازیکن (تومان)",
    "coin_price_toman": "🪙 قیمت هر سکه شاهی (تومان)",
    "war_vote_minutes": "🗳 مدت رأی مجوز جنگ (دقیقه)",
    "income_interval_minutes": "⏱ فاصلهٔ درآمد خودکار (دقیقه)",
    "revolution_minutes": "🔥 مهلت مهار انقلاب (دقیقه)",
    "oil_auto_sell_minutes": "🛢 فاصلهٔ فروش خودکار نفت (دقیقه)",
}


# ─── کمکی‌ها ───


def parse_amount(raw: str) -> int | None:
    """تبدیل «2m»/«500k»/«1.5b»/«250000» به عدد (m=میلیون، k=هزار، b=میلیارد)."""
    text = (raw or "").strip().lower().replace(",", "").replace("،", "")
    text = text.replace("تومان", "").replace("میلیون", "m").replace("میلیارد", "b") \
               .replace("هزار", "k").replace("سکه", "").strip()
    if not text:
        return None
    mult = 1
    if text[-1] in ("k", "m", "b"):
        mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[text[-1]]
        text = text[:-1].strip()
    try:
        value = float(text)
    except ValueError:
        return None
    return int(value * mult)


async def resolve_target(raw: str) -> dict | None:
    """پیداکردن کاربر با آیدی عددی، یوزرنیم یا لینک تلگرام."""
    text = (raw or "").strip()
    if not text:
        return None
    if "t.me/" in text:
        text = text.split("t.me/")[-1].split("/")[0]
    text = text.lstrip("@")
    user = None
    if text.isdigit():
        user = await db.fetchone("SELECT * FROM users WHERE id=?", (int(text),))
    if not user:
        user = await db.fetchone(
            "SELECT * FROM users WHERE LOWER(COALESCE(username,''))=LOWER(?)", (text,))
    return user


async def _guard(call_or_msg) -> bool:
    user = getattr(call_or_msg, "from_user", None)
    if user and await is_admin(user.id):
        return True
    if isinstance(call_or_msg, CallbackQuery):
        await call_or_msg.answer("⛔️ این پنل مخصوص ادمین‌های بازی است.", show_alert=True)
    else:
        await call_or_msg.answer("⛔️ این پنل مخصوص ادمین‌های بازی است.")
    return False


async def panel_text(user_id: int) -> str:
    users = (await db.fetchone("SELECT COUNT(*) c FROM users WHERE banned=0"))["c"]
    money = (await db.fetchone("SELECT COALESCE(SUM(money),0) c FROM users"))["c"]
    coins = (await db.fetchone("SELECT COALESCE(SUM(royal_coins),0) c FROM users"))["c"]
    pending = (await db.fetchone("SELECT COUNT(*) c FROM receipts WHERE status='pending'"))["c"]
    revs = (await db.fetchone("SELECT COUNT(*) c FROM revolutions WHERE status='active'"))["c"]
    owned = (await db.fetchone(
        "SELECT COUNT(*) c FROM users WHERE country_id IS NOT NULL AND banned=0"))["c"]
    role = "👑 سوپرادمین" if await is_super_admin(user_id) else "🛡 ادمین"
    return (
        f"🛡 <b>پنل مدیریت سریع</b> — {role}\n\n"
        f"👥 بازیکنان فعال: <b>{fmt(users)}</b> | 🏳 کشورهای واگذارشده: <b>{fmt(owned)}</b>\n"
        f"💰 مجموع خزانه‌ها: <b>{fmt_money(money)}</b>\n"
        f"🪙 مجموع سکه شاهی: <b>{fmt(coins)}</b>\n"
        f"🧾 فیش‌های منتظر: <b>{fmt(pending)}</b> | 🔥 انقلاب‌های فعال: <b>{fmt(revs)}</b>\n\n"
        "یکی از عملیات را انتخاب کنید (بدون ثبت در لاگ ادمین‌ها):"
    )


def panel_kb(superadmin: bool = False) -> object:
    """کیبورد پنل؛ `superadmin` برای سازگاری عقب‌رو نگه داشته شده است."""
    rows = [
        [("💰 واریز پول", "p|op|money_add"), ("💸 برداشت پول", "p|op|money_sub")],
        [("🪙 دادن سکه", "p|op|coin_add"), ("🔻 گرفتن سکه", "p|op|coin_sub")],
        [("📈 افزایش رضایت", "p|op|sat_add"), ("📉 کاهش رضایت", "p|op|sat_sub")],
        [("🎖 افزودن تجهیزات", "p|op|eq_add"), ("🏗 افزودن دکل نفتی", "p|op|rig_add")],
        [("🚫 مسدودکردن", "p|op|ban"), ("✅ رفع مسدودی", "p|op|unban")],
        [("🔓 آزادکردن قفل‌ها", "p|op|unlock"), ("🔍 کارت کاربر", "p|op|card")],
        [("🧾 فیش‌های منتظر", "p|rec"), ("📢 پیام همگانی", "p|bc")],
        [("📜 لاگ فیش و کاربران", "p|logs"), ("👑 مدیریت ادمین‌ها", "p|admins")],
        [("⚙️ تنظیمات سریع", "p|setmenu")],
        [("🧨 ریست کل بازی (پاک‌سازی ۱۰۰٪)", "p|resetmenu")],
    ]
    rows.append(home_row())
    return kb(rows)


@router.message(Command("panel"))
async def panel_command(message: Message, state: FSMContext):
    if not await _guard(message):
        return
    await state.clear()
    await send_home(message, await panel_text(message.from_user.id),
                    reply_markup=panel_kb(await is_super_admin(message.from_user.id)))


@router.callback_query(F.data == "p|home")
async def panel_home(call: CallbackQuery, state: FSMContext):
    if not await _guard(call):
        return
    await state.clear()
    await call.answer()
    superadmin = await is_super_admin(call.from_user.id)
    try:
        await call.message.edit_text(await panel_text(call.from_user.id),
                                     reply_markup=panel_kb(superadmin))
    except Exception:
        await send_home(call.message, await panel_text(call.from_user.id),
                        reply_markup=panel_kb(superadmin))


# ─── شروع عملیات‌ها ───


@router.callback_query(F.data.startswith("p|op|"))
async def panel_op(call: CallbackQuery, state: FSMContext):
    if not await _guard(call):
        return
    op = call.data.split("|")[2]
    if op not in OP_LABELS:
        return await call.answer("عملیات نامعتبر", show_alert=True)
    await state.set_state(PanelFSM.target)
    await state.update_data(op=op)
    await call.answer()
    hint = ("🔍 آیدی عددی یا یوزرنیم کاربر را بفرستید:" if op in INSTANT_OPS else
            "🔍 آیدی عددی یا یوزرنیم کاربر هدف را بفرستید:")
    await call.message.edit_text(
        f"{OP_LABELS[op]}\n\n{hint}\n"
        "• عدد → آیدی عددی | @name → یوزرنیم\n• برای انصراف /cancel")


@router.message(PanelFSM.target)
async def panel_target(message: Message, state: FSMContext):
    if not await _guard(message):
        return
    data = await state.get_data()
    op = data.get("op", "")
    target = await resolve_target(message.text or "")
    if not target:
        return await send_home(message, "❌ کاربری با این آیدی/یوزرنیم پیدا نشد. دوباره بفرستید یا /cancel")
    uid = int(target["id"])

    if op == "admadd":
        await state.clear()
        if not await is_super_admin(message.from_user.id):
            return await send_home(message, "⛔️ فقط سوپرادمین می‌تواند ادمین اضافه کند.")
        from core.admins import grant_admin
        await grant_admin(uid, target.get("full_name") or "")
        return await send_home(message, f"👑 <code>{uid}</code> با دسترسی ۱۰۰٪ ادمین شد.",
                               reply_markup=panel_kb())

    if op == "card":
        await state.clear()
        return await send_home(message, await user_card(uid), reply_markup=panel_kb())

    if op in ("ban", "unban"):
        await state.clear()
        banned = 1 if op == "ban" else 0
        await db.execute("UPDATE users SET banned=? WHERE id=?", (banned, uid))
        await send_home(message,
                        f"{'🚫 کاربر مسدود شد' if banned else '✅ مسدودی برداشته شد'}: "
                        f"<code>{uid}</code>", reply_markup=panel_kb())
        return

    if op == "unlock":
        await state.clear()
        await db.execute(
            "UPDATE states SET leader_block_until=NULL, server_jam_until=NULL, disarmed_until=NULL, "
            "trade_banned='[]' WHERE user_id=?", (uid,))
        await db.execute(
            "UPDATE revolutions SET status='cancelled' WHERE user_id=? AND status='active'", (uid,))
        await send_home(message, f"🔓 همهٔ قفل‌ها و انقلاب فعال کاربر <code>{uid}</code> آزاد شد.",
                        reply_markup=panel_kb())
        return

    if op == "eq_add":
        eqs = await db.fetchall(
            "SELECT e.*, c.title AS cat_title FROM equipment e "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id ORDER BY c.id, e.id LIMIT 40")
        buttons = [[(f"{e['emoji']} {e['name']}", f"p|eqi|{e['id']}")] for e in eqs]
        buttons.append([("🏰 بازگشت به پنل", "p|home")])
        await state.update_data(target=uid)
        await state.set_state(None)
        await send_home(message, f"🎖 برای کاربر <code>{uid}</code> کدام تجهیز اضافه شود؟",
                        reply_markup=kb(buttons))
        return

    await state.update_data(target=uid)
    await state.set_state(PanelFSM.amount)
    unit = "مبلغ" if op in ("money_add", "money_sub") else "تعداد"
    await send_home(
        message,
        f"{OP_LABELS[op]} برای <code>{uid}</code>\n\n"
        f"{unit} را بفرستید (مثال: 50000000 یا 50m یا 3k).\nبرای انصراف /cancel")


@router.callback_query(F.data.startswith("p|eqi|"))
async def panel_eq_pick(call: CallbackQuery, state: FSMContext):
    if not await _guard(call):
        return
    eid = int(call.data.split("|")[2])
    data = await state.get_data()
    uid = int(data.get("target") or 0)
    eq = await db.fetchone("SELECT * FROM equipment WHERE id=?", (eid,))
    if not eq or not uid:
        return await call.answer("اطلاعات ناقص است — از ابتدا شروع کنید", show_alert=True)
    await state.update_data(eq_id=eid)
    await state.set_state(PanelFSM.eq_qty)
    await call.answer()
    await call.message.edit_text(
        f"{eq['emoji']} <b>{eq['name']}</b> → کاربر <code>{uid}</code>\n\n"
        "تعداد را بفرستید (مثال: 10):")


async def _apply_amount(message: Message, op: str, uid: int, amount: int) -> str:
    """اعمال عملیات عددی؛ خروجی متن گزارش."""
    if op in ("money_add", "money_sub"):
        if op == "money_add":
            await db.execute("UPDATE users SET money=COALESCE(money,0)+? WHERE id=?", (amount, uid))
        else:
            await db.execute("UPDATE users SET money=MAX(0, COALESCE(money,0)-?) WHERE id=?", (amount, uid))
        row = await db.fetchone("SELECT money FROM users WHERE id=?", (uid,))
        return (f"{OP_LABELS[op]}: <b>{fmt_money(amount)}</b>\n"
                f"💰 خزانهٔ جدید کاربر <code>{uid}</code>: <b>{fmt_money(row['money'] if row else 0)}</b>")
    if op in ("coin_add", "coin_sub"):
        if op == "coin_add":
            await db.execute("UPDATE users SET royal_coins=COALESCE(royal_coins,0)+? WHERE id=?",
                             (amount, uid))
        else:
            await db.execute("UPDATE users SET royal_coins=MAX(0, COALESCE(royal_coins,0)-?) WHERE id=?",
                             (amount, uid))
        row = await db.fetchone("SELECT royal_coins FROM users WHERE id=?", (uid,))
        return (f"{OP_LABELS[op]}: <b>{fmt(amount)}</b> 🪙\n"
                f"موجودی جدید کاربر <code>{uid}</code>: <b>{fmt(row['royal_coins'] if row else 0)}</b>")
    if op in ("sat_add", "sat_sub"):
        from core.economy import get_state
        await get_state(uid)
        delta = amount if op == "sat_add" else -amount
        await db.execute(
            "UPDATE states SET satisfaction=MAX(0, MIN(100, COALESCE(satisfaction,50)+?)) WHERE user_id=?",
            (delta, uid))
        row = await db.fetchone("SELECT satisfaction FROM states WHERE user_id=?", (uid,))
        return (f"{OP_LABELS[op]}: {delta:+d}\n"
                f"😊 رضایت جدید کاربر <code>{uid}</code>: <b>{round(row['satisfaction'] or 0)}/100</b>")
    if op == "rig_add":
        b = await db.fetchone("SELECT * FROM buildings WHERE name='دکل نفتی'")
        if not b:
            return "❌ ساختمان «دکل نفتی» در دیتابیس نیست."
        from core.economy import add_asset
        await add_asset(uid, "building", b["id"], amount)
        return f"🏗 {fmt(amount)} دکل نفتی به کاربر <code>{uid}</code> اضافه شد."
    return "عملیات ناشناخته"


@router.message(PanelFSM.amount)
async def panel_amount(message: Message, state: FSMContext):
    if not await _guard(message):
        return
    data = await state.get_data()
    op = data.get("op", "")
    uid = int(data.get("target") or 0)
    amount = parse_amount(message.text or "")
    if amount is None or amount <= 0:
        return await send_home(message, "❌ عدد معتبر بفرستید (مثال: 50m یا 50000000). یا /cancel")
    await state.clear()
    report = await _apply_amount(message, op, uid, amount)
    await send_home(message, f"✅ {report}", reply_markup=panel_kb())


@router.message(PanelFSM.eq_qty)
async def panel_eq_qty(message: Message, state: FSMContext):
    if not await _guard(message):
        return
    data = await state.get_data()
    uid = int(data.get("target") or 0)
    eid = int(data.get("eq_id") or 0)
    qty = parse_amount(message.text or "")
    if not qty or qty <= 0:
        return await send_home(message, "❌ تعداد معتبر بفرستید. یا /cancel")
    await state.clear()
    from core.economy import add_asset, bump_progress
    eq = await db.fetchone("SELECT * FROM equipment WHERE id=?", (eid,))
    await add_asset(uid, "equipment", eid, qty)
    try:
        await bump_progress(uid, "bought", qty)
    except Exception:
        pass
    await send_home(message,
                    f"✅ {fmt(qty)}× {eq['emoji'] if eq else '🎖'} {eq['name'] if eq else eid} "
                    f"به کاربر <code>{uid}</code> اضافه شد.", reply_markup=panel_kb())


async def user_card(uid: int) -> str:
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (uid,))
    if not user:
        return "❌ کاربر در دیتابیس نیست."
    country = await db.fetchone("SELECT * FROM countries WHERE id=?", (user.get("country_id") or 0,))
    state = await db.fetchone("SELECT * FROM states WHERE user_id=?", (uid,))
    rev = await db.fetchone(
        "SELECT * FROM revolutions WHERE user_id=? AND status='active' ORDER BY id DESC", (uid,))
    from core.politics import country_leader
    leader = await country_leader(country)
    return (
        f"🔍 <b>کارت کاربر</b>\n\n"
        f"👤 نام: <b>{user.get('full_name') or '—'}</b>\n"
        f"🆔 آیدی: <code>{uid}</code> | یوزرنیم: @{user.get('username') or '—'}\n"
        f"🏳 کشور: {(country['flag'] + ' ' + country['name']) if country else '—'}\n"
        + (f"🏛 {leader['title']}: {leader['name']}\n" if country else "")
        + f"💰 خزانه: <b>{fmt_money(user.get('money') or 0)}</b> | 🪙 سکه: <b>{fmt(user.get('royal_coins') or 0)}</b>\n"
        f"😊 رضایت: <b>{round((state or {}).get('satisfaction') or 0)}/100</b>\n"
        f"🚫 مسدود: {'بله' if user.get('banned') else 'خیر'}"
        + (f"\n🔥 انقلاب فعال — شدت {rev['severity']}٪" if rev else "")
    )


# ─── فیش‌ها ───


@router.callback_query(F.data == "p|rec")
async def panel_receipts_route(call: CallbackQuery):
    await panel_receipts(call)


async def panel_receipts(call: CallbackQuery, answer: bool = True):
    if answer:
        if not await _guard(call):
            return
        await call.answer()
    rows = await db.fetchall(
        "SELECT r.*, u.full_name FROM receipts r LEFT JOIN users u ON u.id=r.user_id "
        "WHERE r.status='pending' ORDER BY r.id DESC LIMIT 10")
    if not rows:
        return await call.message.edit_text("🧾 فیش منتظر تأییدی وجود ندارد.", reply_markup=panel_kb())
    lines = [f"🧾 <b>{len(rows)} فیش منتظر تأیید</b>\n"]
    buttons = []
    for r in rows:
        kind = "کشور" if r["kind"] == "country" else "سکه شاهی"
        lines.append(f"#{r['id']} — {r['full_name'] or r['user_id']} | {kind} | "
                     f"🪙 {fmt(r['coins'] or 0)} | 💳 {fmt(r['toman'] or 0)}")
        buttons.append([(f"✅ تأیید #{r['id']}", f"p|recok|{r['id']}"),
                        (f"❌ رد #{r['id']}", f"p|recno|{r['id']}")])
    buttons.append([("🏰 بازگشت به پنل", "p|home")])
    await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("p|recok|") | F.data.startswith("p|recno|"))
async def panel_receipt_action(call: CallbackQuery):
    if not await _guard(call):
        return
    approve = call.data.startswith("p|recok|")
    rid = int(call.data.split("|")[2])
    r = await db.fetchone("SELECT * FROM receipts WHERE id=?", (rid,))
    if not r or r["status"] != "pending":
        return await call.answer("این فیش قبلاً بررسی شده است.", show_alert=True)
    if not approve:
        await db.execute(
            "UPDATE receipts SET status='rejected', reviewed_by=?, reviewed_at=? WHERE id=?",
            (call.from_user.id, iso(), rid))
        await _log_receipt(call.from_user.id, f"رد فیش #{rid} کاربر {r['user_id']}")
        await call.answer("❌ فیش رد شد")
        return await panel_receipts(call, answer=False)
    # تأیید بدون ثبت در لاگ ادمین‌ها
    await db.execute(
        "UPDATE receipts SET status='approved', reviewed_by=?, reviewed_at=? WHERE id=?",
        (call.from_user.id, iso(), rid))
    result = ""
    if r["kind"] == "country":
        country = await db.fetchone("SELECT * FROM countries WHERE id=?", (r["country_id"] or 0,))
        cur_owner = (country or {}).get("owner_id")
        if country and (not cur_owner or cur_owner == r["user_id"]):
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
            await db.execute(
                "UPDATE states SET currency_name=?, materials=COALESCE(materials,0)+1000, "
                "energy=COALESCE(energy,0)+5000, water=COALESCE(water,0)+5000, "
                "gas=COALESCE(gas,0)+5000 WHERE user_id=?",
                (country.get("currency") or country["name"], r["user_id"]))
            result = f"✅ فیش #{rid} تأیید و کشور به کاربر واگذار شد."
        else:
            result = f"⚠️ فیش #{rid} تأیید شد اما کشور قبلاً واگذار شده بود."
    else:
        coins = int(r["coins"] or 0)
        if coins <= 0 and (r["toman"] or 0) > 0:
            price = int(await get_setting("coin_price_toman", "1000")) or 1
            coins = max(1, int(r["toman"] // price))
        await db.execute("UPDATE users SET royal_coins=COALESCE(royal_coins,0)+? WHERE id=?",
                         (coins, r["user_id"]))
        result = f"✅ فیش #{rid} تأیید و {fmt(coins)} سکه شاهی واریز شد."
    await _log_receipt(call.from_user.id, f"تأیید فیش #{rid} کاربر {r['user_id']}")
    await call.answer(result[:180], show_alert=True)
    await panel_receipts(call, answer=False)


# ─── پیام همگانی ───


@router.callback_query(F.data == "p|bc")
async def panel_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not await _guard(call):
        return
    await state.set_state(PanelFSM.text)
    await call.answer()
    await call.message.edit_text(
        "📢 متن پیام همگانی را بفرستید. این پیام برای همهٔ بازیکنان ارسال می‌شود.\n"
        "برای انصراف /cancel")


@router.message(PanelFSM.text)
async def panel_broadcast_send(message: Message, state: FSMContext):
    if not await _guard(message):
        return
    text = (message.text or "").strip()
    if not text:
        return await send_home(message, "❌ متن خالی است. دوباره بفرستید یا /cancel")
    await state.clear()
    users = await db.fetchall("SELECT id FROM users WHERE banned=0")
    sent = 0
    for row in users:
        try:
            await message.bot.send_message(row["id"], text)
            sent += 1
        except Exception:
            continue
    await send_home(message, f"📢 پیام همگانی برای {fmt(sent)} کاربر از {fmt(len(users))} ارسال شد.",
                    reply_markup=panel_kb())


# ─── تنظیمات سریع ───


@router.callback_query(F.data == "p|setmenu")
async def panel_settings(call: CallbackQuery):
    if not await _guard(call):
        return
    buttons = []
    for key, title in QUICK_SETTINGS.items():
        value = await get_setting(key, "—")
        buttons.append([(f"{title}: {value}", f"p|set|{key}")])
    buttons.append([("🏰 بازگشت به پنل", "p|home")])
    await call.answer()
    await call.message.edit_text("⚙️ <b>تنظیمات سریع</b>\n\nروی هر مورد بزنید و مقدار جدید را بفرستید:",
                                 reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("p|set|"))
async def panel_setting_pick(call: CallbackQuery, state: FSMContext):
    if not await _guard(call):
        return
    key = call.data.split("|")[2]
    if key not in QUICK_SETTINGS:
        return await call.answer("تنظیم نامعتبر", show_alert=True)
    await state.set_state(PanelFSM.value)
    await state.update_data(setting_key=key)
    await call.answer()
    await call.message.edit_text(
        f"⚙️ مقدار جدید برای «{QUICK_SETTINGS[key]}» را بفرستید:\n"
        f"مقدار فعلی: <b>{await get_setting(key, '—')}</b>\nبرای انصراف /cancel")


@router.message(PanelFSM.value)
async def panel_setting_save(message: Message, state: FSMContext):
    if not await _guard(message):
        return
    data = await state.get_data()
    key = data.get("setting_key", "")
    raw = (message.text or "").strip()
    if key not in QUICK_SETTINGS or not raw:
        await state.clear()
        return await send_home(message, "❌ مقدار نامعتبر است.", reply_markup=panel_kb())
    await set_setting(key, raw)
    await state.clear()
    await send_home(message, f"✅ «{QUICK_SETTINGS[key]}» به <b>{raw}</b> تغییر کرد.",
                    reply_markup=panel_kb())


# ─── لاگ‌ها (فقط فیش و کاربران عادی) و مدیریت ادمین‌ها ───


async def _log_receipt(admin_id: int, detail: str) -> None:
    """تنها نوشتن مجاز در admin_logs از این پنل: رکورد فیش‌ها."""
    await db.execute(
        "INSERT INTO admin_logs(admin_id, action, detail) VALUES(?, 'فیش', ?)",
        (admin_id, detail[:500]))


LOG_ACTIONS = ("فیش", "کاربر")


@router.callback_query(F.data == "p|logs")
async def panel_logs(call: CallbackQuery):
    if not await _guard(call):
        return
    rows = await db.fetchall(
        "SELECT l.*, a.name FROM admin_logs l LEFT JOIN admins a ON a.id=l.admin_id "
        "WHERE l.action IN (?, ?) ORDER BY l.id DESC LIMIT 15", LOG_ACTIONS)
    lines = ["📜 <b>لاگ‌ها — فقط فیش و کاربران</b>\n",
             "طبق تنظیمات، لاگ عملیات مالی/اداری این پنل ثبت نمی‌شود.\n"]
    if not rows:
        lines.append("— رکوردی وجود ندارد —")
    for r in rows:
        icon = "🧾" if r["action"] == "فیش" else "👥"
        lines.append(f"{icon} #{r['id']} | {r['name'] or r['admin_id']} | "
                     f"{r['action']}: {r['detail']}")
    buttons = [[("🧾 فیش‌های منتظر", "p|rec")], [("🏰 بازگشت به پنل", "p|home")]]
    await call.answer()
    await safe_edit_panel(call, "\n".join(lines), buttons)


async def safe_edit_panel(call: CallbackQuery, text: str, buttons: list):
    try:
        await call.message.edit_text(text, reply_markup=kb(buttons))
    except Exception:
        await send_home(call.message, text, reply_markup=kb(buttons))


@router.callback_query(F.data == "p|admins")
async def panel_admins(call: CallbackQuery):
    if not await _guard(call):
        return
    from core.admins import list_admins
    if not await is_super_admin(call.from_user.id):
        return await call.answer("⛔️ فقط سوپرادمین‌ها ادمین‌ها را می‌بینند.", show_alert=True)
    rows = await list_admins()
    lines = ["👑 <b>مدیریت ادمین‌ها (دسترسی ۱۰۰٪)</b>\n"]
    buttons = []
    for a in rows:
        is_super = int(a.get("is_super") or 0)
        lines.append(f"{'👑' if is_super else '🛡'} <code>{a['id']}</code> — {a.get('name') or '—'}")
        if not is_super:
            buttons.append([(f"🗑 حذف ادمین {a['id']}", f"p|admdel|{a['id']}")])
    buttons.append([("➕ افزودن ادمین جدید", "p|admadd")])
    buttons.append([("🏰 بازگشت به پنل", "p|home")])
    await call.answer()
    await safe_edit_panel(call, "\n".join(lines), buttons)


@router.callback_query(F.data == "p|admadd")
async def panel_admin_add(call: CallbackQuery, state: FSMContext):
    if not await _guard(call):
        return
    if not await is_super_admin(call.from_user.id):
        return await call.answer("⛔️ فقط سوپرادمین.", show_alert=True)
    await state.set_state(PanelFSM.target)
    await state.update_data(op="admadd")
    await call.answer()
    await call.message.edit_text(
        "👑 آیدی عددی ادمین جدید را بفرستید (یا @username):\n"
        "این آیدی دسترسی ۱۰۰٪ به هر دو ربات می‌گیرد.\nبرای انصراف /cancel")


@router.callback_query(F.data.startswith("p|admdel|"))
async def panel_admin_del(call: CallbackQuery):
    if not await _guard(call):
        return
    if not await is_super_admin(call.from_user.id):
        return await call.answer("⛔️ فقط سوپرادمین.", show_alert=True)
    from core.admins import revoke_admin
    uid = int(call.data.split("|")[2])
    if not await revoke_admin(uid):
        return await call.answer("سوپرادمین ثابت کانفیگ حذف‌شدنی نیست.", show_alert=True)
    await call.answer("🗑 دسترسی ادمین گرفته شد")
    await panel_admins(call)


# ═══════════════ 🧨 ریست کامل (پاک‌سازی ۱۰۰٪ پیشرفت بازیکنان) ═══════════════
#
# باگ گزارش‌شده: پس از ریست، ☢️ تأسیسات هسته‌ای، 🛢 سطح تجهیزات استخراج،
# 🌐 اینترنت و 🗺 استان‌ها باقی می‌ماندند و کشور تازه «سقوط‌کرده» دیده می‌شد.
# این بخش از موتور مشترک `core.fullreset` استفاده می‌کند تا هیچ داده‌ای جا نماند.

async def _reset_preview() -> str:
    """خلاصهٔ وضعیت فعلی برای صفحهٔ تأیید ریست."""
    u_total = (await db.fetchone("SELECT COUNT(*) c FROM users"))["c"]
    taken = (await db.fetchone(
        "SELECT COUNT(*) c FROM users WHERE country_id IS NOT NULL"))["c"]
    assets = (await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets"))["c"]
    enrich = (await db.fetchone("SELECT COUNT(*) c FROM enrichment"))["c"]
    nukes = (await db.fetchone(
        "SELECT COUNT(*) c FROM nuclear_sites WHERE active=1"))["c"]
    oil = (await db.fetchone(
        "SELECT COALESCE(SUM(level),0) c FROM oil_business"))["c"]
    net = (await db.fetchone(
        "SELECT COALESCE(SUM(level),0) c FROM internet_infra"))["c"]
    provs = (await db.fetchone(
        "SELECT COUNT(*) c FROM provinces WHERE owner_id IS NOT NULL"))["c"]
    wars = (await db.fetchone(
        "SELECT COUNT(*) c FROM wars WHERE status='active'"))["c"]
    coins = (await db.fetchone(
        "SELECT COALESCE(SUM(royal_coins),0) c FROM users"))["c"]
    money = (await db.fetchone(
        "SELECT COALESCE(SUM(money),0) c FROM users"))["c"]
    return (
        "🧨 <b>ریست کامل بازی (پاک‌سازی ۱۰۰٪)</b>\n\n"
        "این عملیات <b>همهٔ پیشرفت بازیکنان</b> را پاک می‌کند و بازی از صفر شروع می‌شود:\n\n"
        f"👥 بازیکنان: <b>{fmt(u_total)}</b> | 🏳 کشورهای واگذارشده: <b>{fmt(taken)}</b>\n"
        f"🎖 تجهیزات و سربازان: <b>{fmt(assets)}</b> واحد\n"
        f"☢️ تأسیسات هسته‌ای فعال: <b>{fmt(nukes)}</b> | 🧬 ردیف غنی‌سازی: <b>{fmt(enrich)}</b>\n"
        f"🛢 مجموع سطح دکل‌های نفتی: <b>{fmt(oil)}</b> | "
        f"🌐 مجموع سطح اینترنت: <b>{fmt(net)}</b>\n"
        f"🗺 استان‌های در اختیار بازیکنان: <b>{fmt(provs)}</b> | "
        f"⚔️ جنگ‌های فعال: <b>{fmt(wars)}</b>\n"
        f"🪙 مجموع سکه شاهی: <b>{fmt(coins)}</b> | 💰 مجموع خزانه‌ها: <b>{fmt_money(money)}</b>\n\n"
        "⚠️ <b>چه چیزی پاک می‌شود:</b>\n"
        "• تجهیزات، سربازان، پروژه‌ها، شرکت‌ها، پایگاه‌ها و دکل‌های نفتی\n"
        "• ☢️ همهٔ تأسیسات هسته‌ای و پیشرفت غنی‌سازی\n"
        "• 🌐 سطوح اینترنت، 🛢 سطح تجهیزات استخراج و ⛓ فرسایش جنگ\n"
        "• 🗺 همهٔ استان‌های تصاحب‌شده، جنگ‌ها، پیمان‌ها، اتحادها، انقلاب‌ها و تنگه‌ها\n"
        "• 🪙 سکه شاهی، 💰 خزانه، رضایت مردم، دین و حکومت\n"
        "• 🏳 کشورها به حالت آزاد با ۵ استان پایه برمی‌گردند و همه می‌توانند\n"
        "  کشور تازه انتخاب کنند.\n\n"
        "✅ <b>چه چیزی می‌ماند:</b> حساب‌های تلگرام، لیست ادمین‌ها، تنظیمات بازی،\n"
        "فیش‌های مالی و لاگ‌ها.\n\n"
        "آیا از ریست کامل صد‌درصدی مطمئن هستید؟"
    )


async def _reset_kb() -> object:
    return kb([
        [("⚠️ بله، همه چیز را از صفر کن", "p|resetall")],
        [("🏰 بازگشت به پنل", "p|home")],
        home_row(),
    ])


@router.callback_query(F.data == "p|resetmenu")
async def panel_reset_menu(call: CallbackQuery):
    if not await _guard(call):
        return
    if not await is_super_admin(call.from_user.id):
        return await call.answer("⛔️ فقط سوپرادمین می‌تواند بازی را ریست کند.", show_alert=True)
    await call.answer()
    try:
        await call.message.edit_text(await _reset_preview(), reply_markup=await _reset_kb())
    except Exception:
        await send_home(call.message, await _reset_preview(), reply_markup=await _reset_kb())


@router.callback_query(F.data == "p|resetall")
async def panel_reset_execute(call: CallbackQuery):
    if not await _guard(call):
        return
    if not await is_super_admin(call.from_user.id):
        return await call.answer("⛔️ فقط سوپرادمین می‌تواند بازی را ریست کند.", show_alert=True)
    from core.fullreset import full_reset
    await call.answer("⏳ در حال ریست کامل بازی…")
    try:
        await call.message.edit_text("⏳ <b>ریست کامل در حال انجام است…</b>\n"
                                     "همهٔ داده‌های بازیکنان در حال پاک‌سازی است.")
    except Exception:
        pass
    stats = await full_reset(reset_wealth=True, keep_bans=True, log_errors=True)
    await db.execute(
        "INSERT INTO admin_logs(admin_id, action, detail) VALUES(?, 'ریست', ?)",
        (call.from_user.id,
         f"ریست کامل بازی: {stats['users']} کاربر، {stats['countries']} کشور، "
         f"{stats['tables']} جدول پاک شد"))
    text = (
        "🎉 <b>ریست کامل بازی انجام شد!</b>\n\n"
        f"👥 بازیکنان ریست‌شده: <b>{fmt(stats['users'])}</b>\n"
        f"🏳 کشورهای آزادشده: <b>{fmt(stats['countries'])}</b>\n"
        f"🎖 تجهیزات پاک‌شده: <b>{fmt(stats['assets'])}</b> واحد\n"
        f"🗄 جدول‌های پاک‌شده: <b>{fmt(stats['tables'])}</b>\n\n"
        f"💰 بودجهٔ اولیهٔ هر بازیکن: <b>{fmt_money(stats['initial_money'])}</b>\n"
        "🗺 همهٔ کشورها ۵ استان پایه دارند و آزاد هستند.\n"
        "همهٔ بازیکنان می‌توانند با /start کشور تازه بگیرند — "
        "☢️ هسته‌ای، 🛢 ارتقا و 🗺 استان‌ها دیگر باقی نمانده‌اند."
    )
    markup = kb([
        [("🏳 کشورها و قیمت‌ها", "p|home")],
        home_row(),
    ])
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:
        await send_home(call.message, text, reply_markup=markup)

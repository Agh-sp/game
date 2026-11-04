"""پنل اصلی ادمین: /start، /panel، آمار کلی، منوهای گروهی و مرورگر دیتابیس خام."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from adminbot.auth import ALL_PERMS, PERM_TITLES, has
from adminbot.entities import for_perm
from core.db import db
from core.utils import fmt
from adminbot.crud import cd, kb, raw_tables

router = Router()


@router.message(CommandStart())
@router.message(Command("panel"))
async def cmd_panel(message: Message, state: FSMContext, admin: dict, perms: set):
    await state.clear()
    await message.answer(root_text(admin), reply_markup=root_kb(perms))


@router.callback_query(F.data == "a|root")
async def panel_root(call: CallbackQuery, state: FSMContext, admin: dict, perms: set):
    await state.clear()
    await call.answer()
    await call.message.edit_text(root_text(admin), reply_markup=root_kb(perms))


def root_text(admin: dict) -> str:
    return (
        "🛡 <b>پنل مدیریت بازی جنگ جهانی</b>\n\n"
        "از اینجا می‌توانید <b>صددرصد همه چیز</b> بازی را بسازید، ویرایش کنید یا حذف کنید:\n"
        "🏳 کشورها و قیمت‌ها • 🪙 سکه شاهی و فیش‌ها • 🪖 تجهیزات نظامی (تکی/جمعی) • 🏗 ساختمان‌ها\n"
        "⚖️ قوانین • ⛪ ادیان • 🏛 حکومت‌ها • 🎯 ماموریت‌ها • 👥 کاربران و ...\n"
        "🖼 کتابخانه تصاویر • 🎬 سیزن‌ها • 🔘 روشن/خاموش کردن بخش‌ها • 🔥 فایربیس • 📋 گزارش روزانه\n\n"
        "💡 دستورهای سریع:\n"
        "/panel — پنل اصلی\n/stats — آمار کلی\n/u — جستجوی کاربر\n/reset_wealth — ریست پول و سکه همه\n"
        "/reset_players — ریست بازیکنان و کشورها\n/bc — پیام همگانی\n"
        "/receipts — فیش‌های در انتظار\n/tickets — تیکت‌ها\n/settings — تنظیمات\n/logs — لاگ‌ها\n"
        "/daily — گزارش ۲۴ ساعت اخیر\n/images — کتابخانه تصاویر")


def root_kb(perms: set) -> InlineKeyboardMarkup:
    def show(p):
        return has(perms, p)
    rows = []
    if show("users"):
        rows.append([("👥 کاربران", "a|usr")])
    if show("economy"):
        rows.append([("🪙 اقتصاد و سکه شاهی", "a|eco")])
        rows.append([("🧾 فیش‌های در انتظار تأیید", "a|rcp|pending|0")])
    if show("countries"):
        rows.append([("🏳 کشورها و قیمت‌ها", "a|grp|countries")])
    if show("military"):
        rows.append([("🪖 نظامی (تجهیزات: تکی/جمعی)", "a|grp|military")])
    if show("world"):
        rows.append([("🌍 دنیا و تنگه‌ها", "a|grp|world")])
    if show("projects"):
        rows.append([("🏢 شرکت‌ها و پروژه‌ها", "a|grp|projects")])
    if show("un"):
        rows.append([("🗳 سازمان ملل، جنگ و نجات", "a|grp|un")])
    if show("trade"):
        rows.append([("🤝 تجارت و پیمان‌ها", "a|grp|trade")])
    if show("missions"):
        rows.append([("🎯 ماموریت‌ها", "a|grp|missions")])
    if show("tickets"):
        rows.append([("🎫 پشتیبانی", "a|tik|open|0")])
    if show("seasons"):
        rows.append([("🎬 سیزن‌ها و رای‌گیری", "a|season")])
    if show("media"):
        rows.append([("🖼 کتابخانه تصاویر", "a|img")])
    if show("settings"):
        rows.append([("⚙️ تنظیمات و متن‌ها", "a|set")])
        rows.append([("🔘 بخش‌های بازی (روشن/خاموش)", "a|sections")])
    if show("broadcast"):
        rows.append([("📣 پیام همگانی", "a|bc")])
    if show("admins"):
        rows.append([("🛡 ادمین‌ها", "a|adm")])
    if show("logs"):
        rows.append([("📜 لاگ‌ها", "a|log|0")])
    rows.append([("🔥 فایربیس (اتصال سرور)", "a|fb")])
    rows.append([("📋 گزارش ۲۴ ساعت اخیر", "a|daily")])
    rows.append([("🗄 دیتابیس خام (همه جدول‌ها)", "a|db")])
    rows.append([("📊 آمار کلی", "a|stats")])
    return kb(rows)


# ─── منوی گروه موجودیت‌ها ───


@router.callback_query(F.data.startswith("a|grp|"))
async def group_menu(call: CallbackQuery, perms: set):
    perm = call.data.split("|")[2]
    if not has(perms, perm):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    entities = for_perm(perm)
    lines = [f"<b>{PERM_TITLES.get(perm, perm)}</b>\n", "مدیریت چه چیزی؟"]
    rows = [[(f"{e.icon} {e.title}", cd(e.key, "p", 0))] for e in entities]
    rows.append([("◀️ بازگشت", "a|root")])
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))


# ─── دیتابیس خام ───


@router.callback_query(F.data == "a|db")
async def db_browser(call: CallbackQuery):
    tables = await raw_tables()
    counts = {}
    for key, name in tables.items():
        row = await db.fetchone(f"SELECT COUNT(*) AS c FROM {name}")
        counts[key] = (name, row["c"])
    lines = ["🗄 <b>دیتابیس خام — همه جدول‌ها</b>\n",
             "هر جدول را می‌توانید مستقیم مرور، ویرایش و حذف کنید (۱۰۰٪ همه چیز):"]
    rows = []
    items = sorted(counts.items(), key=lambda kv: kv[1][0])
    for key, (name, count) in items:
        lines.append(f"• {name}: {fmt(count)} ردیف")
        rows.append([(f"🗄 {name} ({fmt(count)})", cd(key, "p", 0))])
    # دو ستونه
    pairs = [r[0] for r in rows]
    grid = [pairs[i:i + 2] for i in range(0, len(pairs), 2)]
    grid.append([("◀️ بازگشت", "a|root")])
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(grid))


# ─── آمار ───


async def stats_text() -> str:
    async def count(sql, params=()):
        return (await db.fetchone(sql, params))["c"]
    users_total = await count("SELECT COUNT(*) c FROM users")
    users_active = await count("SELECT COUNT(*) c FROM users WHERE country_id IS NOT NULL")
    banned = await count("SELECT COUNT(*) c FROM users WHERE banned=1")
    pending = await count("SELECT COUNT(*) c FROM receipts WHERE status='pending'")
    coins = (await db.fetchone("SELECT COALESCE(SUM(royal_coins),0) c FROM users"))["c"]
    money = (await db.fetchone("SELECT COALESCE(SUM(money),0) c FROM users"))["c"]
    free_countries = await count("SELECT COUNT(*) c FROM countries WHERE owner_id IS NULL AND is_active=1")
    special = await count("SELECT COUNT(*) c FROM countries WHERE is_special=1")
    open_tickets = await count("SELECT COUNT(*) c FROM tickets WHERE status='open'")
    wars_active = await count("SELECT COUNT(*) c FROM wars WHERE status IN ('voting','active')")
    votes_open = await count("SELECT COUNT(*) c FROM un_votes WHERE status='open'")
    companies = await count("SELECT COUNT(*) c FROM companies")
    admins_count = await count("SELECT COUNT(*) c FROM admins")
    return (
        "📊 <b>آمار کلی بازی</b>\n\n"
        f"👥 بازیکنان: <b>{fmt(users_total)}</b> (دارای کشور: {fmt(users_active)} | اخراجی: {fmt(banned)})\n"
        f"🪙 سکه شاهی در گردش: <b>{fmt(coins)}</b>\n"
        f"💰 مجموع خزانه‌ها: <b>{fmt(money)}</b>\n"
        f"🏳 کشورهای آزاد: <b>{fmt(free_countries)}</b> | ویژه: {fmt(special)}\n"
        f"🧾 فیش‌های در انتظار: <b>{fmt(pending)}</b>\n"
        f"🎫 تیکت‌های باز: <b>{fmt(open_tickets)}</b>\n"
        f"⚔️ جنگ‌های فعال: <b>{fmt(wars_active)}</b> | 🗳 رای‌گیری‌های باز: <b>{fmt(votes_open)}</b>\n"
        f"🏢 شرکت‌ها: <b>{fmt(companies)}</b>\n"
        f"🛡 ادمین‌ها: <b>{fmt(admins_count)}</b>")


@router.callback_query(F.data == "a|stats")
async def stats_menu(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(await stats_text(), reply_markup=kb([
        [("🔄 بروزرسانی", "a|stats")],
        [("◀️ بازگشت", "a|root")],
    ]))


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer(await stats_text())


# ─── گزارش روزانه / فایربیس ───


@router.callback_query(F.data == "a|daily")
async def daily_report_menu(call: CallbackQuery):
    from core.scheduler import build_daily_report
    from core.utils import split_text
    text = await build_daily_report()
    parts = split_text(text)
    await call.answer("📋 در حال ساخت گزارش...")
    for p in parts[:3]:
        await call.message.answer(p)
    await call.message.answer("📋 پایان گزارش", reply_markup=kb([[("🔄 بروزرسانی", "a|daily"), ("◀️ بازگشت", "a|root")]]))


@router.message(Command("daily"))
async def cmd_daily(message: Message):
    from core.scheduler import build_daily_report
    from core.utils import split_text
    for p in split_text(await build_daily_report()):
        await message.answer(p)


@router.callback_query(F.data == "a|fb")
async def firebase_panel(call: CallbackQuery):
    from core.firebase import fb
    await fb.test()
    s = fb.status_dict()
    connected = "🟢 متصل" if s["connected"] else ("🟡 حالت محلی" if s["mode"] != "فایربیس واقعی" else "🔴 قطع")
    text = (
        "🔥 <b>اتصال سرور (فایربیس)</b>\n\n"
        f"وضعیت: <b>{connected}</b>\n"
        f"حالت: {s['mode']}\n"
        f"آدرس: <code>{s['url']}</code>\n"
        f"تأخیر: {s['latency_ms']}ms\n"
        f"آخرین همگام‌سازی: {s['last_sync']}\n"
        + (f"خطا: <code>{s['last_error']}</code>\n" if s["last_error"] else "")
        + "\n💡 برای اتصال واقعی، در فایل .env این دو مقدار را پر کنید:\n"
        "<code>FIREBASE_DB_URL=https://YOUR-PROJECT.firebaseio.com</code>\n"
        "<code>FIREBASE_AUTH=secret-or-token</code>")
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb([
        [("🔄 تست اتصال", "a|fb")],
        [("📤 ارسال اسنپ‌شات کامل", "a|fbsnap")],
        [("◀️ بازگشت", "a|root")],
    ]))


@router.callback_query(F.data == "a|fbsnap")
async def firebase_snapshot_push(call: CallbackQuery):
    from core.firebase import fb
    sent = await fb.push_snapshot()
    await call.answer(f"📤 {sent} جدول ارسال شد", show_alert=True)
    await firebase_panel(call)

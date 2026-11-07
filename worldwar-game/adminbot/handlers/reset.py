"""♻️ ریست کشور — ادمین می‌تواند کشور یک بازیکن را کامل آزاد کند.

پس از ریست:
- کشور به حالت اولیه برمی‌گردد (جمعیت، استان‌ها، درآمد نفتی، پرچم مالکیت)
- بازیکن کشورش را از دست می‌دهد و با `/start` می‌تواند **کشور دیگری** انتخاب کند
- دارایی‌های وابسته به کشور (تجهیزات، پروژه، شرکت، استان‌ها) پاک می‌شوند

مسیرها:
    /resetcountry  → راهنما
    a|rcty|<uid>   → ریست کشور یک بازیکن (با تأیید)
    a|rctygo|<uid> → اجرای قطعی
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import kb
from adminbot.tools import log_action
from core.db import db, get_initial_money
from core.utils import fmt, fmt_money

router = Router()


async def _user_brief(uid: int) -> dict | None:
    return await db.fetchone(
        "SELECT u.id, u.full_name, u.money, u.royal_coins, u.banned, "
        "c.id AS cid, c.name AS cname, c.flag AS cflag "
        "FROM users u LEFT JOIN countries c ON c.id=u.country_id WHERE u.id=?",
        (uid,))


async def reset_payload(uid: int) -> tuple[str, object]:
    """متن و دکمه‌های صفحهٔ تأیید ریست کشور."""
    u = await _user_brief(uid)
    if not u:
        return "❌ کاربر یافت نشد.", kb([[("◀️ بازگشت", "a|root")]])
    country_line = (f"{u['cflag'] or ''} <b>{u['cname']}</b>" if u["cname"]
                    else "<i>بدون کشور</i>")
    provinces = await db.fetchone(
        "SELECT COUNT(*) c FROM provinces WHERE owner_id=?", (uid,))
    assets = await db.fetchone(
        "SELECT COUNT(*) c FROM player_assets WHERE user_id=?", (uid,))
    projects = await db.fetchone(
        "SELECT COUNT(*) c FROM player_projects WHERE user_id=?", (uid,))

    async def _cnt(sql: str) -> int:
        try:
            row = await db.fetchone(sql, (uid,))
            return int((row or {}).get("c") or 0)
        except Exception:
            return 0
    enrich_stage = await _cnt("SELECT COALESCE(MAX(stage),0) c FROM enrichment WHERE user_id=?")
    nuke = await _cnt("SELECT COUNT(*) c FROM nuclear_sites WHERE user_id=? AND active=1")
    oil_lv = await _cnt("SELECT COALESCE(MAX(level),0) c FROM oil_business WHERE user_id=?")
    net_lv = await _cnt("SELECT COALESCE(MAX(level),0) c FROM internet_infra WHERE user_id=?")
    wear = await _cnt("SELECT CAST(COALESCE(AVG(wear),0) AS INT) c FROM country_attrition WHERE user_id=?")

    text = (
        "♻️ <b>ریست کامل کشور</b>\n\n"
        f"👤 بازیکن: <b>{u['full_name'] or uid}</b> (<code>{uid}</code>)\n"
        f"🏳 کشور فعلی: {country_line}\n"
        f"💰 خزانه: {fmt_money(u['money'] or 0)} | 🪙 سکه: {fmt(u['royal_coins'] or 0)}\n"
        f"🗺 استان‌ها: {fmt((provinces or {}).get('c') or 0)}\n"
        f"🎖 تجهیزات: {fmt((assets or {}).get('c') or 0)} | "
        f"🏗 پروژه‌ها: {fmt((projects or {}).get('c') or 0)}\n"
        f"☢️ مرحلهٔ غنی‌سازی: {fmt(enrich_stage)} | "
        f"تأسیسات فعال: {fmt(nuke)} | ⛓ فرسایش: {fmt(wear)}٪\n"
        f"🛢 سطح تجهیزات استخراج: {fmt(oil_lv)} | 🌐 سطح اینترنت: {fmt(net_lv)}\n\n"
        "⚠️ <b>با تأیید، این موارد انجام می‌شود:</b>\n"
        "• کشور فعلی کاملاً آزاد و به حالت اولیه برمی‌گردد (۵ استان پایه، بدون مالک)\n"
        "• بازیکن همهٔ استان‌ها، تجهیزات، پروژه‌ها و شرکت‌ها را از دست می‌دهد\n"
        "• ☢️ تأسیسات هسته‌ای، 🧬 غنی‌سازی، 🛢 ارتقای نفت، 🌐 اینترنت و ⛓ فرسایش پاک می‌شود\n"
        "• سکه شاهی صفر و خزانه به بودجهٔ اولیه برمی‌گردد\n"
        "• بازیکن با <b>/start</b> می‌تواند کشور دیگری انتخاب کند\n\n"
        "آیا مطمئن هستید؟"
    )
    rows = [
        [("✅ بله، کشور را ریست کن", f"a|rctygo|{uid}")],
        [("🏳 بعد از ریست، کشور تازه انتخاب کن", f"a|rctypick|{uid}|0")],
        [("◀️ انصراف", "a|root")],
    ]
    return text, kb(rows)


PICK_PAGE = 10


async def pick_payload(uid: int, page: int) -> tuple[str, object]:
    """لیست کشورهای آزاد برای انتخاب مستقیم توسط ادمین."""
    u = await db.fetchone("SELECT id, full_name, country_id FROM users WHERE id=?", (uid,))
    if not u:
        return "❌ کاربر یافت نشد.", kb([[("◀️ بازگشت", "a|root")]])
    total = (await db.fetchone(
        "SELECT COUNT(*) c FROM countries WHERE is_active=1 AND owner_id IS NULL AND NOT EXISTS (SELECT 1 FROM users u WHERE u.country_id=countries.id)"))["c"]
    rows_db = await db.fetchall(
        "SELECT * FROM countries WHERE is_active=1 AND owner_id IS NULL AND NOT EXISTS (SELECT 1 FROM users u WHERE u.country_id=countries.id) "
        "ORDER BY population DESC LIMIT ? OFFSET ?", (PICK_PAGE, page * PICK_PAGE))
    pages = max(1, (total + PICK_PAGE - 1) // PICK_PAGE)
    lines = [
        f"🏳 <b>انتخاب کشور تازه برای {u['full_name'] or uid}</b>",
        f"<code>{uid}</code> — صفحه {page + 1} از {pages}",
        f"کشورهای آزاد: <b>{fmt(total)}</b>\n",
    ]
    buttons = []
    for r in rows_db:
        sea = "🌊" if r["has_sea"] else "🚫"
        lines.append(f"{r['flag']} {r['name']} — 👥 {fmt(r['population'])} {sea}")
        buttons.append([(f"{r['flag']} {r['name']}", f"a|rctyset|{uid}|{r['id']}")])
    if not rows_db:
        lines.append("— هیچ کشور آزادی نمانده —")
    nav = []
    if page > 0:
        nav.append(("‹ قبلی", f"a|rctypick|{uid}|{page - 1}"))
    if (page + 1) * PICK_PAGE < total:
        nav.append(("بعدی ›", f"a|rctypick|{uid}|{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([("◀️ بازگشت به کارت ریست", f"a|rcty|{uid}")])
    return "\n".join(lines), kb(buttons)


@router.message(Command("resetcountry"))
async def cmd_reset_country(message: Message, perms: set):
    """/resetcountry — راهنما · /resetcountry <uid> — صفحهٔ تأیید ریست."""
    if not has(perms, "users"):
        return await message.answer("⛔️ دسترسی ندارید")
    parts = (message.text or "").split()
    if len(parts) >= 2 and parts[1].isdigit():
        text, markup = await reset_payload(int(parts[1]))
        return await message.answer(text, reply_markup=markup)
    await message.answer(
        "♻️ <b>ریست کشور بازیکن</b>\n\n"
        "برای ریست، آیدی عددی بازیکن را بعد از دستور بنویسید:\n"
        "<code>/resetcountry 8666501866</code>\n\n"
        "یا از پنل: 👥 کاربران → جستجوی کاربر → «♻️ ریست کشور»")


@router.callback_query(F.data.startswith("a|rcty|"))
async def reset_country_prompt(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    text, markup = await reset_payload(uid)
    await call.answer()
    await call.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("a|rctypick|"))
async def reset_country_pick(call: CallbackQuery, perms: set):
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    _, _, uid, page = call.data.split("|")
    text, markup = await pick_payload(int(uid), int(page))
    await call.answer()
    await call.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("a|rctyset|"))
async def reset_country_assign(call: CallbackQuery, perms: set):
    """کشور آزاد را مستقیماً به بازیکن بده (پس از ریست یا هر زمان دیگر)."""
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    _, _, uid_s, cid_s = call.data.split("|")
    uid, cid = int(uid_s), int(cid_s)
    c = await db.fetchone("SELECT * FROM countries WHERE id=? AND is_active=1", (cid,))
    if not c:
        return await call.answer("کشور یافت نشد", show_alert=True)
    holder = await db.fetchone(
        "SELECT id FROM users WHERE country_id=? AND id!=?", (cid, uid))
    if holder or (c["owner_id"] and c["owner_id"] != uid):
        return await call.answer("❌ این کشور همین حالا مالک دارد", show_alert=True)

    # کشور قبلی بازیکن آزاد شود
    prev = await db.fetchone("SELECT country_id FROM users WHERE id=?", (uid,))
    if prev and prev["country_id"] and prev["country_id"] != cid:
        old = prev["country_id"]
        await db.execute("UPDATE countries SET owner_id=NULL, collapsed=0 "
                         "WHERE id=? AND owner_id=?", (old, uid))
        await db.execute("DELETE FROM provinces WHERE country_id=? AND owner_id=?", (old, uid))

    # استان‌های باقی‌مانده از صاحب قبلی آزاد می‌شوند
    await db.execute("UPDATE provinces SET owner_id=NULL, captured_at=NULL WHERE country_id=?", (cid,))
    await db.execute("UPDATE countries SET owner_id=?, collapsed=0 WHERE id=?", (uid, cid))
    await db.execute("UPDATE users SET country_id=?, country_taken_at=datetime('now') WHERE id=?",
                     (cid, uid))
    # 🗺 استان‌های پایهٔ کشور به بازیکن برسد (همهٔ استان‌ها به مالک جدید)
    try:
        from core.provinces import ensure_country_provinces
        await ensure_country_provinces(cid, uid, normalize=True)
    except Exception:
        pass
    try:
        from core.economy import get_state as _gs
        await _gs(uid)
    except Exception:
        pass

    await log_action(call.from_user.id, "کاربر", f"دادن کشور {c['name']} به {uid}")
    try:
        from gamebot.common import kb as gkb
        await call.bot.send_message(
            uid,
            f"🏳 <b>کشور تازه شما تعیین شد</b>\n\n"
            f"شما اکنون رهبر {c['flag']} <b>{c['name']}</b> هستید.\n"
            "از /start وارد بازی شوید — ۵ استان و بودجهٔ اولیه در اختیار شماست.",
            reply_markup=gkb([]))
    except Exception:
        pass

    await call.answer(f"✅ {c['name']} به بازیکن داده شد", show_alert=True)
    text, markup = await reset_payload(uid)
    await call.message.edit_text(
        f"✅ <b>کشور تازه تعیین شد</b>\n\n"
        f"👤 بازیکن <code>{uid}</code> ← {c['flag']} <b>{c['name']}</b>\n\n" + text,
        reply_markup=markup)


@router.callback_query(F.data.startswith("a|rctygo|"))
async def reset_country_execute(call: CallbackQuery, perms: set):
    """اجرای ریست: آزادسازی کشور + پاک‌سازی دارایی‌ها + اطلاع به بازیکن."""
    if not has(perms, "users"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    uid = int(call.data.split("|")[2])
    u = await _user_brief(uid)
    if not u:
        return await call.answer("کاربر یافت نشد", show_alert=True)

    cid = u["cid"]
    cname = u["cname"] or "—"

    # ۱) آزادسازی کشور و بازگرداندنش به حالت اولیه
    if cid:
        await db.execute(
            "UPDATE countries SET owner_id=NULL, collapsed=0, province_count=5 WHERE id=?",
            (cid,))
        # استان‌های کشور: مالکیت پاک، ساختار حفظ (۵ استان پایه)
        await db.execute(
            "UPDATE provinces SET owner_id=NULL, captured_at=NULL WHERE country_id=?", (cid,))

    # ۲) آزادسازی استان‌هایی که بازیکن از کشورهای دیگر گرفته بود
    await db.execute("UPDATE provinces SET owner_id=NULL WHERE owner_id=?", (uid,))

    # ۳) پاک‌سازی دارایی‌های وابسته
    for sql in (
        "DELETE FROM player_assets WHERE user_id=?",
        "DELETE FROM player_projects WHERE user_id=?",
        "DELETE FROM soldier_trainings WHERE user_id=?",
        "DELETE FROM companies WHERE owner_id=?",
        "DELETE FROM bases WHERE guest_id=? OR host_id=?",
        "DELETE FROM oil_business WHERE user_id=?",
        "DELETE FROM enrichment WHERE user_id=?",
        "DELETE FROM alliance_members WHERE user_id=?",
        "DELETE FROM country_attrition WHERE user_id=?",
        "DELETE FROM nuclear_sites WHERE user_id=?",
        "DELETE FROM internet_infra WHERE user_id=?",
    ):
        try:
            await db.execute(sql, (uid, uid) if sql.count("?") == 2 else (uid,))
        except Exception:
            pass
    # ۳) پاک‌سازی کامل دارایی‌های وابسته با موتور مشترک core.fullreset
    #    (تجهیزات، سرباز، پروژه، شرکت، پایگاه، ☢️ هسته‌ای، 🛢 ارتقا، 🌐 اینترنت،
    #     ⛓ فرسایش، 🗺 استان‌های تصاحب‌شده، پیمان‌ها، اتحاد، جنگ‌ها…)
    from core.fullreset import reset_player_progress
    await reset_player_progress(uid)

    # ۴) ریست بازیکن
    await db.execute(
        "UPDATE users SET country_id=NULL, country_taken_at=NULL, royal_coins=0, "
        "money=? WHERE id=?",
        (await get_initial_money(), uid))
    # وضعیت داخلی کشور به حالت پایه برمی‌گردد (states در ریست بالا پاک شده،
    # پس ردیف تازه با مقادیر پیش‌فرض ساخته می‌شود)
    try:
        from core.economy import get_state
        await get_state(uid)
    except Exception:
        pass
    # 🗺 استان‌های کشور آزاد می‌شوند تا مالک بعدی «سقوط‌کرده» نبیند
    if cid:
        try:
            await db.execute(
                "UPDATE countries SET collapsed=0, province_count=5 WHERE id=?", (cid,))
        except Exception:
            pass

    # ۵) اطلاع به بازیکن
    try:
        from gamebot.common import kb as gkb
        await call.bot.send_message(
            uid,
            "♻️ <b>کشور شما توسط ادمین ریست شد</b>\n\n"
            f"🏳 کشور قبلی: <b>{cname}</b>\n"
            "می‌توانید با /start کشور تازه‌ای انتخاب کنید.\n"
            "💰 بودجهٔ اولیه و وضعیت پایه برای شما تنظیم شد.",
            reply_markup=gkb([]))
    except Exception:
        pass

    await call.answer("✅ کشور ریست شد", show_alert=True)
    await log_action(call.from_user.id, "کاربر",
                     f"ریست کامل کشور و پیشرفت بازیکن {uid} (کشور قبلی: {cname})")
    text, markup = await reset_payload(uid)
    await call.message.edit_text(
        f"✅ <b>ریست کامل انجام شد</b>\n\n"
        f"👤 بازیکن <code>{uid}</code> از کشور <b>{cname}</b> آزاد شد.\n"
        "🧹 همهٔ پیشرفت‌ها پاک شد: 🎖 تجهیزات • 🏗 پروژه‌ها • 🏢 شرکت‌ها • "
        "☢️ هسته‌ای • 🛢 ارتقای نفت • 🌐 اینترنت • 🗺 استان‌ها • ⛓ فرسایش • 📜 پیمان‌ها\n"
        "🏳 کشور قبلی با ۵ استان پایه آزاد شد و «سقوط‌کرده» علامت نمی‌خورد.\n\n"
        "اکنون می‌تواند با /start کشور تازه بگیرد.\n\n" + text,
        reply_markup=markup)

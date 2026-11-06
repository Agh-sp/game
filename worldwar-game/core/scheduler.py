"""زمان‌بند پس‌زمینه — درآمد خودکار هر ۳۰ دقیقه، ارز، سازمان نجات، سیزن، فایربیس و گزارش روزانه.

- start_game_scheduler(bot): فقط در ربات اصلی (gamebot) اجرا می‌شود.
- start_admin_scheduler(bot): فقط در ربات ادمین (گزارش روزانه) اجرا می‌شود.
"""
import asyncio
import logging

from core.currency import main_currency_recompute
from core.db import db, get_setting, set_setting
from core.economy import (consumption, get_country, income_amount, income_breakdown,
                          satisfaction_recompute, sector_capacity, get_state)
from core.events import log_event
from core.firebase import fb
from core.images import announce_img
from core.rescue import close_campaign, campaign_list
from core.straits import toll_payers_slice
from core.utils import fmt, fmt_money, iso, now, TEHRAN_OFFSET
from core import seed as seed_mod

log = logging.getLogger("scheduler")
_tasks: list[asyncio.Task] = []


# ─── تیک درآمد (هر ۳۰ دقیقه) ───


async def income_tick(bot) -> None:
    """پرداخت خودکار مالیات/درآمد هر کشور + کسر یارانه + عوارض تنگه + استخراج نفت + اعلان به بازیکن."""
    if await get_setting("bot_off", "0") == "1":
        return
    minutes = max(5, int(float(await get_setting("income_interval_minutes", "30"))))
    share = minutes / (24 * 60)
    users = await db.fetchall(
        "SELECT u.id, u.money, s.satisfaction, s.tax_rate, s.subsidy_daily FROM users u "
        "JOIN states s ON s.user_id=u.id WHERE u.country_id IS NOT NULL AND u.banned=0")
    total_paid = 0
    for u in users:
        uid = u["id"]
        try:
            await satisfaction_recompute(uid)
        except Exception:
            pass
        info = await income_breakdown(uid)
        daily = info["daily"]
        tax = info["tax_rate"]
        non_tax_daily = info["non_tax"]
        income_slice = int(daily * share)
        non_tax_slice = int(non_tax_daily * share)
        subsidy_slice = int((u["subsidy_daily"] or 0) * share)
        # عوارض تنگه‌ها: ۱.۵٪ درآمد غیرمالیاتی به مالک تنگه
        tolls = await toll_payers_slice(uid, non_tax_slice)
        toll_total = sum(amount for _owner, amount in tolls)
        for owner, amount in tolls:
            if amount > 0:
                await db.execute("UPDATE users SET money=money+? WHERE id=?", (amount, owner))

        # جریمه مسدودی تنگه‌ها (کاهش ۱۰٪ درآمد به ازای هر تنگه مسدود شده علیه این کشور)
        blockade_row = await db.fetchone(
            "SELECT COUNT(*) AS c FROM strait_blockades WHERE target_user_id=?", (uid,))
        blockade_count = blockade_row["c"] if blockade_row else 0
        blockade_loss = 0
        if blockade_count > 0:
            blockade_pct = min(0.9, blockade_count * 0.10)
            blockade_loss = int(income_slice * blockade_pct)
            income_slice -= blockade_loss

        # استخراج نفت خودکار
        from core import oil as oil_mod
        try:
            extracted = await oil_mod.extraction_tick(uid)
        except Exception:
            extracted = 0
        # مازاد منابع → انبار
        res_txt = []
        country = await get_country(uid)
        if country:
            state = await get_state(uid)
            for sector, col in (("power", "energy"), ("water", "water"), ("gas", "gas")):
                cap = await sector_capacity(uid, sector)
                cons = consumption(country["population"] or 1, state.get(f"blackout_{sector}") or 0)
                surplus = max(0, cap - cons)
                if surplus > 0:
                    await db.execute(f"UPDATE states SET {col}={col}+? WHERE user_id=?", (surplus, uid))
                    res_txt.append(sector)
        # بازیابی تدریجی دیپلماسی به سمت ۵۰
        await db.execute(
            "UPDATE states SET diplomacy=CASE WHEN diplomacy<50 THEN MIN(50,diplomacy+0.5) "
            "WHEN diplomacy>50 THEN MAX(50,diplomacy-0.5) ELSE diplomacy END WHERE user_id=?", (uid,))
        net = income_slice - subsidy_slice - toll_total
        if net:
            await db.execute("UPDATE users SET money=money+? WHERE id=?", (net, uid))
        await db.execute("UPDATE states SET last_income=? WHERE user_id=?", (iso(), uid))
        total_paid += max(0, net)
        # اعلان به بازیکن
        c = country or {}
        blockade_txt = (f"🚫 جریمه انسداد تنگه‌ها ({blockade_count} تنگه مسدود): <b>-{fmt_money(blockade_loss)}</b> (۱۰٪ به ازای هر تنگه)\n" if blockade_loss else "")
        msg = (
            f"💰 <b>درآمد دوره‌ای ({minutes} دقیقه)</b>\n\n"
            f"{blockade_txt}"
            f"{c.get('flag', '')} {c.get('name', '')}\n"
            f"👥 جمعیت: <b>{fmt(info['population'])}</b> نفر | 🙂 رضایت: <b>{info['satisfaction']}%</b>"
            f" | 💰 نرخ مالیات: <b>{round(info['tax_rate'] * 100, 1)}%</b>\n"
            f"💵 درآمد مالیات این دوره: <b>{fmt_money(income_slice)}</b>"
            f" (روزانه <b>{fmt_money(daily)}</b>)\n"
        )
        if subsidy_slice:
            msg += f"🎁 کسر یارانه: <b>{fmt_money(subsidy_slice)}</b>\n"
        if toll_total:
            msg += f"⚓ عوارض تنگه‌ها: <b>-{fmt_money(toll_total)}</b>\n"
        if extracted:
            msg += f"🛢 نفت استخراج‌شده: <b>{fmt(extracted)} بشکه</b>\n"
        if res_txt:
            names = {"power": "برق", "water": "آب", "gas": "گاز"}
            msg += "🏭 مازاد به انبار رفت: " + "، ".join(names.get(r, r) for r in res_txt) + "\n"
        msg += f"\n✅ خالص به خزانه: <b>{fmt_money(net)}</b>"
        try:
            from gamebot.common import kb
            await bot.send_message(uid, msg, reply_markup=kb([]))
        except Exception:
            pass
    if total_paid:
        await log_event("income", f"پرداخت خودکار دوره‌ای: مجموع {fmt(total_paid)} پول به {len(users)} کشور")


# ─── رای‌گیری سیزن ───


async def season_votes_task(bot) -> None:
    """پست کردن رای‌گیری‌های بدون پیام کانال + بررسی رسیدن به حد رأی."""
    votes = await db.fetchall("SELECT * FROM season_votes WHERE status='open'")
    for v in votes:
        if v["channel_msg"] is None:
            options = __import__("json").loads(v["options"] or "[]")
            rows = [[(opt, f"g|svote|{v['id']}|{i}")] for i, opt in enumerate(options)]
            from core.images import get_channel_bot_username
            username = await get_channel_bot_username(bot)
            rows.append([("🎮 ورود به ربات", f"https://t.me/{username}")])
            from gamebot.common import kb
            channel = await get_setting("announcement_channel", "")
            if channel:
                try:
                    from core.images import send_with_image
                    m = await send_with_image(
                        bot, channel,
                        "🗳 <b>رای‌گیری سیزن جدید!</b>\n\nکدام مود سیزن بعدی باشد؟ "
                        f"(نخستین گزینه به <b>{v['required_votes']}</b> رأی برسد همان اجرا می‌شود)",
                        "season", reply_markup=kb(rows, home=False))
                    await db.execute("UPDATE season_votes SET channel_msg=? WHERE id=?",
                                     (getattr(m, "message_id", 0), v["id"]))
                except Exception:
                    pass
        # بررسی حد رأی / پایان زمان
        ballots = await db.fetchall("SELECT choice FROM season_ballots WHERE vote_id=?", (v["id"],))
        tally: dict[int, int] = {}
        for b in ballots:
            tally[b["choice"]] = tally.get(b["choice"], 0) + 1
        options = __import__("json").loads(v["options"] or "[]")
        winner = None
        for idx, cnt in tally.items():
            if cnt >= (v["required_votes"] or 10) and 0 <= idx < len(options):
                winner = idx
                break
        if winner is None and v["ends_at"] and v["ends_at"] <= iso():
            if tally:
                top = max(tally.values())
                leaders = [k for k, x in tally.items() if x == top]
                if len(leaders) == 1 and 0 <= leaders[0] < len(options):
                    winner = leaders[0]
        if winner is not None:
            label = options[winner]
            mode = {"🌍 جنگ جهانی": "worldwar", "✝️ جنگ‌های صلیبی": "crusades",
                    "🏛 جنگ‌های باستان": "ancient"}.get(label, "worldwar")
            await db.execute("UPDATE season_votes SET status='closed', winner=? WHERE id=?",
                             (label, v["id"]))
            await set_setting("season_name", label)
            await set_setting("season_mode", mode)
            await db.execute("UPDATE seasons SET is_active=0")
            await db.execute("INSERT INTO seasons(name, mode, is_active) VALUES(?,?,1)",
                             (label, mode))
            await log_event("season", f"سیزن جدید انتخاب شد: {label}")
            try:
                await announce_img(bot, f"🎬 سیزن جدید بازی شروع شد: <b>{label}</b>", "season")
            except Exception:
                pass
        elif v["ends_at"] and v["ends_at"] <= iso():
            await db.execute("UPDATE season_votes SET status='cancelled' WHERE id=?", (v["id"],))


# ─── سازمان نجات ───


async def rescue_task(bot) -> None:
    for c in await campaign_list():
        if c["ends_at"] and c["ends_at"] <= iso():
            try:
                await close_campaign(bot, c)
            except Exception:
                log.exception("rescue close failed")


# ─── فایربیس ───


async def firebase_heartbeat_task() -> None:
    while True:
        try:
            await fb.heartbeat()
        except Exception:
            pass
        await asyncio.sleep(60)


async def firebase_flush_task() -> None:
    while True:
        try:
            await fb.flush_queue()
        except Exception:
            pass
        await asyncio.sleep(2)


async def firebase_snapshot_task() -> None:
    while True:
        await asyncio.sleep(300)
        try:
            await fb.push_snapshot()
        except Exception:
            pass


# ─── گزارش روزانه ادمین ───


async def build_daily_report() -> str:
    since = iso(now() - __import__("datetime").timedelta(hours=24))
    evs = await db.fetchall(
        "SELECT kind, text FROM game_events WHERE created_at>=? ORDER BY id DESC LIMIT 200", (since,))
    grouped: dict[str, list[str]] = {}
    for e in evs:
        grouped.setdefault(e["kind"], []).append(e["text"])
    KINDS = {"war": "⚔️ جنگ", "treaty": "📜 پیمان‌ها", "trade": "🔁 تجارت مستقیم",
             "oil": "🛢 نفت", "strait": "⚓ تنگه‌ها", "currency": "💵 ارز",
             "rescue": "🏥 سازمان نجات", "income": "💰 درآمد", "season": "🎬 سیزن",
             "negotiation": "🕊 مذاکره", "user": "👥 بازیکنان"}
    async def count(sql):
        return (await db.fetchone(sql))["c"]
    lines = ["📋 <b>گزارش ۲۴ ساعت اخیر بازی</b>\n"]
    new_users = await count(f"SELECT COUNT(*) c FROM users WHERE joined_at>='{since}'")
    lines.append(f"👥 بازیکنان جدید: <b>{new_users}</b>")
    active_users = await count("SELECT COUNT(*) c FROM users WHERE country_id IS NOT NULL AND banned=0")
    lines.append(f"🌍 کشورهای فعال: <b>{active_users}</b>")
    wars_active = await count("SELECT COUNT(*) c FROM wars WHERE status IN ('voting','active')")
    lines.append(f"⚔️ جنگ‌های فعال: <b>{wars_active}</b>")
    trades = await count(f"SELECT COUNT(*) c FROM direct_trades WHERE created_at>='{since}'")
    vol = (await db.fetchone(
        f"SELECT COALESCE(SUM(value_estimate),0) c FROM direct_trades WHERE created_at>='{since}'"))["c"]
    lines.append(f"🔁 تجارت‌های مستقیم: <b>{trades}</b> (ارزش: {fmt(vol)})")
    oil = await count(f"SELECT COUNT(*) c FROM oil_offers WHERE created_at>='{since}'")
    lines.append(f"🛢 عرضه‌های نفت: <b>{oil}</b>")
    pending_rcp = await count("SELECT COUNT(*) c FROM receipts WHERE status='pending'")
    lines.append(f"🧾 فیش‌های در انتظار: <b>{pending_rcp}</b>")
    open_tik = await count("SELECT COUNT(*) c FROM tickets WHERE status='open'")
    lines.append(f"🎫 تیکت‌های باز: <b>{open_tik}</b>")
    main_cur = await get_setting("main_currency", "—")
    lines.append(f"💵 ارز اصلی: <b>{main_cur}</b>")
    lines.append(f"🎬 سیزن: <b>{await get_setting('season_name', '—')}</b>")
    for kind, title in KINDS.items():
        items = grouped.get(kind, [])
        if items:
            lines.append(f"\n<b>{title}</b> ({len(items)}):")
            lines.extend(f"• {t[:120]}" for t in items[:8])
            if len(items) > 8:
                lines.append(f"… و {len(items) - 8} مورد دیگر")
    if not evs:
        lines.append("\n<i>— رویداد خاصی ثبت نشده —</i>")
    return "\n".join(lines)


async def daily_report_task(bot) -> None:
    """ارسال گزارش روزانه به همه ادمین‌ها در ساعت تنظیم‌شده (تهران)."""
    while True:
        try:
            tehran_now = now() + TEHRAN_OFFSET
            hour = int(await get_setting("daily_report_hour", "9"))
            last_day = await get_setting("last_report_day", "")
            today = tehran_now.strftime("%Y-%m-%d")
            if tehran_now.hour == hour and last_day != today:
                text = await build_daily_report()
                admins = await db.fetchall("SELECT id FROM admins")
                for a in admins:
                    try:
                        from core.utils import split_text
                        for part in split_text(text):
                            await bot.send_message(a["id"], part)
                    except Exception:
                        pass
                await set_setting("last_report_day", today)
        except Exception:
            log.exception("daily report failed")
        await asyncio.sleep(300)


# ─── چرخه اصلی ───


async def _income_loop(bot) -> None:
    while True:
        minutes = max(5, int(float(await get_setting("income_interval_minutes", "30"))))
        try:
            await income_tick(bot)
        except Exception:
            log.exception("income tick failed")
        await asyncio.sleep(minutes * 60)


async def _slow_loop(bot) -> None:
    """کارهای دقیقه‌ای: سیزن، نجات، ارز و بستن رای‌گیری‌های سازمان ملل."""
    while True:
        try:
            # بستن خودکار رای‌گیری‌های تمام‌شده (مجوز جنگ ۳۰ دقیقه‌ای و ...)
            from gamebot.handlers.war import settle_votes
            await settle_votes(bot)
        except Exception:
            log.exception("settle votes failed")
        try:
            await season_votes_task(bot)
        except Exception:
            log.exception("season votes failed")
        try:
            await rescue_task(bot)
        except Exception:
            log.exception("rescue task failed")
        try:
            await main_currency_recompute(bot)
        except Exception:
            log.exception("currency recompute failed")
        # فروش خودکار نفت (هر ۱۰ دقیقه) — درآمد میلیونی به خزانه
        try:
            from core import oil as oil_mod
            paid = await oil_mod.auto_sell_tick(bot)
            if paid:
                log.info("🛢 درآمد نفت پرداخت شد: %s", paid)
        except Exception:
            log.exception("oil auto sell failed")
        # بستن انقلاب‌هایی که مهلتشان تمام شده
        try:
            from core.politics import revolution_tick
            closed = await revolution_tick(bot)
            if closed:
                log.info("🔥 %s انقلاب به پایان رسید", closed)
        except Exception:
            log.exception("revolution tick failed")
        await asyncio.sleep(60)


async def _world_news_loop(bot) -> None:
    """هر ۳ ساعت یک خبر «وضعیت جهان» در کانال می‌گذارد."""
    await asyncio.sleep(120)
    while True:
        await world_news_task(bot)
        await asyncio.sleep(3 * 60 * 60)


async def world_news_task(bot) -> None:
    """خبر دوره‌ای «وضعیت جهان» در کانال: قدرت‌ها، جنگ‌های فعال و کشورهای آزاد."""
    try:
        from core.economy import announce_news
        wars = await db.fetchall("SELECT COUNT(*) c FROM wars WHERE status IN ('active','voting')")
        active = int((wars[0]["c"] if wars else 0) or 0)
        free = await db.fetchall(
            "SELECT COUNT(*) c FROM countries WHERE (owner_id IS NULL OR owner_id=0) AND is_active=1")
        free_count = int((free[0]["c"] if free else 0) or 0)
        total = await db.fetchall("SELECT COUNT(*) c FROM users WHERE country_id IS NOT NULL AND banned=0")
        players = int((total[0]["c"] if total else 0) or 0)
        top = await db.fetchall(
            "SELECT c.flag, c.name, COUNT(DISTINCT u.id) n FROM countries c "
            "JOIN users u ON u.country_id=c.id AND u.banned=0 "
            "GROUP BY c.id ORDER BY n DESC LIMIT 3")
        lines = [f"👥 بازیکنان فعال: <b>{players}</b>",
                 f"⚔️ جنگ‌های جاری: <b>{active}</b>",
                 f"🏳 کشورهای آزاد: <b>{free_count}</b>"]
        if top:
            lines.append("🏆 قدرت‌های برتر: " + " • ".join(
                f"{r['flag']} {r['name']}" for r in top))
        await announce_news(bot, "📰 وضعیت امروز جهان", lines, section="general")
    except Exception:
        log.exception("world news failed")


def start_game_scheduler(bot) -> list[asyncio.Task]:
    """راه‌اندازی زمان‌بند ربات اصلی (یک‌بار)."""
    global _tasks
    if _tasks:
        return _tasks
    async def _on_start():
        await fb.start()
    _tasks = [
        asyncio.create_task(_on_start()),
        asyncio.create_task(_income_loop(bot)),
        asyncio.create_task(_slow_loop(bot)),
        asyncio.create_task(_world_news_loop(bot)),
        asyncio.create_task(firebase_heartbeat_task()),
        asyncio.create_task(firebase_flush_task()),
        asyncio.create_task(firebase_snapshot_task()),
    ]
    log.info("⏰ زمان‌بند بازی راه‌اندازی شد (درآمد ۳۰ دقیقه‌ای، ارز، نجات، سیزن، فایربیس)")
    return _tasks


def start_admin_scheduler(bot) -> list[asyncio.Task]:
    """زمان‌بند ربات ادمین (گزارش روزانه)."""
    return [asyncio.create_task(daily_report_task(bot))]

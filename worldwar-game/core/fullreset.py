"""🧨 ریست کامل بازی — یک مرجع واحد برای پاک‌سازی تمام داده‌های بازیکنان.

چرا این ماژول؟ پیش‌تر «ریست همه بازیکنان» در سه جای مختلف (ربات ادمین، پنل وب و
اسکریپت قدیمی `db_bridge`) جداگانه نوشته شده بود و هر کدام بخشی از داده‌ها را
جا می‌گذاشت؛ نتیجه‌اش این بود که پس از ریست، ☢️ تأسیسات هسته‌ای، 🛢 سطح تجهیزات
استخراج، 🌐 اینترنت، 🗺 مالکیت استان‌ها و ⛓ فرسایش همان بازیکن باقی می‌ماند و
کشور تازه‌اش «سقوط‌کرده» نشان داده می‌شد.

این ماژول دو کار انجام می‌دهد:

1. `reset_player_progress(user_id)` — پاک‌سازی کامل پیشرفت **یک** بازیکن
   (تجهیزات، پروژه‌ها، شرکت‌ها، آموزش سرباز، تسلیحات، هسته‌ای، ارتقاها، فرسایش،
   استان‌های تصاحب‌شده، جنگ‌ها، پیمان‌ها، اتحاد، انقلاب، احکام…). پول و سکه
   دست نمی‌خورد مگر با فلگ `reset_wealth=True`.
2. `full_reset()` — ریست کامل کل بازی: همان پاک‌سازی برای همه + آزادسازی همهٔ
   کشورها + بازگرداندن ۵ استان پایه + صفرکردن سکه/بودجه. حساب‌های تلگرام،
   ادمین‌ها، تنظیمات، فیش‌های مالی و لاگ‌ها **باقی می‌مانند**.

هر سه مصرف‌کننده (ربات ادمین، پنل داخل ربات بازی و پنل وب) از همین فهرست‌ها
استفاده می‌کنند تا دیگر هیچ‌وقت داده‌ای جا نماند.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# ─── جدول‌هایی که در ریست کامل، تمام ردیف‌هایشان پاک می‌شود ───
# ترتیب: فرزند قبل از والد (برای دیتابیس‌هایی که کلید خارجی دارند)
CLEAR_TABLES: tuple[str, ...] = (
    "player_assets",
    "player_projects",
    "soldier_trainings",
    "companies",
    "bases",
    "enrichment",
    "nuclear_strikes",
    "nuclear_sites",
    "nuclear_bombs",
    "nuclear_arsenal",
    "country_attrition",
    "sabotage_ops",
    "internet_infra",
    "oil_business",
    "oil_offers",
    "ceasefire_offers",
    "arms_deals",
    "battles",
    "wars",
    "cyber_ops",
    "trades",
    "direct_trades",
    "statements",
    "un_ballots",
    "un_votes",
    "alliance_members",
    "alliance_invites",
    "alliances",
    "negotiation_msgs",
    "negotiation_members",
    "negotiations",
    "treaty_confirms",
    "treaties",
    "provinces_history",
    "provinces",
    "revolutions",
    "rescue_donations",
    "rescue_campaigns",
    "currency_requests",
    "strait_blockades",
    "season_ballots",
    "season_votes",
    "mission_claims",
    "daily_progress",
    # 🧨 موتور واقع‌گرایی (نسخهٔ ۹)
    "supply_stock",
    "strikes",
    "debts",
    "refugee_flows",
    "intel_levels",
    "intel_reports",
    "party_state",
    "season_weather",
    "market_history",
    "states",
)

# ─── ستون‌های مالکیت هر جدول برای پاک‌سازی یک بازیکن ───
USER_COLUMNS: dict[str, tuple[str, ...]] = {
    "player_assets": ("user_id",),
    "player_projects": ("user_id",),
    "soldier_trainings": ("user_id",),
    "companies": ("owner_id",),
    "bases": ("host_id", "guest_id"),
    "enrichment": ("user_id",),
    "nuclear_sites": ("user_id",),
    "nuclear_arsenal": ("user_id",),
    "nuclear_bombs": ("owner_id",),
    "nuclear_strikes": ("attacker_id", "defender_id"),
    "country_attrition": ("user_id",),
    "sabotage_ops": ("attacker_id", "defender_id"),
    "internet_infra": ("user_id",),
    "oil_business": ("user_id",),
    "oil_offers": ("seller_id", "buyer_id"),
    "ceasefire_offers": ("from_id", "to_id"),
    "arms_deals": ("seller_id", "buyer_id"),
    "battles": ("attacker_id", "defender_id"),
    "wars": ("attacker_id", "defender_id"),
    "cyber_ops": ("attacker_id", "defender_id"),
    "trades": ("seller_id", "buyer_id"),
    "direct_trades": ("from_id", "to_id"),
    "statements": ("user_id",),
    "un_ballots": ("user_id",),
    "alliance_members": ("user_id",),
    "alliance_invites": ("inviter_id", "invitee_id"),
    "alliances": ("leader_id",),
    "negotiation_members": ("user_id",),
    "negotiation_msgs": ("sender_id",),
    "negotiations": ("initiator_id",),
    "treaty_confirms": ("user_id",),
    "treaties": ("party_a", "party_b", "witness_id"),
    "provinces_history": ("from_owner", "to_owner"),
    "revolutions": ("user_id",),
    "rescue_donations": ("user_id",),
    "rescue_campaigns": ("winner_id",),
    "currency_requests": ("user_id",),
    "strait_blockades": ("owner_id", "target_user_id"),
    "season_ballots": ("user_id",),
    "mission_claims": ("user_id",),
    "daily_progress": ("user_id",),
    # 🧨 موتور واقع‌گرایی (نسخهٔ ۹)
    "supply_stock": ("user_id",),
    "strikes": ("user_id",),
    "debts": ("user_id",),
    "refugee_flows": ("from_user", "to_user"),
    "intel_levels": ("user_id",),
    "intel_reports": ("attacker_id", "defender_id"),
    "party_state": ("user_id",),
    "states": ("user_id",),
}

# ─── SQL ثابت (بدون پارامتر) ───
GLOBAL_UPDATE_SQL: tuple[str, ...] = (
    "UPDATE countries SET owner_id=NULL, collapsed=0",
    "UPDATE countries SET province_count=5",
    "UPDATE straits SET owner_id=NULL, captured_at=NULL",
)

PLAYER_UPDATE_SQL: tuple[str, ...] = (
    "UPDATE provinces SET owner_id=NULL, captured_at=NULL WHERE owner_id=?",
    "UPDATE straits SET owner_id=NULL, captured_at=NULL WHERE owner_id=?",
)


def _delete_sql(table: str, columns: tuple[str, ...]) -> str:
    where = " OR ".join(f"{c}=?" for c in columns)
    return f"DELETE FROM {table} WHERE {where}"


USER_DELETE_SQL: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
    (_delete_sql(t, cols), cols) for t, cols in USER_COLUMNS.items()
)


# ─── نسخهٔ async (ربات‌ها) ───

async def reset_player_progress(user_id: int, reset_wealth: bool = False,
                                log_errors: bool = False) -> int:
    """پاک‌سازی کامل پیشرفت یک بازیکن. خروجی: تعداد دستورهای موفق."""
    from core.db import db

    done = 0
    for sql, cols in USER_DELETE_SQL:
        try:
            await db.execute(sql, tuple(user_id for _ in cols))
            done += 1
        except Exception as exc:      # جدول در دیتابیس قدیمی نیست
            if log_errors:
                log.warning("reset_player_progress %s: %s", sql.split()[2], exc)
    for sql in PLAYER_UPDATE_SQL:
        try:
            await db.execute(sql, (user_id,))
            done += 1
        except Exception as exc:
            if log_errors:
                log.warning("reset_player_progress update: %s", exc)
    if reset_wealth:
        try:
            from core.db import get_initial_money
            await db.execute(
                "UPDATE users SET royal_coins=0, money=? WHERE id=?",
                (await get_initial_money(), user_id))
            done += 1
        except Exception as exc:
            if log_errors:
                log.warning("reset_player_progress wealth: %s", exc)
    return done


async def full_reset(reset_wealth: bool = True, keep_bans: bool = True,
                     log_errors: bool = False) -> dict:
    """ریست کامل کل بازی. خروجی: آمار برای گزارش به ادمین."""
    from core.db import db, get_initial_money

    users = (await db.fetchone("SELECT COUNT(*) c FROM users")) or {"c": 0}
    countries = (await db.fetchone("SELECT COUNT(*) c FROM countries")) or {"c": 0}
    assets = (await db.fetchone("SELECT COALESCE(SUM(quantity),0) c FROM player_assets")) or {"c": 0}

    for table in CLEAR_TABLES:
        try:
            await db.execute(f"DELETE FROM {table}")
        except Exception as exc:
            if log_errors:
                log.warning("full_reset clear %s: %s", table, exc)
    for sql in GLOBAL_UPDATE_SQL:
        try:
            await db.execute(sql)
        except Exception as exc:
            if log_errors:
                log.warning("full_reset update: %s", exc)

    money = await get_initial_money()
    if reset_wealth:
        await db.execute(
            "UPDATE users SET country_id=NULL, country_taken_at=NULL, "
            "royal_coins=0, money=?", (money,))
    else:
        await db.execute(
            "UPDATE users SET country_id=NULL, country_taken_at=NULL")
    if not keep_bans:
        await db.execute("UPDATE users SET banned=0")

    # 🗺 ساخت مجدد ۵ استان پایه برای همهٔ کشورها (همه آزاد)
    try:
        from core.provinces import ensure_provinces
        await ensure_provinces()
    except Exception as exc:
        log.warning("full_reset provinces: %s", exc)

    try:
        from core.events import log_event
        await log_event("season", "🧨 ریست کامل بازی انجام شد — همهٔ کشورها آزاد و "
                                 "همهٔ پیشرفت‌ها پاک شد")
    except Exception:
        pass

    return {
        "users": int(users["c"] or 0),
        "countries": int(countries["c"] or 0),
        "assets": int(assets["c"] or 0),
        "tables": len(CLEAR_TABLES),
        "initial_money": money,
    }


# ─── نسخهٔ sync (پنل وب / اسکریپت‌ها) ───

def _safe_execute(conn, sql: str, params: tuple = (), log_errors: bool = False) -> bool:
    try:
        conn.execute(sql, params)
        return True
    except Exception as exc:
        if log_errors:
            log.warning("reset sql failed [%s]: %s", sql.split()[2] if len(sql.split()) > 2 else sql, exc)
        return False


def sync_player_progress(conn, user_id: int, reset_wealth: bool = False,
                         initial_money: int | None = None) -> int:
    """نسخهٔ sync همان `reset_player_progress` برای sqlite3 معمولی."""
    done = 0
    for sql, cols in USER_DELETE_SQL:
        done += 1 if _safe_execute(conn, sql, tuple(user_id for _ in cols)) else 0
    for sql in PLAYER_UPDATE_SQL:
        done += 1 if _safe_execute(conn, sql, (user_id,)) else 0
    if reset_wealth:
        money = initial_money if initial_money is not None else 200_000_000
        done += 1 if _safe_execute(
            conn, "UPDATE users SET royal_coins=0, money=? WHERE id=?", (money, user_id)) else 0
    return done


def sync_full_reset(conn, reset_wealth: bool = True, keep_bans: bool = True,
                    initial_money: int | None = None, log_errors: bool = False) -> dict:
    """نسخهٔ sync ریست کامل برای پنل وب."""
    total_users = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    total_countries = int(conn.execute("SELECT COUNT(*) FROM countries").fetchone()[0])
    total_assets = int(conn.execute(
        "SELECT COALESCE(SUM(quantity),0) FROM player_assets").fetchone()[0])

    cleared = 0
    for table in CLEAR_TABLES:
        cleared += 1 if _safe_execute(conn, f"DELETE FROM {table}", (), log_errors) else 0
    for sql in GLOBAL_UPDATE_SQL:
        _safe_execute(conn, sql, (), log_errors)

    if reset_wealth:
        money = initial_money if initial_money is not None else 200_000_000
        conn.execute("UPDATE users SET country_id=NULL, country_taken_at=NULL, "
                     "royal_coins=0, money=?", (money,))
    else:
        conn.execute("UPDATE users SET country_id=NULL, country_taken_at=NULL")
    if not keep_bans:
        conn.execute("UPDATE users SET banned=0")

    # 🗺 استان‌های پایه (۵ تای هر کشور، بدون مالک)
    try:
        names = ["استان مرکزی", "استان شمالی", "استان جنوبی", "استان شرقی", "استان غربی"]
        for (cid,) in conn.execute("SELECT id FROM countries WHERE is_active=1").fetchall():
            for idx, name in enumerate(names):
                conn.execute(
                    "INSERT OR IGNORE INTO provinces(country_id, idx, name, owner_id) "
                    "VALUES(?,?,?,NULL)", (cid, idx, name))
        conn.execute("UPDATE countries SET province_count=5 WHERE owner_id IS NULL")
    except Exception as exc:
        log.warning("sync_full_reset provinces: %s", exc)
    conn.commit()
    return {
        "users": total_users,
        "countries": total_countries,
        "assets": total_assets,
        "tables": len(CLEAR_TABLES),
        "cleared": cleared,
    }

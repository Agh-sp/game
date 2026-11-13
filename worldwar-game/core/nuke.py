"""☢️ سلاح هسته‌ای — از غنی‌سازی ۹۰٪ تا کلاهک واقعی و ضربهٔ هسته‌ای.

پس از تکمیل مرحلهٔ ۴ غنی‌سازی (۹۰٪) کشور «مواد شکاف‌پذیر» دارد، اما بمب اتم
چیزی است که باید **ساخته** شود: طراحی، مونتاژ، آزمایش و نگهداری. این ماژول
همان چرخهٔ واقعی را شبیه‌سازی می‌کند:

    غنی‌سازی ۹۰٪  →  🏭 ساخت کلاهک (هزینه + مصالح + سکه + زمان)
                  →  ☢️ زرادخانه (سقف قابل تنظیم، ثبت هر کلاهک با قدرت و نام)
                  →  🎯 شلیک به کشور دشمن (کول‌داون، غارت، جداشدن استان، فرسایش)

**واقعیت‌گرایی پیامدها:**

- 💥 تلفات غیرنظامی و افت شدید رضایت کشور هدف (قابل تنظیم از پنل ادمین)
- 🗺 احتمال جدا شدن استان‌های هدف (فقط با قدرت کافی؛ هرگز کل کشور یک‌جا)
- ⛓ فرسایش سنگین کشور هدف (زیرساخت، اقتصاد، روحیه)
- 🌍 محکومیت جهانی: رضایت خود مهاجم هم افت می‌کند و در کانال رسمی اعلام می‌شود
- 🚫 کول‌داون چندساعته بین دو ضربهٔ هسته‌ای (بازدارندگی واقعی)
- 🛡 پدافند هدف می‌تواند بخشی از اثر را کم کند (رهگیری کلاهک سخت است، اما نه صفر)
- 🔥 احتمال فاجعهٔ انسانی/نشت (اثر جانبی غیرقابل کنترل)

جدول‌ها: `nuclear_arsenal` (شمارش) و `nuclear_bombs` (تک‌تک کلاهک‌ها).
همهٔ اعداد از پنل ادمین (`nuke_*`) قابل تغییرند.
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting
from core.utils import add_hours, fmt, fmt_money, iso, is_past

log = logging.getLogger(__name__)

BOMB_STAGE = 4          # فقط بعد از غنی‌سازی ۹۰٪
DEFAULT_COST_M = 1800
DEFAULT_MATERIALS = 40_000
DEFAULT_COINS = 25
DEFAULT_MINUTES = 30
DEFAULT_YIELD = 150
DEFAULT_LIMIT = 8

# 🏭 صف ساخت هیچ‌وقت در حافظهٔ پروسه نگه داشته نمی‌شود (ری‌استارت سرور آن را از بین
# می‌برد)؛ هر کلاهک در حال ساخت یک ردیف در `nuclear_bombs` با
# state='building' و `ready_at` دارد و زمان‌بند سرور آن را تحویل می‌دهد.
_PREPARED = False


async def _num(key: str, default: float) -> float:
    try:
        raw = await get_setting(key, "")
        return float(str(raw).strip()) if str(raw).strip() else default
    except (TypeError, ValueError):
        return default


async def _add_columns() -> None:
    """مهاجرت سبک برای دیتابیس‌های قبلی (idempotent)."""
    for table, cols in (
        ("nuclear_arsenal", (("bombs", "INTEGER DEFAULT 0"),
                             ("built_total", "INTEGER DEFAULT 0"),
                             ("last_built_at", "TEXT"),
                             ("last_used_at", "TEXT"))),
        ("nuclear_bombs", (("yield_kt", "REAL DEFAULT 0"),
                           ("state", "TEXT DEFAULT 'ready'"),
                           ("name", "TEXT DEFAULT ''"),
                           ("target_id", "INTEGER DEFAULT 0"))),
    ):
        try:
            names = {c["name"] for c in await db.fetchall(f"PRAGMA table_info({table})")}
            for col, decl in cols:
                if col not in names:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        except Exception:
            log.exception("migration failed for %s", table)


async def _ensure() -> None:
    """یک‌بار ساخت جدول‌ها/ستون‌های لازم را تضمین می‌کند (روی دیتابیس‌های قدیمی هم)."""
    global _PREPARED
    if _PREPARED:
        return
    try:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS nuclear_arsenal (user_id INTEGER PRIMARY KEY, "
            "bombs INTEGER DEFAULT 0, built_total INTEGER DEFAULT 0, last_built_at TEXT, "
            "last_used_at TEXT, created_at TEXT DEFAULT (datetime('now')))")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS nuclear_bombs (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "owner_id INTEGER, name TEXT DEFAULT '', yield_kt REAL DEFAULT 0, "
            "state TEXT DEFAULT 'ready', built_at TEXT, used_at TEXT, "
            "target_id INTEGER DEFAULT 0, ready_at TEXT)")
    except Exception:            # دیتابیس قفل بود؟ دفعهٔ بعد دوباره تلاش می‌شود
        log.exception("nuke ensure tables failed")
        return
    await _add_columns()
    _PREPARED = True


async def arsenal(user_id: int) -> dict:
    """وضعیت زرادخانهٔ کشور."""
    await _ensure()
    row = await db.fetchone("SELECT * FROM nuclear_arsenal WHERE user_id=?", (int(user_id),))
    if not row:
        await db.execute("INSERT OR IGNORE INTO nuclear_arsenal(user_id) VALUES(?)",
                         (int(user_id),))
        row = await db.fetchone("SELECT * FROM nuclear_arsenal WHERE user_id=?", (int(user_id),))
    return dict(row) if row else {"user_id": user_id, "bombs": 0, "built_total": 0}


async def bomb_list(user_id: int, limit: int = 12) -> list[dict]:
    """کلاهک‌های ساخته‌شدهٔ کشور (آماده یا مصرف‌شدهٔ اخیر)."""
    try:
        rows = await db.fetchall(
            "SELECT * FROM nuclear_bombs WHERE owner_id=? AND state IN ('ready','launched') "
            "ORDER BY id DESC LIMIT ?", (int(user_id), int(limit)))
        return [dict(r) for r in rows]
    except Exception:
        return []


async def can_build(user_id: int) -> tuple[bool, str]:
    """آیا کشور می‌تواند کلاهک بسازد؟"""
    from core import enrichment, nuclear

    if await building_info(user_id):
        return False, "⏳ یک کلاهک در حال ساخت است — صبر کنید تا آماده شود."
    st = await enrichment.get_state(user_id)
    stage = int(st.get("stage") or 0)
    if stage < BOMB_STAGE:
        return False, (f"🔒 برای ساخت بمب اتم باید غنی‌سازی ۹۰٪ کامل شود "
                       f"(پیشرفت شما: {stage}/{BOMB_STAGE}).")
    # تأسیسات باید فعال باشد (بمب در تأسیسات سالم مونتاژ می‌شود)
    site = await nuclear.ensure_site(user_id)
    if not site:
        return False, "❌ تأسیسات هسته‌ای ندارید — اول غنی‌سازی را شروع کنید."
    if int(site.get("hp") or 0) <= 0 or not int(site.get("active") or 0):
        return False, ("💥 تأسیسات هسته‌ای شما از کار افتاده است — اول با "
                       "«🔧 بازسازی تأسیسات» آن را فعال کنید.")
    inv = await arsenal(user_id)
    limit = int(await _num("nuke_bomb_limit", DEFAULT_LIMIT))
    if limit > 0 and int(inv.get("bombs") or 0) >= limit:
        return False, (f"📦 زرادخانهٔ شما پر است ({limit} کلاهک). ابتدا از کلاهک‌ها "
                       "استفاده کنید یا سقف را از پنل ادمین بالا ببرید.")
    cost_m = await _num("nuke_bomb_cost_m", DEFAULT_COST_M)
    mats = int(await _num("nuke_bomb_materials", DEFAULT_MATERIALS))
    coins = int(await _num("nuke_bomb_coins", DEFAULT_COINS))
    user = await db.fetchone("SELECT money, royal_coins FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost_m * 1_000_000:
        return False, (f"❌ بودجه کافی نیست.\n💰 نیاز: <b>{fmt_money(int(cost_m * 1_000_000))}</b>\n"
                       f"💰 خزانه: <b>{fmt_money(money)}</b>")
    state = await db.fetchone("SELECT materials FROM states WHERE user_id=?", (user_id,))
    have_mats = int((state or {}).get("materials") or 0)
    if have_mats < mats:
        return False, (f"❌ مصالح کافی نیست.\n🧱 نیاز: <b>{fmt(mats)}</b>\n"
                       f"🧱 موجودی: <b>{fmt(have_mats)}</b>\n"
                       "💡 از «🧱 خرید مصالح» در پادگان بخرید.")
    if coins and int((user or {}).get("royal_coins") or 0) < coins:
        return False, (f"❌ سکه شاهی کافی نیست. نیاز: <b>{fmt(coins)}</b> — "
                       f"موجودی: {fmt(int((user or {}).get('royal_coins') or 0))}")
    return True, ""


async def build(bot, user_id: int, name: str = "") -> tuple[bool, str]:
    """🏭 ساخت یک کلاهک هسته‌ای (پرداخت هزینه + شروع زمان ساخت)."""
    ok, err = await can_build(user_id)
    if not ok:
        return False, err
    cost_m = await _num("nuke_bomb_cost_m", DEFAULT_COST_M)
    mats = int(await _num("nuke_bomb_materials", DEFAULT_MATERIALS))
    coins = int(await _num("nuke_bomb_coins", DEFAULT_COINS))
    minutes = int(await _num("nuke_bomb_minutes", DEFAULT_MINUTES))
    money = int(cost_m * 1_000_000)
    await db.execute("UPDATE users SET money=MAX(0,money-?) WHERE id=?", (money, user_id))
    await db.execute("UPDATE states SET materials=MAX(0,COALESCE(materials,0)-?) WHERE user_id=?",
                     (mats, user_id))
    if coins:
        await db.execute("UPDATE users SET royal_coins=MAX(0,royal_coins-?) WHERE id=?",
                         (coins, user_id))
    from core.utils import now, parse
    from datetime import timedelta
    ready_at = (now() + timedelta(minutes=max(0, minutes))).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        "INSERT INTO nuclear_bombs(owner_id, name, yield_kt, state, built_at, ready_at) "
        "VALUES(?,?,?,'building',?,?)",
        (int(user_id), (name or "").strip()[:40], 0, iso(), ready_at))
    try:
        from core.events import log_event
        await log_event("science", "☢️ ساخت کلاهک هسته‌ای آغاز شد")
    except Exception:
        pass
    # اگر زمان ساخت صفر بود، همان لحظه تحویل بده
    if minutes <= 0:
        await settle(user_id, bot=bot)
    return True, (f"☢️ <b>ساخت کلاهک هسته‌ای آغاز شد</b>\n\n"
                  f"⏱ زمان آماده‌شدن: <b>{minutes} دقیقه</b>\n"
                  f"📅 آماده در: {ready_at} (UTC)\n"
                  f"💰 هزینه: {fmt_money(money)} | 🧱 {fmt(mats)} مصالح"
                  + (f" | 🪙 {fmt(coins)} سکه" if coins else "") + "\n\n"
                  "💡 می‌توانید ربات را ببندید؛ تکمیل خودکار ثبت می‌شود.")


async def building_info(user_id: int) -> dict | None:
    """🏭 کلاهک در حال ساخت (اگر تمام نشده باشد)."""
    await _ensure()
    try:
        row = await db.fetchone(
            "SELECT * FROM nuclear_bombs WHERE owner_id=? AND state='building' "
            "ORDER BY id ASC LIMIT 1", (int(user_id),))
    except Exception:
        return None
    return dict(row) if row else None


async def settle(user_id: int, bot=None) -> dict | None:
    """تحویل کلاهکی که زمان ساختش گذشته است (منبع حقیقت: دیتابیس)."""
    await _ensure()
    item = await building_info(user_id)
    if not item:
        return None
    ready_at = item.get("ready_at") or ""
    if ready_at and not is_past(ready_at):
        return None
    yield_kt = await _num("nuke_bomb_yield_kt", DEFAULT_YIELD)
    name = item.get("name") or ""
    await db.execute("UPDATE nuclear_bombs SET state='ready', yield_kt=?, built_at=?, ready_at=NULL "
                     "WHERE id=?", (float(yield_kt), iso(), int(item["id"])))
    await db.execute("INSERT OR IGNORE INTO nuclear_arsenal(user_id) VALUES(?)", (int(user_id),))
    await db.execute(
        "UPDATE nuclear_arsenal SET bombs=COALESCE(bombs,0)+1, built_total=COALESCE(built_total,0)+1, "
        "last_built_at=? WHERE user_id=?", (iso(), int(user_id)))
    inv = await arsenal(user_id)
    try:
        from core.events import log_event
        await log_event("science", f"☢️ کلاهک هسته‌ای ({int(yield_kt)} کیلوتن) آماده شد")
    except Exception:
        pass
    if bot is not None:
        try:
            from gamebot.common import kb
            await bot.send_message(
                int(user_id),
                "☢️ <b>کلاهک هسته‌ای شما آماده شد!</b>\n\n"
                f"💣 قدرت: <b>{int(yield_kt)} کیلوتن</b>"
                + (f"\n🏷 نام: <b>{name}</b>" if name else "") +
                f"\n📦 زرادخانه: <b>{fmt(int(inv.get('bombs') or 0))}</b> کلاهک\n\n"
                "از «☢️ سلاح هسته‌ای» می‌توانید شلیک کنید.",
                reply_markup=kb([]))
        except Exception:
            pass
    return {"yield_kt": int(yield_kt), "bombs": int(inv.get("bombs") or 0)}


async def settle_all(bot=None) -> int:
    """تحویل همهٔ کلاهک‌های آماده (از زمان‌بند سرور)."""
    await _ensure()
    now_s = iso()
    try:
        rows = await db.fetchall(
            "SELECT DISTINCT owner_id FROM nuclear_bombs WHERE state='building' "
            "AND (ready_at IS NULL OR ready_at<=?)", (now_s,))
    except Exception:
        return 0
    done = 0
    for r in rows:
        if await settle(int(r["owner_id"]), bot=bot):
            done += 1
    return done


async def cooldown_left(user_id: int) -> int:
    """دقیقه‌های باقی‌مانده تا ضربهٔ هسته‌ای بعدی."""
    hours = await _num("nuke_strike_cooldown_hours", 12)
    if hours <= 0:
        return 0
    inv = await arsenal(user_id)
    last = inv.get("last_used_at")
    if not last:
        return 0
    try:
        from core.utils import now, parse
        then = parse(last)
        if not then:
            return 0
        used = (now() - then).total_seconds() / 60
    except Exception:
        return 0
    return max(0, int(round(hours * 60 - used)))


async def targets(user_id: int) -> list[dict]:
    """کشورهای قابل هدف برای ضربهٔ هسته‌ای (همهٔ کشورهای فعال به‌جز خودم)."""
    try:
        rows = await db.fetchall(
            "SELECT u.id AS user_id, c.name, c.flag, c.population FROM users u "
            "JOIN countries c ON c.id=u.country_id "
            "WHERE u.banned=0 AND u.id!=? AND u.country_id IS NOT NULL "
            "ORDER BY c.population DESC", (int(user_id),))
        return [dict(r) for r in rows]
    except Exception:
        return []


async def can_strike(user_id: int) -> tuple[bool, str]:
    """آیا کشور می‌تواند ضربهٔ هسته‌ای بزند؟"""
    inv = await arsenal(user_id)
    if int(inv.get("bombs") or 0) <= 0:
        return False, ("❌ کلاهک آماده ندارید. اول از «🏭 ساخت کلاهک» یکی بسازید "
                       "(نیازمند غنی‌سازی ۹۰٪).")
    left = await cooldown_left(user_id)
    if left > 0:
        return False, (f"⏱ پس از هر ضربهٔ هسته‌ای باید {left} دقیقه صبر کنید "
                       "(کول‌داون از پنل ادمین قابل تغییر است).")
    return True, ""


async def outlook(attacker_id: int, defender_id: int) -> dict:
    """پیش‌نمایش اثر ضربهٔ هسته‌ای (هیچ‌چیز تغییر نمی‌کند)."""
    from core.economy import get_country
    from core import nuclear

    d_country = await get_country(defender_id)
    prov = await db.fetchone("SELECT COUNT(*) c FROM provinces WHERE owner_id=?",
                            (int(defender_id),))
    provinces = int((prov or {}).get("c") or 0)
    shield = 0
    try:
        shield = await nuclear.defense_power(defender_id)
    except Exception:
        shield = 0
    try:
        from core import sabotage
        shield += await sabotage.air_shield(defender_id)
    except Exception:
        pass
    # رهگیری کلاهک سخت است: حداکثر ۳۵٪ اثر با پدافند بسیار قوی کم می‌شود
    mitig = min(0.35, shield / max(1.0, shield + 400_000))
    inv = await arsenal(attacker_id)
    bombs = await bomb_list(attacker_id)
    yield_kt = float((bombs[0] or {}).get("yield_kt") or 0) if bombs else 0
    if not yield_kt:
        yield_kt = await _num("nuke_bomb_yield_kt", DEFAULT_YIELD)
    civilian = int(await _num("nuke_blast_civilian", 900_000) * (1 - mitig))
    sat_drop = round(await _num("nuke_blast_satisfaction", 45) * (1 - mitig), 1)
    loot_pct = await _num("nuke_blast_loot_percent", 25) * (1 - mitig)
    wear = round(await _num("nuke_blast_wear", 35) * (1 - mitig), 1)
    return {
        "country": d_country, "provinces": provinces, "shield": int(shield),
        "mitigation": round(mitig * 100, 1), "bombs": int(inv.get("bombs") or 0),
        "yield_kt": int(yield_kt), "civilian": max(0, civilian),
        "satisfaction_drop": sat_drop, "loot_percent": round(loot_pct, 1),
        "wear": wear,
    }


async def strike(bot, attacker_id: int, defender_id: int) -> str:
    """☢️ شلیک واقعی یک کلاهک هسته‌ای به کشور دشمن. خروجی: گزارش کامل."""
    from core.economy import announce, get_country
    from core.events import log_event

    ok, err = await can_strike(attacker_id)
    if not ok:
        return err
    if int(attacker_id) == int(defender_id):
        return "❌ نمی‌توانید کشور خودتان را هسته‌ای بزنید."
    d_country = await get_country(defender_id)
    a_country = await get_country(attacker_id)
    if not d_country:
        return "❌ کشور هدف پیدا نشد."
    a_name = f"{a_country['flag']} <b>{a_country['name']}</b>" if a_country else "مهاجم"
    d_name = f"{d_country['flag']} <b>{d_country['name']}</b>"

    look = await outlook(attacker_id, defender_id)
    mitig = look["mitigation"] / 100

    # کلاهک مصرف می‌شود
    bombs = await bomb_list(attacker_id)
    bomb_id = int(bombs[0]["id"]) if bombs else 0
    yield_kt = int(look["yield_kt"])
    await db.execute("UPDATE nuclear_arsenal SET bombs=MAX(0,COALESCE(bombs,0)-1), "
                     "last_used_at=? WHERE user_id=?", (iso(), int(attacker_id)))
    if bomb_id:
        await db.execute("UPDATE nuclear_bombs SET state='launched', used_at=?, target_id=? "
                         "WHERE id=?", (iso(), int(defender_id), bomb_id))

    # 💥 اثرها
    civilian = int(look["civilian"])
    sat_drop = look["satisfaction_drop"]
    await db.execute(
        "UPDATE states SET satisfaction=MAX(0, satisfaction-?) WHERE user_id=?",
        (sat_drop, int(defender_id)))
    # غارت خزانه
    d_user = await db.fetchone("SELECT money FROM users WHERE id=?", (int(defender_id),))
    loot = int(int((d_user or {}).get("money") or 0) * look["loot_percent"] / 100)
    if loot:
        await db.execute("UPDATE users SET money=MAX(0,money-?) WHERE id=?", (loot, int(defender_id)))
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (loot, int(attacker_id)))
    # فرسایش سنگین
    wear_line = ""
    try:
        from core import attrition as attr
        await attr.add_strike(int(defender_id), int(attacker_id), look["wear"])
        wear_line = f"⛓ فرسایش کشور هدف: <b>+{look['wear']}٪</b>"
    except Exception:
        log.exception("nuclear wear failed")

    # 🗺 جدا شدن استان‌ها (محدود)
    province_lines: list[str] = []
    chance = await _num("nuke_blast_provinces", 40)
    max_prov = int(await _num("nuke_blast_max_provinces", 2))
    taken = 0
    if max_prov > 0:
        rows = await db.fetchall(
            "SELECT id, name FROM provinces WHERE owner_id=? ORDER BY RANDOM() LIMIT ?",
            (int(defender_id), max_prov))
        for row in rows:
            if random.random() * 100 > chance:
                continue
            await db.execute("UPDATE provinces SET owner_id=?, captured_at=? WHERE id=?",
                             (int(attacker_id), iso(), row["id"]))
            await db.execute(
                "INSERT INTO provinces_history(province_id, from_owner, to_owner, created_at) "
                "VALUES(?,?,?,?)", (row["id"], int(defender_id), int(attacker_id), iso()))
            province_lines.append(f"  • 🗺 <b>{row['name'] or 'یک استان'}</b> از کنترل دشمن خارج شد")
            taken += 1
    # رضایت خود مهاجم (محکومیت جهانی)
    self_drop = await _num("nuke_fallout_self", 6)
    if self_drop > 0:
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-?) WHERE user_id=?",
                         (self_drop, int(attacker_id)))

    # ☢️ احتمال فاجعهٔ انسانی جانبی
    catastrophe = ""
    if random.random() * 100 < await _num("nuke_catastrophe_chance", 6):
        extra = int(civilian * 0.5)
        civilian += extra
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-8) WHERE user_id=?",
                         (int(defender_id),))
        catastrophe = ("\n🔥 <b>فاجعهٔ انسانی:</b> آتش‌سوزی گسترده و نشت مواد پرتوزا؛ "
                       f"{fmt(extra)} تلفات غیرنظامی اضافه و افت رضایت بیشتری ثبت شد.")

    await log_event("war", f"☢️ {a_country['name'] if a_country else attacker_id} ضربهٔ هسته‌ای "
                          f"به {d_country['name']} زد ({yield_kt} کیلوتن)")
    try:
        await db.execute(
            "INSERT INTO nuclear_strikes(attacker_id, defender_id, success, damage, created_at) "
            "VALUES(?,?,1,?,?)", (int(attacker_id), int(defender_id), int(yield_kt), iso()))
    except Exception:
        pass

    lines = [
        "☢️💥 <b>ضربهٔ هسته‌ای!</b>",
        "",
        f"🚀 مهاجم: {a_name}",
        f"🎯 هدف: {d_name}",
        f"💣 قدرت کلاهک: <b>{fmt(yield_kt)} کیلوتن</b>",
        f"🛡 پدافند هدف: <b>{fmt(look['shield'])}</b> — اثر حمله "
        f"<b>{100 - look['mitigation']}٪</b> باقی ماند",
        "",
        f"💀 تلفات غیرنظامی تخمینی: <b>{fmt(civilian)}</b> نفر",
        f"😞 افت رضایت مردم هدف: <b>-{sat_drop}٪</b>",
        wear_line or None,
        f"💰 غارت خزانه: <b>{fmt_money(loot)}</b>" if loot else None,
        "",
        "🗺 <b>استان‌های از دست رفتهٔ دشمن:</b>" if province_lines else "🗺 استانی جدا نشد.",
        *province_lines,
        catastrophe or None,
        "",
        f"🌍 <b>محکومیت جهانی:</b> رضایت مردم {a_country['name'] if a_country else 'مهاجم'} "
        f"<b>-{self_drop}٪</b> افت کرد.",
        "",
        "⚠️ این حمله در تاریخ جهان ثبت شد. بازمانده‌ها انتقام می‌گیرند.",
    ]
    report = "\n".join(x for x in lines if x)
    try:
        await announce(bot, report, section="war_attack")
    except Exception:
        log.exception("nuclear announce failed")
    try:
        from gamebot.common import dm
        await dm(bot, int(defender_id), report)
    except Exception:
        pass
    return report


async def arsenal_text(user_id: int) -> str:
    """متن وضعیت زرادخانه و امکان ساخت."""
    from core import enrichment

    inv = await arsenal(user_id)
    st = await enrichment.get_state(user_id)
    stage = int(st.get("stage") or 0)
    limit = int(await _num("nuke_bomb_limit", DEFAULT_LIMIT))
    bombs = await bomb_list(user_id)
    cost_m = await _num("nuke_bomb_cost_m", DEFAULT_COST_M)
    mats = int(await _num("nuke_bomb_materials", DEFAULT_MATERIALS))
    coins = int(await _num("nuke_bomb_coins", DEFAULT_COINS))
    minutes = int(await _num("nuke_bomb_minutes", DEFAULT_MINUTES))
    yld = int(await _num("nuke_bomb_yield_kt", DEFAULT_YIELD))
    left = await cooldown_left(user_id)

    lines = [
        "☢️ <b>سلاح هسته‌ای</b>",
        "",
        f"🧪 غنی‌سازی: <b>{stage}/{BOMB_STAGE}</b>"
        + ("  ✅ آمادهٔ ساخت کلاهک" if stage >= BOMB_STAGE else "  🔒 ناکافی"),
        f"📦 زرادخانه: <b>{fmt(int(inv.get('bombs') or 0))}</b>"
        + (f" از سقف {limit}" if limit else ""),
        f"🏭 کل ساخته‌شده: {fmt(int(inv.get('built_total') or 0))}",
    ]
    build_state = await building_info(user_id)
    if build_state:
        lines.append(f"⏳ در حال ساخت — آماده در <b>{build_state['ready_at']}</b> (UTC)")
    if left:
        lines.append(f"⏱ کول‌داون ضربهٔ بعدی: <b>{left}</b> دقیقه")
    if bombs:
        lines.append("")
        lines.append("<b>کلاهک‌های آماده:</b>")
        for b in bombs[:5]:
            tag = b.get("name") or f"کلاهک #{b['id']}"
            lines.append(f"  • {tag} — <b>{int(b.get('yield_kt') or 0)}</b> کیلوتن")
    if stage < BOMB_STAGE:
        lines.append("\n🔒 بمب اتم فقط پس از تکمیل مرحلهٔ ۴ غنی‌سازی (۹۰٪) ساخته می‌شود.")
    else:
        lines += [
            "",
            "🏭 <b>هزینهٔ ساخت هر کلاهک:</b>",
            f"  💰 {fmt_money(int(cost_m * 1_000_000))} • 🧱 {fmt(mats)} مصالح"
            + (f" • 🪙 {fmt(coins)} سکه" if coins else ""),
            f"  ⏱ {minutes} دقیقه • 💣 قدرت {fmt(yld)} کیلوتن",
            "",
            "⚠️ هر ضربهٔ هسته‌ای تلفات غیرنظامی، فرسایش و محکومیت جهانی دارد.",
        ]
    return "\n".join(lines)

"""🏃 پناهندگان و فرار مغزها — هزینهٔ انسانی جنگ و قطعی خدمات.

واقعیت: بمباران شهرها، قطعی برق و آب و اشغال استان‌ها مردم را به آن‌سوی مرزها
می‌فرستد. کشور مبدأ نیروی کار و رضایت از دست می‌دهد و کشور مقصد هزینه و
نارضایتی می‌گیرد؛ مگر آنکه با پول آن‌ها را اسکان دهد یا برگرداند.

مکانیک:
  • `flight_tick` برای هر کشور: سهم جمعیت بر اساس استان‌های اشغال‌شده، قطعی‌های
    خدمات، خاموشی شبکه و فرسایش جنگ محاسبه می‌شود و از جمعیت کشور کسر می‌گردد.
  • اگر کشور هم‌مرز/هم‌منطقه‌ای پیدا شود، پناهندگان به آن کشور می‌روند و
    نارضایتی میزبان بالا می‌رود (`refugee_satisfaction_hit`).
  • بازیکن می‌تواند با هزینهٔ `refugee_return_cost_m` هر ۱۰۰۰ نفر را اسکان دهد و
    ناآرامی میزبان را کم کند (`host_tick` هشدار می‌دهد).
همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting
from core.utils import fmt, iso

log = logging.getLogger(__name__)

DEFAULT_PCT_PER_PROVINCE = 0.05
DEFAULT_PCT_PER_HIT = 0.02
DEFAULT_RETURN_COST_M = 10.0
DEFAULT_SAT_HIT = 1.5


async def _num(key: str, default: float) -> float:
    try:
        raw = await get_setting(key, "")
    except Exception:
        return default
    try:
        return float(str(raw).strip()) if str(raw).strip() else default
    except (TypeError, ValueError):
        return default


async def enabled() -> bool:
    try:
        return await get_setting("sec_refugees", "1") == "1"
    except Exception:
        return True


BORDER_REGIONS = {"آسیا", "اروپا", "آفریقا", "خاورمیانه"}


async def _pick_host(source_user: int) -> dict | None:
    """کشور میزبان: هم‌منطقه و بازیکن‌دار (ترجیح کشوری با رضایت بالاتر)."""
    src = await db.fetchone(
        "SELECT c.region FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (source_user,))
    if not src:
        return None
    rows = await db.fetchall(
        "SELECT u.id, c.name, c.flag, COALESCE(s.satisfaction,50) sat FROM users u "
        "JOIN countries c ON c.id=u.country_id LEFT JOIN states s ON s.user_id=u.id "
        "WHERE u.id!=? AND u.banned=0 AND c.is_active=1 AND c.region=? "
        "ORDER BY sat DESC", (source_user, src["region"]))
    if not rows:
        rows = await db.fetchall(
            "SELECT u.id, c.name, c.flag, COALESCE(s.satisfaction,50) sat FROM users u "
            "JOIN countries c ON c.id=u.country_id LEFT JOIN states s ON s.user_id=u.id "
            "WHERE u.id!=? AND u.banned=0 AND c.is_active=1 ORDER BY sat DESC LIMIT 5",
            (source_user,))
    return rows[0] if rows else None


async def flight_tick(user_id: int) -> dict:
    """محاسبه و اعمال موج پناهندگان برای یک کشور."""
    if not await enabled():
        return {"fled": 0}
    try:
        country = await db.fetchone(
            "SELECT c.* FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?", (user_id,))
    except Exception:
        country = None
    if not country:
        return {"fled": 0}
    pop = int(country.get("population") or 0)
    if pop <= 0:
        return {"fled": 0}
    state = await db.fetchone("SELECT * FROM states WHERE user_id=?", (user_id,)) or {}
    reasons: dict[str, float] = {}
    # 🗺 استان‌های اشغال‌شده
    try:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM provinces WHERE country_id=? AND owner_id IS NOT NULL "
            "AND owner_id!=?", (country["id"], user_id))
        occ = int((row or {}).get("c") or 0)
        if occ:
            reasons["🗺 اشغال استان‌ها"] = occ * await _num("refugee_pct_per_province",
                                                           DEFAULT_PCT_PER_PROVINCE)
    except Exception:
        pass
    # ⚡ قطعی خدمات و خاموشی شبکه
    hits = sum(1 for k in ("blackout_power", "blackout_water", "blackout_gas")
               if float(state.get(k) or 0) > 0)
    try:
        from core import grid
        if await grid.hours_left(user_id) > 0:
            hits += 1
    except Exception:
        pass
    if hits:
        reasons["⚡ قطعی خدمات و خاموشی"] = hits * await _num("refugee_pct_per_hit",
                                                             DEFAULT_PCT_PER_HIT)
    # ⛓ فرسایش جنگ
    try:
        from core import attrition as attr
        wear = await attr.wear_of(user_id)
        if wear >= 40:
            reasons["⛓ ویرانی جنگ"] = 0.02
    except Exception:
        pass
    pct = min(0.35, sum(reasons.values()))
    if pct <= 0:
        return {"fled": 0, "reasons": reasons}
    fled = max(1, int(pop * pct * random.uniform(0.7, 1.2)))
    new_pop = max(10_000, pop - fled)
    await db.execute("UPDATE countries SET population=? WHERE id=?", (new_pop, country["id"]))
    await db.execute(
        "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
        (round(pct * 40, 1), user_id))
    host = await _pick_host(user_id)
    lines = [f"🏃 <b>موج پناهندگان:</b> {fmt(fled)} نفر از {country['flag']} "
             f"<b>{country['name']}</b> مهاجرت کردند (جمعیت: {fmt(pop)} → {fmt(new_pop)})"]
    for k, v in reasons.items():
        lines.append(f"   • {k}: {round(v * 100, 1)}٪ جمعیت")
    if host:
        sat_hit = await _num("refugee_satisfaction_hit", DEFAULT_SAT_HIT)
        await db.execute(
            "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
            (sat_hit, host["id"]))
        try:
            from core import unrest as unrest_mod
            await unrest_mod.add_unrest(host["id"], 3)
        except Exception:
            pass
        lines.append(f"   ↪️ پذیرش: {host['flag']} <b>{host['name']}</b> "
                     f"(رضایت میزبان −{sat_hit})")
        await db.execute(
            "INSERT INTO refugee_flows(from_user, to_user, count, reason, created_at) VALUES(?,?,?,?,?)",
            (user_id, host["id"], fled, "، ".join(reasons.keys()) or "جنگ", iso()))
        try:
            from gamebot.common import dm
            if dm:
                pass
        except Exception:
            pass
    try:
        from core.events import log_event
        await log_event("war", f"🏃 {fmt(fled)} پناهنده از {country['name']} "
                              f"به {host['name'] if host else 'خارج'} رفتند")
    except Exception:
        pass
    return {"fled": fled, "pop": new_pop, "reasons": reasons,
            "host": host, "lines": lines}


async def host_tick(user_id: int) -> dict:
    """اثر پناهندگان روی کشور میزبان: نارضایتی و هزینهٔ اسکان."""
    if not await enabled():
        return {"hosted": 0}
    row = await db.fetchone(
        "SELECT COALESCE(SUM(count),0) c FROM refugee_flows WHERE to_user=?", (user_id,))
    hosted = int((row or {}).get("c") or 0)
    if not hosted:
        return {"hosted": 0}
    # هشدار: هر ۱۰ هزار پناهنده یک امتیاز ناآرامی
    bump = min(10.0, hosted / 10_000)
    if bump > 0:
        try:
            from core import unrest as unrest_mod
            await unrest_mod.add_unrest(user_id, bump)
        except Exception:
            pass
    return {"hosted": hosted, "unrest_bump": round(bump, 1)}


async def resettle(user_id: int, count: int) -> tuple[bool, str]:
    """🏠 اسکان و بازگشت پناهندگان: ناآرامی میزبان را کم می‌کند."""
    count = max(100, int(count))
    unit = int(await _num("refugee_return_cost_m", DEFAULT_RETURN_COST_M) * 1_000_000)
    cost = max(1, int(unit * count / 1000))
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, f"❌ بودجه کافی نیست — اسکان {fmt(count)} نفر {fmt(cost)} می‌خواهد."
    row = await db.fetchone(
        "SELECT COALESCE(SUM(count),0) c FROM refugee_flows WHERE to_user=?", (user_id,))
    hosted = int((row or {}).get("c") or 0)
    if hosted <= 0:
        return False, "❌ پناهنده‌ای در کشور شما نیست."
    count = min(count, hosted)
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    remaining = count
    rows = await db.fetchall(
        "SELECT id, count FROM refugee_flows WHERE to_user=? AND count>0 ORDER BY id", (user_id,))
    for r in rows:
        if remaining <= 0:
            break
        take = min(remaining, int(r["count"]))
        await db.execute("UPDATE refugee_flows SET count=count-? WHERE id=?", (take, r["id"]))
        remaining -= take
    try:
        from core import unrest as unrest_mod
        await unrest_mod.add_unrest(user_id, -min(12.0, count / 5_000))
    except Exception:
        pass
    return True, (f"🏠 <b>{fmt(count)} پناهنده اسکان داده شدند.</b>\n"
                  f"💰 هزینه: {fmt(cost)}\n"
                  "🙂 ناآرامی کشور کمی کم شد و نیروی کار برگشت.")


async def refugees_text(user_id: int) -> str:
    rows = await db.fetchall(
        "SELECT r.from_user, r.count, r.reason, c.name, c.flag FROM refugee_flows r "
        "JOIN countries c ON c.id=(SELECT country_id FROM users WHERE id=r.from_user) "
        "WHERE r.to_user=? AND r.count>0 ORDER BY r.count DESC LIMIT 10", (user_id,))
    out = await db.fetchone(
        "SELECT COALESCE(SUM(count),0) c FROM refugee_flows WHERE from_user=?", (user_id,))
    lines = ["🏃 <b>پناهندگان و مهاجرت</b>", ""]
    if rows:
        total = sum(int(r["count"]) for r in rows)
        lines.append(f"📥 <b>پناهندگان در کشور شما: {fmt(total)} نفر</b>")
        for r in rows:
            lines.append(f"  • {r['flag']} {r['name']}: {fmt(r['count'])} نفر ({r['reason']})")
        unit = int(await _num("refugee_return_cost_m", DEFAULT_RETURN_COST_M) * 1_000_000)
        lines.append(f"\n🏠 هزینهٔ اسکان هر ۱۰۰۰ نفر: {fmt(unit)}")
        lines.append("💡 هر ۱۰ هزار پناهنده یک امتیاز ناآرامی به کشور شما اضافه می‌کند.")
    else:
        lines.append("📥 پناهنده‌ای در کشور شما نیست. ✅")
    fled = int((out or {}).get("c") or 0)
    if fled:
        lines.append(f"\n📤 تا امروز {fmt(fled)} نفر از کشور شما مهاجرت کرده‌اند.")
    lines.append("\n💡 علت‌های فرار: اشغال استان‌ها، قطعی برق/آب/گاز، خاموشی شبکه و ویرانی جنگ.")
    return "\n".join(lines)

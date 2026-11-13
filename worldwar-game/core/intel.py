"""🕵 شبکهٔ اطلاعاتی، جاسوسی و «مه اطلاعات» (Fog of War).

واقعیت: هیچ کشوری توان واقعی حریف را با عدد دقیق نمی‌داند. تصمیم‌های بزرگ
(حمله یا نه) روی **برآورد** گرفته می‌شود، نه روی عدد قطعی؛ و برآورد خوب پول
می‌خواهد.

مکانیک:
  • هر عملیات جاسوسی (`spy`) هزینه دارد، سطح شبکهٔ اطلاعاتی را کمی بالا می‌برد
    و یک **گزارش با بازهٔ خطا** می‌سازد: نیروی برآوردی = واقعی ± پهنای بازه.
  • پهنای بازه با هر سطح شبکه کم می‌شود (`intel_radius_step`).
  • هر جاسوسی شانس لو رفتن دارد (`intel_expose_chance`): رسوایی دیپلماتیک،
    افت روابط و بهانهٔ اعلام جنگ برای طرف مقابل.
  • گزارش‌ها `intel_expire_hours` ساعت معتبرند؛ پیش‌بینی نبرد هم از همین بازه
    استفاده می‌کند تا عدد قطعی نبیند.
همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting
from core.utils import add_hours, fmt, fmt_hm, hours_left, iso

log = logging.getLogger(__name__)

DEFAULT_COST_M = 12.0
DEFAULT_RADIUS = 0.35
DEFAULT_STEP = 0.05
DEFAULT_MAX_LEVEL = 5
DEFAULT_EXPOSE = 25.0
DEFAULT_EXPIRE = 12.0


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
        return await get_setting("sec_intel", "1") == "1"
    except Exception:
        return True


# ─── سطح شبکه ───

async def level(user_id: int) -> int:
    row = await db.fetchone("SELECT value FROM intel_levels WHERE user_id=?", (user_id,))
    return int((row or {}).get("value") or 0)


async def set_level(user_id: int, value: int) -> int:
    max_level = int(await _num("intel_max_level", DEFAULT_MAX_LEVEL))
    value = max(0, min(max_level, int(value)))
    await db.execute(
        "INSERT INTO intel_levels(user_id, value, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (user_id, value, iso()))
    return value


async def radius(user_id: int) -> float:
    """پهنای بازهٔ برآورد (± نسبت). هر سطح شبکه آن را کم می‌کند."""
    base = await _num("intel_radius_base", DEFAULT_RADIUS)
    step = await _num("intel_radius_step", DEFAULT_STEP)
    lvl = await level(user_id)
    return round(max(0.05, base - lvl * step), 3)


# ─── عملیات ───

async def spy(attacker_id: int, defender_id: int) -> tuple[bool, str]:
    """اجرای عملیات جاسوسی روی یک کشور."""
    if not await enabled():
        return False, "❌ بخش اطلاعات خاموش است."
    if attacker_id == defender_id:
        return False, "❌ نمی‌توانید علیه کشور خودتان جاسوسی کنید."
    try:
        from core import sabotage
        ok, err = await sabotage.can_sabotage(attacker_id, "internet")
        if not ok:
            return False, f"❌ برای جاسوسی به تجهیزات سایبری/ماهواره نیاز دارید.\n{err}"
    except Exception:
        pass
    cost = int(await _num("intel_cost_m", DEFAULT_COST_M) * 1_000_000)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (attacker_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, f"❌ بودجهٔ اطلاعات کافی نیست — نیاز: {fmt(cost)}"
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, attacker_id))

    from core.economy import army_power, get_country
    a_country = await get_country(attacker_id)
    d_country = await get_country(defender_id)
    a_name = f"{a_country['flag']} {a_country['name']}" if a_country else "شما"
    d_name = f"{d_country['flag']} {d_country['name']}" if d_country else "کشور هدف"
    atk, dfn, cyb = await army_power(defender_id)
    rad = await radius(attacker_id)
    est_atk = sample(atk, rad)
    est_def = sample(dfn, rad)

    exposed = random.random() * 100 < await _num("intel_expose_chance", DEFAULT_EXPOSE)
    new_level = await set_level(attacker_id, await level(attacker_id) + 1)
    expires = add_hours(await _num("intel_expire_hours", DEFAULT_EXPIRE))
    await db.execute(
        "INSERT INTO intel_reports(attacker_id, defender_id, est_attack, est_defense, "
        "real_attack, real_defense, radius, accuracy, exposed, expires_at, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (attacker_id, defender_id, est_atk, est_def, int(atk), int(dfn), rad,
         1 if not exposed else 0, 1 if exposed else 0, expires, iso()))
    try:
        from core.events import log_event
        await log_event("intel", f"{a_name} شبکهٔ اطلاعاتی خود را در {d_name} گسترش داد")
    except Exception:
        pass
    lines = [f"🕵 <b>گزارش اطلاعاتی</b>", "",
             f"🎯 هدف: {d_name}",
             f"📊 سطح شبکهٔ اطلاعاتی شما: <b>{new_level}</b> "
             f"(دقت ±{round(rad * 100)}٪)",
             "",
             f"⚔️ توان حملهٔ برآوردی: <b>{fmt(est_atk)}</b>",
             f"🛡 توان دفاعی برآوردی: <b>{fmt(est_def)}</b>",
             f"   (بازهٔ خطا: {fmt(atk * (1 - rad))} تا {fmt(atk * (1 + rad))})",
             f"⏳ اعتبار گزارش: {fmt_hm(hours_left(expires))}",
             "💡 به‌جای تکیه بر یک عدد، بازهٔ خطا را ببینید؛ هر جاسوسی تازه "
             "برآورد را دقیق‌تر می‌کند."]
    if exposed:
        await db.execute(
            "UPDATE states SET diplomacy=MAX(0, COALESCE(diplomacy,50)-15) WHERE user_id=?",
            (defender_id,))
        await db.execute(
            "UPDATE states SET diplomacy=MAX(0, COALESCE(diplomacy,50)-8) WHERE user_id=?",
            (attacker_id,))
        try:
            from core import unrest as unrest_mod
            await unrest_mod.add_unrest(attacker_id, 3)
        except Exception:
            pass
        lines += ["", "🚨 <b>جاسوس لو رفت!</b>",
                  "  • رسوایی دیپلماتیک: روابط شما با کشور هدف −۱۵",
                  "  • کشور هدف اکنون بهانهٔ اعلام جنگ دارد."]
        try:
            from core.events import log_event
            await log_event("intel", f"جاسوسی {a_name} در {d_name} لو رفت — رسوایی دیپلماتیک")
        except Exception:
            pass
    return True, "\n".join(lines)


def sample(real: float, radius: float) -> int:
    """یک برآورد تصادفی داخل بازهٔ خطا."""
    real = max(1.0, float(real or 0))
    low = real * (1 - radius)
    high = real * (1 + radius)
    return int(round(random.uniform(low, high)))


async def last_report(attacker_id: int, defender_id: int) -> dict | None:
    """آخرین گزارش معتبر (منقضی‌نشده) علیه یک کشور."""
    row = await db.fetchone(
        "SELECT * FROM intel_reports WHERE attacker_id=? AND defender_id=? AND expires_at>? "
        "ORDER BY id DESC LIMIT 1", (attacker_id, defender_id, iso()))
    return row


async def estimate(attacker_id: int, defender_id: int) -> dict:
    """برآورد فعلی: از گزارش معتبر استفاده می‌کند، وگرنه بازهٔ عریض بدون گزارش."""
    from core.economy import army_power
    atk, dfn, _ = await army_power(defender_id)
    report = await last_report(attacker_id, defender_id)
    if report:
        return {"estimate": True, "radius": float(report["radius"]),
                "est_attack": int(report["est_attack"]),
                "est_defense": int(report["est_defense"]),
                "low": int(atk * (1 - float(report["radius"]))),
                "high": int(atk * (1 + float(report["radius"]))),
                "real_attack": int(atk), "real_defense": int(dfn),
                "expires_at": report.get("expires_at")}
    base = await _num("intel_radius_base", DEFAULT_RADIUS)
    wide = round(min(0.95, base * 2.2), 3)
    return {"estimate": False, "radius": wide,
            "est_attack": int(atk), "est_defense": int(dfn),
            "low": int(atk * (1 - wide)), "high": int(atk * (1 + wide)),
            "real_attack": int(atk), "real_defense": int(dfn),
            "expires_at": ""}


async def battle_preview(attacker_id: int, defender_id: int) -> str:
    """پیش‌بینی نبرد با مه اطلاعات (برای صفحهٔ حمله)."""
    from core import combat
    from core.economy import army_power
    a_atk, a_def, _ = await army_power(attacker_id)
    est = await estimate(attacker_id, defender_id)
    real_chance = combat.battle_chance(a_atk, est["est_defense"])
    lo = combat.battle_chance(a_atk, max(1, est["high"]))
    hi = combat.battle_chance(a_atk, max(1, est["low"]))
    confidence = "دقیق" if est["estimate"] else "بسیار کم — جاسوسی بفرستید"
    return (f"🎲 <b>پیش‌بینی نبرد (با مه اطلاعات)</b>\n"
            f"   شانس پیروزی: <b>{round(lo * 100)}٪ تا {round(hi * 100)}٪</b>\n"
            f"   🛡 توان دفاعی برآوردی دشمن: {fmt(est['low'])} تا {fmt(est['high'])}\n"
            f"   📊 اعتماد به برآورد: <b>{confidence}</b>")


async def intel_text(user_id: int) -> str:
    lvl = await level(user_id)
    rad = await radius(user_id)
    cost = int(await _num("intel_cost_m", DEFAULT_COST_M) * 1_000_000)
    max_level = int(await _num("intel_max_level", DEFAULT_MAX_LEVEL))
    lines = ["🕵 <b>شبکهٔ اطلاعاتی</b>", "",
             f"📊 سطح شبکه: <b>{lvl}</b> از {max_level}",
             f"🎯 دقت برآورد: ±{round(rad * 100)}٪",
             f"💰 هزینهٔ هر عملیات: {fmt(cost)}",
             f"🚨 شانس لو رفتن: {round(await _num('intel_expose_chance', DEFAULT_EXPOSE))}٪",
             "",
             "💡 با جاسوسی روی کشور هدف، بازهٔ خطای توان نظامی‌اش تنگ‌تر می‌شود؛ "
             "بدون گزارش، پیش‌بینی نبرد فقط یک حدس پهن است."]
    try:
        rows = await db.fetchall(
            "SELECT r.*, c.flag, c.name FROM intel_reports r JOIN users u ON u.id=r.defender_id "
            "JOIN countries c ON c.id=u.country_id WHERE r.attacker_id=? AND r.expires_at>? "
            "ORDER BY r.id DESC LIMIT 5", (user_id, iso()))
    except Exception:
        rows = []
    if rows:
        lines.append("\n📁 <b>آخرین گزارش‌ها:</b>")
        for r in rows:
            flag = "🚨 لو رفته" if r["exposed"] else "✅ پنهان"
            lines.append(f"  • {r['flag']} {r['name']} — توان دفاعی "
                         f"{fmt(r['est_defense'])} | {flag} | {fmt_hm(hours_left(r['expires_at']))}")
    return "\n".join(lines)

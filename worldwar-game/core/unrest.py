"""✊ اعتصاب، اعتراض خیابانی و جنگ داخلی — «کشور از داخل می‌شکند».

واقعیت: پیش از آنکه یک کشور در جبهه سقوط کند، در خیابان می‌شکند. اعتصاب سراسری
اقتصاد را می‌خواباند و نارضایتی اگر مهار نشود به شورش مسلحانه و جنگ داخلی می‌رسد.

مکانیک (`states.unrest`):
  • ناآرامی هر دوره از رضایت پایین (`satisfaction < unrest_sat_threshold`)، قطعی
    برق/آب/گاز، فرسایش جنگ و استان‌های اشغال‌شده بالا می‌رود و با رضایت بالا
    به‌اندازهٔ `unrest_decay_per_period` پایین می‌آید.
  • عبور از `unrest_strike_threshold` → **اعتصاب سراسری**: درآمد نصف، شرکت‌ها تعطیل.
  • بازیکن سه راه دارد: 🎁 بستهٔ یارانه (پول)، 🪖 سرکوب نظامی (سرباز از دست می‌دهد
    و رضایت می‌افتد) یا ⏳ نادیده‌گرفتن (رضایت می‌افتد و ناآرامی بالا می‌رود).
  • اگر ناآرامی از `revolt_threshold` بگذرد → **جنگ داخلی**: درآمد به یک‌سوم می‌رسد
    و باید با امتیازدهی، خریدن فرماندهان شورشی یا سرکوب نظامی مهار شود؛ در غیر این
    صورت «شورای انقلابی» کشور را می‌گیرد (تغییر حاکمیت، نه سقوط کشور).

همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting
from core.utils import add_hours, fmt, fmt_hm, hours_left, iso, clamp

log = logging.getLogger(__name__)

DEFAULT_DECAY = 4.0
DEFAULT_SAT_THRESHOLD = 45.0
DEFAULT_STRIKE_THRESHOLD = 65.0
DEFAULT_STRIKE_MIN = 120.0
DEFAULT_STRIKE_INCOME = 0.5
DEFAULT_SUBSIDY_STEP = 15.0
DEFAULT_SUBSIDY_COST_M = 40.0
DEFAULT_CRACKDOWN_GAIN = 22.0
DEFAULT_CRACKDOWN_SAT = 6.0
DEFAULT_CRACKDOWN_LOSS = 0.06
DEFAULT_IGNORE_GAIN = 12.0
DEFAULT_IGNORE_SAT = 9.0
DEFAULT_RISE_PER_MISS = 22.0
DEFAULT_STRIKE_FAIL_PENALTY = 18.0

DEFAULT_REVOLT_THRESHOLD = 90.0
DEFAULT_REVOLT_MIN = 90.0
DEFAULT_REVOLT_INCOME = 0.35
DEFAULT_NEGOTIATE_COST_M = 150.0
DEFAULT_NEGOTIATE_GAIN = 35.0
DEFAULT_BRIBE_COST_M = 300.0
DEFAULT_BRIBE_CHANCE = 60.0
DEFAULT_BRIBE_GAIN = 40.0
DEFAULT_CRUSH_LOSS = 0.18
DEFAULT_RIVAL_SHARE = 0.10
DEFAULT_RIVAL_MONEY = 0.25

STRIKE_NAMES = {
    "labor": "✊ اعتصاب سراسری کارگران",
    "bazaar": "🏪 بستن بازار و اعتصاب اصناف",
    "students": "🎓 اعتراض دانشجویی و اعتصاب دانشگاه‌ها",
    "fuel": "⛽ اعتراض به گرانی سوخت",
    "water": "💧 اعتراض به بی‌آبی",
}
DEMANDS = {
    "labor": "افزایش دستمزد و لغو تعدیل نیرو",
    "bazaar": "لغو مالیات تازه و بازگرداندن یارانه",
    "students": "آزادی زندانیان سیاسی و اصلاح قانون",
    "fuel": "برگرداندن قیمت سوخت",
    "water": "رساندن آب به شهرها",
}


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
        return await get_setting("sec_unrest", "1") == "1"
    except Exception:
        return True


async def revolt_enabled() -> bool:
    try:
        return await get_setting("sec_revolt", "1") == "1"
    except Exception:
        return True


async def _state(user_id: int) -> dict:
    row = await db.fetchone("SELECT * FROM states WHERE user_id=?", (user_id,))
    if not row:
        await db.execute("INSERT OR IGNORE INTO states(user_id) VALUES(?)", (user_id,))
        row = await db.fetchone("SELECT * FROM states WHERE user_id=?", (user_id,)) or {}
    return row


async def get(user_id: int) -> dict:
    """وضعیت ناآرامی: unrest، آستانه‌ها، اعتصاب/شورش فعال و مهلت‌ها."""
    st = await _state(user_id)
    strike_th = await _num("unrest_strike_threshold", DEFAULT_STRIKE_THRESHOLD)
    revolt_th = await _num("revolt_threshold", DEFAULT_REVOLT_THRESHOLD)
    strike_active = bool(st.get("strike_until")) and str(st["strike_until"]) > iso()
    revolt_active = bool(st.get("revolt_until")) and str(st["revolt_until"]) > iso()
    return {
        "unrest": round(float(st.get("unrest") or 0), 1),
        "peak": round(float(st.get("unrest_peak") or 0), 1),
        "strike_threshold": strike_th,
        "revolt_threshold": revolt_th,
        "strike_active": strike_active,
        "strike_left": fmt_hm(hours_left(st.get("strike_until"))) if strike_active else "",
        "strike_demand": st.get("strike_demand") or "",
        "revolt_active": revolt_active,
        "revolt_left": fmt_hm(hours_left(st.get("revolt_until"))) if revolt_active else "",
        "revolt_winner": st.get("revolt_winner") or "",
    }


async def set_unrest(user_id: int, value: float) -> float:
    value = clamp(float(value), 0.0, 100.0)
    peak = max(value, float((await _state(user_id)).get("unrest_peak") or 0))
    await db.execute("UPDATE states SET unrest=?, unrest_peak=? WHERE user_id=?",
                     (round(value, 1), round(peak, 1), user_id))
    return round(value, 1)


async def add_unrest(user_id: int, delta: float) -> float:
    st = await _state(user_id)
    return await set_unrest(user_id, float(st.get("unrest") or 0) + float(delta))


# ─── ورودی‌های ناآرامی ───

async def pressure(user_id: int) -> dict:
    """عوامل فعلی فشار اجتماعی (برای نمایش شفاف به بازیکن)."""
    st = await _state(user_id)
    sat = float(st.get("satisfaction") or 0)
    sat_th = await _num("unrest_sat_threshold", DEFAULT_SAT_THRESHOLD)
    parts: dict[str, float] = {}
    if sat < sat_th:
        parts["😞 رضایت پایین"] = min(12.0, (sat_th - sat) * 0.5)
    blackout = sum(float(st.get(k) or 0) for k in ("blackout_power", "blackout_water", "blackout_gas"))
    if blackout > 0:
        parts["⚡ قطعی خدمات"] = min(10.0, blackout * 0.6)
    try:
        from core import attrition as attr
        wear = await attr.wear_of(user_id)
        if wear > 0:
            parts["⛓ فرسایش جنگ"] = min(9.0, wear * 0.1)
    except Exception:
        pass
    try:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM provinces p JOIN countries c2 ON c2.id=p.country_id "
            "JOIN users u ON u.country_id=c2.id WHERE u.id=? AND p.owner_id IS NOT NULL "
            "AND p.owner_id!=?", (user_id, user_id))
        occupied = int((row or {}).get("c") or 0)
        if occupied:
            parts["🗺 استان اشغال‌شده"] = min(8.0, occupied * 2.5)
    except Exception:
        pass
    try:
        from core import grid
        hours = await grid.hours_left(user_id)
        if hours > 0:
            parts["🔌 خاموشی شبکه"] = min(6.0, hours * 0.4)
    except Exception:
        pass
    try:
        from core import market
        infl = await market.inflation(user_id)
        if infl > 5:
            parts["💸 تورم"] = min(6.0, infl * 0.15)
    except Exception:
        pass
    return parts


async def decay_tick(user_id: int) -> dict:
    """تیک هر دوره: فشار جدید + بازیابی خودکار + بررسی شروع اعتصاب/شورش."""
    if not await enabled():
        return {"unrest": 0.0, "strike_started": False}
    st = await _state(user_id)
    cur = float(st.get("unrest") or 0)
    parts = await pressure(user_id)
    rise = sum(parts.values())
    decay = await _num("unrest_decay_per_period", DEFAULT_DECAY)
    new = clamp(cur + rise - (decay if rise <= 0 else 0), 0.0, 100.0)
    # ✊ آغاز اعتصاب سراسری
    strike_started = False
    strike_th = await _num("unrest_strike_threshold", DEFAULT_STRIKE_THRESHOLD)
    if new >= strike_th and not (st.get("strike_until") and str(st["strike_until"]) > iso()):
        minutes = await _num("unrest_strike_minutes", DEFAULT_STRIKE_MIN)
        kind = random.choice(list(STRIKE_NAMES))
        await db.execute(
            "UPDATE states SET strike_until=?, strike_demand=?, unrest=? , unrest_peak=? WHERE user_id=?",
            (add_hours(minutes / 60), DEMANDS[kind], round(new, 1),
             round(max(new, float(st.get("unrest_peak") or 0)), 1), user_id))
        strike_started = True
        await _record(user_id, "strike", new, DEMANDS[kind], minutes / 60)
        try:
            from core.events import log_event
            await log_event("unrest", f"{STRIKE_NAMES[kind]} در کشور یک بازیکن آغاز شد "
                                      f"(ناآرامی {round(new)}٪)")
        except Exception:
            pass
        return {"unrest": round(new, 1), "strike_started": True, "kind": kind,
                "minutes": minutes, "demand": DEMANDS[kind], "parts": parts}
    await db.execute("UPDATE states SET unrest=?, unrest_peak=? WHERE user_id=?",
                     (round(new, 1), round(max(new, float(st.get("unrest_peak") or 0)), 1), user_id))
    return {"unrest": round(new, 1), "strike_started": strike_started, "parts": parts}


async def _record(user_id: int, kind: str, severity: float, demand: str,
                  hours: float) -> None:
    """ثبت رویداد ناآرامی در جدول strikes برای تاریخچه."""
    try:
        await db.execute(
            "INSERT INTO strikes(user_id, kind, severity, demand, started_at, ends_at, status) "
            "VALUES(?,?,?,?,?,?,'active')",
            (user_id, kind, round(float(severity), 1), (demand or "")[:80], iso(),
             add_hours(hours)))
    except Exception:
        log.exception("strike record failed")


async def history(user_id: int, limit: int = 5) -> list[dict]:
    """تاریخچهٔ اعتصاب/جنگ داخلی کشور."""
    try:
        return await db.fetchall(
            "SELECT * FROM strikes WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, int(limit)))
    except Exception:
        return []


# ─── اثرها ───

async def income_multiplier(user_id: int) -> float:
    """ضریب درآمد: اعتصاب سراسری یا جنگ داخلی."""
    if not await enabled():
        return 1.0
    st = await _state(user_id)
    mult = 1.0
    if st.get("strike_until") and str(st["strike_until"]) > iso():
        mult *= await _num("unrest_strike_income_penalty", DEFAULT_STRIKE_INCOME)
    if await revolt_enabled() and st.get("revolt_until") and str(st["revolt_until"]) > iso():
        mult *= await _num("revolt_income_penalty", DEFAULT_REVOLT_INCOME)
    return round(mult, 3)


# ─── اقدام‌های بازیکن ───

async def pay_subsidy(user_id: int, packages: int = 1) -> tuple[bool, str]:
    """🎁 بستهٔ یارانه: با پول، ناآرامی و رضایت را آرام می‌کند."""
    packages = max(1, int(packages))
    cost = int(await _num("unrest_subsidy_cost_m", DEFAULT_SUBSIDY_COST_M) * 1_000_000) * packages
    gain = await _num("unrest_subsidy_step", DEFAULT_SUBSIDY_STEP) * packages
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, f"❌ بودجه کافی نیست — نیاز: {fmt(cost)}"
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    after = await add_unrest(user_id, -gain)
    await db.execute(
        "UPDATE states SET satisfaction=MIN(100, COALESCE(satisfaction,50)+?) WHERE user_id=?",
        (2.0 * packages, user_id))
    # رضایت فوراً بازمحاسبه نمی‌شود؛ اثر یارانه به‌صورت موقت اضافه می‌شود
    return True, (f"🎁 <b>بستهٔ یارانه پرداخت شد.</b>\n"
                  f"💰 هزینه: {fmt(cost)}\n"
                  f"✊ ناآرامی: <b>{after}٪</b> (−{round(gain)})\n"
                  "🙂 رضایت مردم کمی بهتر شد.")


async def crackdown(user_id: int) -> tuple[bool, str]:
    """🪖 سرکوب نظامی: ناآرامی را می‌شکند ولی سرباز و رضایت می‌گیرد."""
    gain = await _num("unrest_crackdown_gain", DEFAULT_CRACKDOWN_GAIN)
    sat_hit = await _num("unrest_crackdown_sat", DEFAULT_CRACKDOWN_SAT)
    loss_pct = await _num("unrest_crackdown_loss_pct", DEFAULT_CRACKDOWN_LOSS)
    row = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
        (user_id,))
    soldiers = int((row or {}).get("c") or 0)
    if soldiers <= 0:
        return False, "❌ برای سرکوب به سرباز نیاز دارید (🎖 پادگان → تعلیم سرباز)."
    lost = max(1, int(soldiers * loss_pct))
    cat = await db.fetchone(
        "SELECT item_id FROM player_assets WHERE user_id=? AND item_type='soldier' AND quantity>0 "
        "ORDER BY quantity DESC LIMIT 1", (user_id,))
    if cat:
        await db.execute(
            "UPDATE player_assets SET quantity=MAX(0, quantity-?) "
            "WHERE user_id=? AND item_type='soldier' AND item_id=?",
            (lost, user_id, cat["item_id"]))
    after = await add_unrest(user_id, -gain)
    await db.execute("UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
                     (sat_hit, user_id))
    try:
        from core.events import log_event
        await log_event("unrest", f"سرکوب نظامی اعتراض‌ها — ناآرامی به {after}٪ رسید")
    except Exception:
        pass
    return True, (f"🪖 <b>سرکوب نظامی انجام شد.</b>\n"
                  f"✊ ناآرامی: <b>{after}٪</b> (−{round(gain)})\n"
                  f"💀 سربازان از دست‌رفته: <b>{fmt(lost)}</b>\n"
                  f"😞 رضایت مردم: −{round(sat_hit)}")


async def ignore(user_id: int) -> tuple[bool, str]:
    """⏳ نادیده‌گرفتن: ارزان، ولی خطرناک."""
    gain = await _num("unrest_ignore_gain", DEFAULT_IGNORE_GAIN)
    sat_hit = await _num("unrest_ignore_sat", DEFAULT_IGNORE_SAT)
    after = await add_unrest(user_id, -gain)
    await db.execute("UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
                     (sat_hit, user_id))
    return True, (f"⏳ <b>اعتراض‌ها نادیده گرفته شد.</b>\n"
                  f"✊ ناآرامی: <b>{after}٪</b> (−{round(gain)})\n"
                  f"😞 رضایت مردم: −{round(sat_hit)}\n"
                  "⚠️ اگر ناآرامی دوباره بالا برود، ممکن است به جنگ داخلی برسد.")


async def negotiate_strike(user_id: int) -> tuple[bool, str]:
    """🤝 مذاکره با معترضان: پایان اعتصاب با قبول خواسته‌ها (هزینهٔ سیاسی)."""
    st = await _state(user_id)
    cost = int(await _num("unrest_subsidy_cost_m", DEFAULT_SUBSIDY_COST_M) * 1_000_000 * 2)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, (f"❌ برای پذیرش خواسته‌ها {fmt(cost)} بودجه لازم است "
                       "(پرداخت معوقات و لغو تصمیم).")
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    await db.execute(
        "UPDATE states SET strike_until=NULL, strike_demand='', unrest=MAX(0, COALESCE(unrest,0)-?) "
        "WHERE user_id=?", (await _num("unrest_subsidy_step", DEFAULT_SUBSIDY_STEP), user_id))
    after = (await get(user_id))["unrest"]
    return True, (f"🤝 <b>اعتصاب پایان یافت.</b>\n"
                  f"💰 هزینهٔ پذیرش خواسته‌ها: {fmt(cost)}\n"
                  f"✊ ناآرامی: <b>{after}٪</b>\n"
                  f"📜 خواستهٔ معترضان پذیرفته شد: {st.get('strike_demand') or '—'}")


async def break_strike(user_id: int) -> tuple[bool, str]:
    """🪖 شکستن اعتصاب: پایان فوری، ولی با هزینهٔ رضایت."""
    sat_hit = await _num("unrest_strike_fail_penalty", DEFAULT_STRIKE_FAIL_PENALTY)
    await db.execute("UPDATE states SET strike_until=NULL, strike_demand='' WHERE user_id=?",
                     (user_id,))
    after = await add_unrest(user_id, -10)
    await db.execute("UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
                     (sat_hit, user_id))
    return True, (f"🪖 <b>اعتصاب با نیروی امنیتی شکسته شد.</b>\n"
                  f"😞 رضایت مردم: −{round(sat_hit)}\n"
                  f"✊ ناآرامی: <b>{after}٪</b>")


# ─── جنگ داخلی ───

async def maybe_start_revolt(bot, user_id: int) -> dict | None:
    """اگر ناآرامی از آستانه بگذرد، جنگ داخلی آغاز می‌شود."""
    if not await revolt_enabled():
        return None
    st = await _state(user_id)
    if st.get("revolt_until") and str(st["revolt_until"]) > iso():
        return None
    th = await _num("revolt_threshold", DEFAULT_REVOLT_THRESHOLD)
    unrest = float(st.get("unrest") or 0)
    if unrest < th:
        return None
    minutes = await _num("revolt_minutes", DEFAULT_REVOLT_MIN)
    await db.execute("UPDATE states SET revolt_until=?, revolt_winner='' WHERE user_id=?",
                     (add_hours(minutes / 60), user_id))
    await _record(user_id, "revolt", unrest, "سرنگونی دولت", minutes / 60)
    country = await db.fetchone(
        "SELECT c.flag, c.name FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (user_id,))
    cname = f"{country['flag']} {country['name']}" if country else "یک کشور"
    try:
        from core.events import log_event
        await log_event("unrest", f"🔥 جنگ داخلی در {cname} آغاز شد (ناآرامی {round(unrest)}٪)")
    except Exception:
        pass
    if bot:
        try:
            from core.economy import announce
            await announce(
                bot,
                f"🔥 <b>جنگ داخلی در {cname}!</b>\n\n"
                f"✊ ناآرامی به <b>{round(unrest)}٪</b> رسید و گروه‌های مسلح بخشی از "
                f"کشور را گرفتند.\n⏳ مهلت مهار: <b>{int(minutes)} دقیقه</b>\n"
                "دولت باید با امتیازدهی، خرید فرماندهان شورشی یا سرکوب، کشور را نگه دارد.",
                section="revolution")
        except Exception:
            pass
        try:
            from gamebot.common import dm
            await dm(bot, user_id,
                     "🔥 <b>جنگ داخلی آغاز شد!</b>\n"
                     f"✊ ناآرامی: {round(unrest)}٪\n"
                     f"⏳ {int(minutes)} دقیقه فرصت دارید از «✊ ناآرامی و اعتصاب» "
                     "وضعیت را مهار کنید.")
        except Exception:
            pass
    return {"started": True, "minutes": minutes, "unrest": round(unrest, 1)}


async def revolt_negotiate(user_id: int) -> tuple[bool, str]:
    """🤝 امتیازدهی به شورشی‌ها (آتش‌بس داخلی)."""
    cost = int(await _num("revolt_negotiate_cost_m", DEFAULT_NEGOTIATE_COST_M) * 1_000_000)
    gain = await _num("revolt_negotiate_gain", DEFAULT_NEGOTIATE_GAIN)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, f"❌ بودجه کافی نیست — نیاز: {fmt(cost)}"
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    await bend_revolt(user_id, gain)
    return True, (f"🤝 <b>امتیازدهی به شورشی‌ها انجام شد.</b>\n"
                  f"💰 هزینه: {fmt(cost)}\n{await revolt_status_line(user_id)}")


async def revolt_bribe(user_id: int) -> tuple[bool, str]:
    """💼 خریدن فرماندهان شورشی."""
    cost = int(await _num("revolt_bribe_cost_m", DEFAULT_BRIBE_COST_M) * 1_000_000)
    chance = await _num("revolt_bribe_chance", DEFAULT_BRIBE_CHANCE)
    gain = await _num("revolt_bribe_gain", DEFAULT_BRIBE_GAIN)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, f"❌ بودجه کافی نیست — نیاز: {fmt(cost)}"
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    if random.random() * 100 >= chance:
        await bend_revolt(user_id, -gain * 0.25)
        return False, (f"❌ <b>نفوذ لو رفت!</b> یکی از فرماندهان شورشی پول را گرفت و "
                       f"افشا کرد (شانس {round(chance)}٪).\n{await revolt_status_line(user_id)}")
    await bend_revolt(user_id, gain)
    return True, (f"💼 <b>خرید فرماندهان شورشی موفق بود.</b>\n"
                  f"💰 هزینه: {fmt(cost)}\n{await revolt_status_line(user_id)}")


async def revolt_crush(user_id: int) -> tuple[bool, str]:
    """🪖 سرکوب نظامی جنگ داخلی (پرهزینه)."""
    loss_pct = await _num("revolt_crush_loss_pct", DEFAULT_CRUSH_LOSS)
    row = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
        (user_id,))
    soldiers = int((row or {}).get("c") or 0)
    if soldiers <= 0:
        return False, "❌ برای سرکوب شورشی‌ها سرباز لازم است."
    lost = max(1, int(soldiers * loss_pct))
    cat = await db.fetchone(
        "SELECT item_id FROM player_assets WHERE user_id=? AND item_type='soldier' AND quantity>0 "
        "ORDER BY quantity DESC LIMIT 1", (user_id,))
    if cat:
        await db.execute(
            "UPDATE player_assets SET quantity=MAX(0, quantity-?) "
            "WHERE user_id=? AND item_type='soldier' AND item_id=?",
            (lost, user_id, cat["item_id"]))
    await db.execute("UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-8) WHERE user_id=?",
                     (user_id,))
    # سرکوب نظامی همیشه شدت را کم می‌کند ولی کشور را فرسوده می‌سازد
    await bend_revolt(user_id, 45)
    try:
        from core.events import log_event
        await log_event("unrest", "ارتش شورش داخلی را سرکوب کرد "
                                  f"({fmt(lost)} سرباز از دست رفت)")
    except Exception:
        pass
    return True, (f"🪖 <b>ارتش شورش را در هم شکست.</b>\n"
                  f"💀 سربازان ازدست‌رفته: <b>{fmt(lost)}</b>\n"
                  f"😞 رضایت: −۸\n{await revolt_status_line(user_id)}")


async def bend_revolt(user_id: int, delta: float) -> float:
    """کاهش شدت جنگ داخلی؛ اگر به زیر ۳۰ رسید، شورش مهار می‌شود."""
    st = await _state(user_id)
    if not (st.get("revolt_until") and str(st["revolt_until"]) > iso()):
        return float(st.get("unrest") or 0)
    after = await add_unrest(user_id, -abs(delta))
    if after <= 30:
        await db.execute("UPDATE states SET revolt_until=NULL WHERE user_id=?", (user_id,))
        await db.execute("UPDATE states SET unrest=?, unrest_peak=? WHERE user_id=?",
                         (round(min(after, 30), 1), 30.0, user_id))
    return after


async def revolt_status_line(user_id: int) -> str:
    info = await get(user_id)
    if not info["revolt_active"]:
        return "✅ جنگ داخلی مهار شد — حاکمیت کشور حفظ شد."
    return (f"🔥 شدت جنگ داخلی: <b>{round(info['unrest'])}٪</b> | "
            f"⏳ {info['revolt_left']} مانده")


async def revolt_tick(bot) -> int:
    """تیک جنگ داخلی: مهلت تمام‌شده → شورای انقلابی کشور را می‌گیرد."""
    if not await revolt_enabled():
        return 0
    rows = await db.fetchall(
        "SELECT s.user_id, s.revolt_until, s.unrest FROM states s "
        "WHERE s.revolt_until IS NOT NULL AND s.revolt_until!='' AND s.revolt_until<=?", (iso(),))
    done = 0
    for r in rows:
        user_id = int(r["user_id"])
        await _revolt_succeeds(bot, user_id)
        done += 1
    return done


async def _revolt_succeeds(bot, user_id: int) -> None:
    """اثر شکست دولت در جنگ داخلی: تغییر حاکمیت + غارت، ولی کشور سقوط نمی‌کند."""
    country = await db.fetchone(
        "SELECT c.* FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?", (user_id,))
    share = await _num("revolt_rival_share", DEFAULT_RIVAL_SHARE)
    money_pct = await _num("revolt_rival_money_pct", DEFAULT_RIVAL_MONEY)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    stolen = int(int((user or {}).get("money") or 0) * money_pct)
    if stolen:
        await db.execute("UPDATE users SET money=MAX(0, money-?) WHERE id=?", (stolen, user_id))
    # دارایی‌ها: سهمی از تجهیزات/سربازان به شورشی‌ها می‌رسد (از بین می‌رود)
    try:
        await db.execute(
            "UPDATE player_assets SET quantity=MAX(0, CAST(quantity * ? AS INTEGER)) "
            "WHERE user_id=?", (1.0 - share, user_id))
    except Exception:
        log.exception("revolt asset share failed")
    if country:
        try:
            from core.politics import set_leader
            await set_leader(country["id"], "شورای انقلابی موقت", "شورا")
        except Exception:
            pass
    await db.execute(
        "UPDATE states SET revolt_until=NULL, revolt_winner='rival', unrest=55, unrest_peak=100, "
        "satisfaction=MAX(0, COALESCE(satisfaction,50)-15) WHERE user_id=?", (user_id,))
    try:
        from core.events import log_event
        await log_event("unrest", f"جنگ داخلی در {country['name'] if country else user_id} "
                                  "با پیروزی شورشی‌ها پایان یافت")
    except Exception:
        pass
    if bot and country:
        try:
            from core.economy import announce
            await announce(
                bot,
                f"🔥 <b>جنگ داخلی پایان یافت — شورشی‌ها پیروز شدند</b>\n\n"
                f"دولت {country['flag']} <b>{country['name']}</b> نتوانست شورش را مهار کند و "
                f"«شورای انقلابی» قدرت را گرفت.\n"
                f"💸 غارت خزانه: {fmt(stolen)} | 🪖 کاهش {round(share * 100)}٪ دارایی نظامی\n"
                "کشور سقوط نکرد؛ فرمانده باید کشور را بازسازی کند.",
                section="revolution")
        except Exception:
            pass
        try:
            from gamebot.common import dm
            await dm(bot, user_id,
                     "🔥 <b>شورشی‌ها پیروز شدند!</b>\n"
                     f"💸 {fmt(stolen)} از خزانه غارت شد و {round(share * 100)}٪ تجهیزات از دست رفت.\n"
                     "«شورای انقلابی» رهبری کشور را گرفت. برای تعیین رهبر جدید از "
                     "«🏛 رهبری و انقلاب» استفاده کنید.")
        except Exception:
            pass


# ─── نمایش ───

async def unrest_text(user_id: int) -> str:
    """متن کامل وضعیت ناآرامی برای منوی بازیکن."""
    info = await get(user_id)
    parts = await pressure(user_id)
    mult = await income_multiplier(user_id)
    lines = ["✊ <b>ناآرامی، اعتصاب و جنگ داخلی</b>", ""]
    filled = max(0, min(10, int(round(info["unrest"] / 10))))
    lines.append(f"📊 ناآرامی مردم: <b>{info['unrest']}٪</b> "
                 + "█" * filled + "░" * (10 - filled))
    lines.append(f"🚨 آستانهٔ اعتصاب: {round(info['strike_threshold'])}٪ | "
                 f"🔥 آستانهٔ جنگ داخلی: {round(info['revolt_threshold'])}٪")
    if parts:
        lines.append("\n📈 <b>عوامل فشار:</b>")
        for k, v in parts.items():
            lines.append(f"  • {k}: +{round(v, 1)}")
    if info["strike_active"]:
        lines.append(f"\n✊ <b>اعتصاب سراسری فعال است</b> ({info['strike_left']} مانده)")
        lines.append(f"   📜 خواستهٔ معترضان: {info['strike_demand'] or '—'}")
        lines.append("   ⚠️ اعتصاب درآمد کشور را نصف کرده و شرکت‌ها تعطیل‌اند.")
    if info["revolt_active"]:
        lines.append(f"\n🔥 <b>جنگ داخلی جریان دارد</b> — {info['revolt_left']} مانده")
        lines.append("   شدت شورش: " + f"<b>{round(info['unrest'])}٪</b>")
    if mult < 1.0:
        lines.append(f"\n💸 ضریب درآمد فعلی: <b>×{mult}</b>")
    hist = await history(user_id, 4)
    if hist:
        lines.append("\n🗂 <b>تاریخچهٔ اخیر ناآرامی:</b>")
        for h in hist:
            kind = "✊ اعتصاب" if h["kind"] == "strike" else "🔥 جنگ داخلی"
            lines.append(f"  • {kind} — شدت {round(float(h['severity'] or 0))}٪ "
                         f"({str(h['started_at'] or '')[:16]})")
    lines.append("\n💡 ناآرامی با رضایت بالا، خدمات پایدار و پایان جنگ پایین می‌آید.")
    return "\n".join(lines)

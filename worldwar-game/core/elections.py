"""🗳 انتخابات دوره‌ای، احزاب و کمپین انتخاباتی.

واقعیت: دولت‌ها با رأی مردم می‌آیند و می‌روند؛ حزب حاکم سیاست‌های کشور را
تعیین می‌کند و کمپین تبلیغاتی پول می‌خواهد.

مکانیک:
  • هر `election_interval_hours` ساعت، برای هر کشور انتخابات دوره‌ای برگزار می‌شود
    (اگر کشور در انقلاب/جنگ داخلی نباشد).
  • حزب حاکم از میان چهار گرایش انتخاب می‌شود: 🪖 نظامی، 🏭 صنعتی، 🎁 رفاهی، 🕌 مذهبی.
    هر حزب یک بونوس مشخص می‌دهد (حمله/درآمد/رضایت).
  • شانس پیروزی اپوزیسیون از رضایت و ناآرامی کشور می‌آید
    (`election_opposition_threshold`)؛ اگر اپوزیسیون ببرد، رهبر و حزب عوض می‌شوند.
  • بازیکن با پول **کمپین** می‌خرد (`election_bonus_step` به ازای هر رأی تبلیغاتی)
    تا حزب خودش بماند؛ ولی کمپین گران است و به ناآرامی دامن می‌زند.
همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting, set_setting
from core.utils import add_hours, clamp, fmt, fmt_hm, hours_left, iso

log = logging.getLogger(__name__)

PARTIES = {
    "military": ("🪖 حزب نظامیان", "بونوس قدرت حمله و پدافند — سیاست سخت‌گیرانه", "attack", 12.0),
    "industry": ("🏭 حزب صنعتگران", "بونوس درآمد و تولید — سیاست اقتصادی", "income", 10.0),
    "welfare": ("🎁 حزب رفاه", "بونوس رضایت مردم — سیاست رفاهی", "satisfaction", 6.0),
    "clergy": ("🕌 حزب مذهبی", "بونوس رضایت و پایهٔ اجتماعی — سیاست محافظه‌کار", "satisfaction", 4.0),
}
PARTY_KEYS = list(PARTIES)
DEFAULT_INTERVAL = 48.0
DEFAULT_COST_M = 25.0
DEFAULT_STEP = 0.35
DEFAULT_THRESHOLD = 55.0
DEFAULT_INCOME_BONUS = 0.05


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
        return await get_setting("sec_elections", "1") == "1"
    except Exception:
        return True


# ─── حزب ───

async def party_of(user_id: int) -> dict:
    """حزب فعلی کشور بازیکن (اگر نداشته باشد، اولین بار تعیین می‌شود)."""
    row = await db.fetchone(
        "SELECT p.* FROM party_state p WHERE p.user_id=?", (user_id,))
    if row:
        key = row.get("party") or "industry"
        meta = PARTIES.get(key, PARTIES["industry"])
        return {"key": key, "title": meta[0], "desc": meta[1], "effect": meta[2],
                "bonus": meta[3], "campaign": int(row.get("campaign") or 0),
                "support": round(float(row.get("support") or 50), 1),
                "next_at": row.get("next_at") or "",
                "terms": int(row.get("terms") or 0)}
    key = random.choice(PARTY_KEYS)
    interval = await _num("election_interval_hours", DEFAULT_INTERVAL)
    await db.execute(
        "INSERT INTO party_state(user_id, party, support, campaign, next_at, terms, updated_at) "
        "VALUES(?,?,?,?,?,0,?)",
        (user_id, key, 50.0, 0, add_hours(interval), iso()))
    meta = PARTIES[key]
    return {"key": key, "title": meta[0], "desc": meta[1], "effect": meta[2],
            "bonus": meta[3], "campaign": 0, "support": 50.0,
            "next_at": add_hours(interval), "terms": 0}


async def income_bonus(user_id: int) -> float:
    """بونوس درآمد حزب صنعتگران + پاداش عمومی حزب حاکم."""
    if not await enabled():
        return 0.0
    p = await party_of(user_id)
    bonus = float(await _num("election_party_income_bonus", DEFAULT_INCOME_BONUS))
    if p["key"] == "industry":
        bonus += p["bonus"] / 100 / 2
    return round(bonus, 3)


async def attack_bonus(user_id: int) -> float:
    if not await enabled():
        return 0.0
    p = await party_of(user_id)
    if p["key"] == "military":
        return round(p["bonus"] / 100 / 2, 3)
    return 0.0


async def satisfaction_bonus(user_id: int) -> float:
    if not await enabled():
        return 0.0
    p = await party_of(user_id)
    if p["effect"] == "satisfaction":
        return round(p["bonus"] * 0.5, 1)
    return 0.0


# ─── کمپین ───

async def campaign(user_id: int, votes: int = 1) -> tuple[bool, str]:
    """📣 خرید رأی تبلیغاتی برای ماندن حزب در قدرت."""
    votes = max(1, min(20, int(votes)))
    cost = int(await _num("election_campaign_cost_m", DEFAULT_COST_M) * 1_000_000) * votes
    step = await _num("election_bonus_step", DEFAULT_STEP)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, f"❌ بودجهٔ کمپین کافی نیست — نیاز: {fmt(cost)}"
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    p = await party_of(user_id)
    new_campaign = min(20, p["campaign"] + votes)
    await db.execute(
        "UPDATE party_state SET campaign=?, support=MIN(95, COALESCE(support,50)+?) WHERE user_id=?",
        (new_campaign, step * votes, user_id))
    try:
        from core import unrest as unrest_mod
        await unrest_mod.add_unrest(user_id, 1.5)   # تبلیغات پرهزینه، کمی نارضایتی می‌آورد
    except Exception:
        pass
    return True, (f"📣 <b>کمپین انتخاباتی.</b>\n"
                  f"💰 هزینه: {fmt(cost)}\n"
                  f"🎯 رأی تبلیغاتی: +{votes} (مجموع {new_campaign}) — "
                  f"پشتیبانی <b>+{round(step * votes, 1)}٪</b>")


# ─── برگزاری ───

async def _eligible(user_id: int) -> tuple[bool, str]:
    try:
        from core import politics, unrest
        if await politics.active_revolution(user_id):
            return False, "انقلاب فعال است — انتخابات فوری جایگزین آن است."
        info = await unrest.get(user_id)
        if info["revolt_active"]:
            return False, "جنگ داخلی فعال است — انتخابات در کشور اختلال دارد."
    except Exception:
        pass
    return True, ""


async def run_one(user_id: int, bot=None) -> dict | None:
    """برگزاری انتخابات یک کشور. خروجی: نتیجه یا None."""
    if not await enabled():
        return None
    p = await party_of(user_id)
    ok, _why = await _eligible(user_id)
    if not ok:
        return None
    country = await db.fetchone(
        "SELECT c.flag, c.name FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (user_id,))
    if not country:
        return None
    st = await db.fetchone("SELECT satisfaction FROM states WHERE user_id=?", (user_id,)) or {}
    sat = float(st.get("satisfaction") or 50)
    threshold = await _num("election_opposition_threshold", DEFAULT_THRESHOLD)
    campaign = p["campaign"]
    # آستانهٔ مؤثر: رضایت بالا آن را بالا می‌برد، کمپین هم کمک می‌کند
    effective = clamp(threshold + (50 - sat) * 0.6 - campaign * 1.5, 10.0, 95.0)
    opposition_win = random.random() * 100 < effective
    interval = await _num("election_interval_hours", DEFAULT_INTERVAL)
    changed = False
    if opposition_win:
        old_key = p["key"]
        new_key = random.choice([k for k in PARTY_KEYS if k != old_key] or PARTY_KEYS)
        await db.execute(
            "UPDATE party_state SET party=?, campaign=0, support=?, next_at=?, terms=terms+1, "
            "updated_at=? WHERE user_id=?",
            (new_key, 55.0, add_hours(interval), iso(), user_id))
        changed = True
        try:
            from core.politics import set_leader
            from core.seed import LEADER_POOL
            country_row = await db.fetchone(
                "SELECT c.id FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
                (user_id,))
            if country_row:
                await set_leader(country_row["id"], random.choice(list(LEADER_POOL)))
        except Exception:
            pass
        try:
            from core import unrest as unrest_mod
            await unrest_mod.add_unrest(user_id, 6)
        except Exception:
            pass
    else:
        await db.execute(
            "UPDATE party_state SET campaign=0, support=MIN(95, COALESCE(support,50)+4), "
            "next_at=?, terms=terms+1, updated_at=? WHERE user_id=?",
            (add_hours(interval), iso(), user_id))
    result = {
        "country": f"{country['flag']} {country['name']}",
        "opposition": opposition_win, "winner": (await party_of(user_id)),
        "turnout": round(random.uniform(45, 85), 1),
        "effective_threshold": round(effective, 1),
        "user_id": user_id, "changed": changed,
    }
    try:
        from core.events import log_event
        winner = result["winner"]["title"]
        await log_event("politics", f"🗳 انتخابات {country['name']} — حزب پیروز: {winner}")
    except Exception:
        pass
    if bot:
        title = ("🗳 <b>تغییر قدرت در انتخابات</b>" if changed else "🗳 <b>انتخابات دوره‌ای</b>")
        line = (f"{title}\n\n🏳 {country['flag']} <b>{country['name']}</b>\n"
                f"🏆 حزب حاکم جدید: {result['winner']['title']}\n"
                f"📊 مشارکت: {result['turnout']}٪\n"
                f"🧭 {result['winner']['desc']}")
        try:
            from gamebot.common import dm
            await dm(bot, user_id, line)
        except Exception:
            pass
        if changed:
            try:
                from core.economy import announce
                await announce(bot, line, section="politics")
            except Exception:
                pass
    return result


async def tick(bot) -> int:
    """بررسی همهٔ کشورهایی که وقت انتخاباتشان رسیده است."""
    if not await enabled():
        return 0
    rows = await db.fetchall(
        "SELECT p.user_id FROM party_state p WHERE p.next_at IS NOT NULL AND p.next_at!='' "
        "AND p.next_at<=?", (iso(),))
    done = 0
    for r in rows:
        try:
            if await run_one(int(r["user_id"]), bot):
                done += 1
        except Exception:
            log.exception("election tick failed")
    return done


async def elections_text(user_id: int) -> str:
    p = await party_of(user_id)
    interval = await _num("election_interval_hours", DEFAULT_INTERVAL)
    cost = int(await _num("election_campaign_cost_m", DEFAULT_COST_M) * 1_000_000)
    st = await db.fetchone("SELECT satisfaction, unrest FROM states WHERE user_id=?",
                           (user_id,)) or {}
    sat = float(st.get("satisfaction") or 50)
    threshold = await _num("election_opposition_threshold", DEFAULT_THRESHOLD)
    effective = clamp(threshold + (50 - sat) * 0.6 - p["campaign"] * 1.5, 10.0, 95.0)
    lines = ["🗳 <b>انتخابات و حزب حاکم</b>", "",
             f"🏆 حزب حاکم: <b>{p['title']}</b>",
             f"🧭 {p['desc']}",
             f"📣 رأی تبلیغاتی فعلی: <b>{p['campaign']}</b> | پشتیبانی: <b>{p['support']}٪</b>",
             f"📅 انتخابات بعدی: {fmt_hm(hours_left(p['next_at']))} دیگر "
             f"(هر {int(interval)} ساعت)",
             f"⚠️ شانس پیروزی اپوزیسیون در انتخابات بعدی: <b>{round(effective)}٪</b>",
             f"💰 هزینهٔ هر رأی تبلیغاتی: {fmt(cost)}",
             "",
             "🏛 <b>احزاب:</b>"]
    for key, (title, desc, _e, bonus) in PARTIES.items():
        lines.append(f"  • {title}: {desc} (+{bonus:g})")
    lines.append("\n💡 رضایت بالا شانس اپوزیسیون را کم می‌کند؛ کمپین هم کمک می‌کند ولی گران است.")
    return "\n".join(lines)

"""🍁 فصل‌ها و آب‌وهوا — ژنرال زمستان، خشکسالی و موسمی.

واقعیت: تاریخ جنگ‌ها را آب‌وهوا عوض کرده است: زمستان روسیه، موسمی ویتنام،
خشکسالی و قحطی. فصل‌ها باید در تصمیم بازیکن اثر بگذارند، نه فقط در تزئین.

مکانیک (جدول `season_weather` — یک ردیف برای «فصل فعلی بازی»):
  • هر `weather_season_hours` ساعت، فصل عوض می‌شود: بهار → تابستان → پاییز → زمستان.
  • ❄️ زمستان: مصرف انرژی کشور بالا (`weather_winter_energy_pct`) و عملیات حمله
    کند (`weather_winter_attack_pct`).
  • ☀️ تابستان: احتمال خشکسالی (`weather_drought_chance`) → افت آب و رضایت.
  • 🍂 پاییز: احتمال طوفان (`weather_storm_chance`) → کندی حمله؛ و بونوس برداشت
    (`weather_harvest_bonus_m`) در دورهٔ درآمد.
  • 🌱 بهار: رشد جمعیت/بازسازی فرسایش کمی سریع‌تر.
همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting, set_setting
from core.utils import add_hours, fmt, hours_left, iso

log = logging.getLogger(__name__)

SEASONS = ["spring", "summer", "autumn", "winter"]
SEASON_INFO = {
    "spring": ("🌱", "بهار", "فصل بازسازی و رشد؛ ارتش‌ها تازه‌نفس می‌شوند."),
    "summer": ("☀️", "تابستان", "گرما و مصرف آب؛ خطر خشکسالی و قحطی."),
    "autumn": ("🍂", "پاییز", "فصل برداشت؛ طوفان‌ها عملیات را کند می‌کنند."),
    "winter": ("❄️", "زمستان", "سرما، مصرف بالای انرژی و کندی عملیات نظامی."),
}
DEFAULT_SEASON_HOURS = 24.0


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
        return await get_setting("sec_weather", "1") == "1"
    except Exception:
        return True


async def current() -> dict:
    """فصل فعلی بازی + زمان شروع/پایان و وضعیت خشکسالی."""
    row = await db.fetchone("SELECT * FROM season_weather ORDER BY id DESC LIMIT 1")
    if not row:
        return await rotate(force=True)
    return row


async def rotate(force: bool = False) -> dict:
    """چرخش فصل: اگر زمانش رسیده (یا force) فصل بعدی ثبت می‌شود."""
    hours_needed = await _num("weather_season_hours", DEFAULT_SEASON_HOURS)
    row = await db.fetchone("SELECT * FROM season_weather ORDER BY id DESC LIMIT 1")
    if row and not force:
        # هنوز وقتش نشده؟
        try:
            from core.utils import parse, now
            started = parse(row.get("started_at"))
            if started and (now() - started).total_seconds() / 3600 < hours_needed:
                return row
        except Exception:
            return row
    idx = int((row or {}).get("season_index") or 0)
    season = SEASONS[(idx + 1) % 4] if row else "spring"
    new_idx = (idx + 1) if row else 0
    await db.execute(
        "INSERT INTO season_weather(season_index, season, started_at, ends_at) VALUES(?,?,?,?)",
        (new_idx, season, iso(), add_hours(hours_needed)))
    await set_setting("current_season", season)
    fresh = await db.fetchone("SELECT * FROM season_weather ORDER BY id DESC LIMIT 1")
    return fresh or {"season": season, "season_index": new_idx}


async def tick(bot=None) -> dict:
    """تیک فصل‌ها (در حلقهٔ آرام)."""
    if not await enabled():
        return {"season": "off"}
    before = await db.fetchone("SELECT * FROM season_weather ORDER BY id DESC LIMIT 1")
    after = await rotate()
    changed = bool(before) and (before.get("season") != after.get("season"))
    if changed and bot:
        emoji, name, desc = SEASON_INFO.get(after.get("season"), ("🍁", "فصل", ""))
        try:
            from core.economy import announce_news
            lines = [f"{emoji} <b>فصل {name}</b> آغاز شد.", desc]
            if after.get("season") == "winter":
                lines.append(f"❄️ مصرف انرژی +{round(await _num('weather_winter_energy_pct', 18))}٪ و "
                             f"عملیات حمله {round(await _num('weather_winter_attack_pct', 12))}٪ کندتر.")
            if after.get("season") == "summer":
                lines.append(f"☀️ خطر خشکسالی: {round(await _num('weather_drought_chance', 20))}٪")
            if after.get("season") == "autumn":
                lines.append(f"🌾 بونوس برداشت: {fmt(int(await _num('weather_harvest_bonus_m', 25) * 1_000_000))}")
            await announce_news(bot, f"{emoji} تغییر فصل در جهان", lines, section="general")
        except Exception:
            pass
    return {"season": after.get("season"), "changed": changed}


async def season_key() -> str:
    row = await current()
    return str(row.get("season") or "spring")


async def season_line() -> str:
    row = await current()
    emoji, name, desc = SEASON_INFO.get(row.get("season"), ("🍁", "—", ""))
    left = hours_left(row.get("ends_at"))
    drought = " | ☀️ خشکسالی فعال" if await is_drought() else ""
    storm = " | 🌪 طوفان فعال" if await is_storm() else ""
    return f"{emoji} <b>فصل {name}</b> — {round(left, 1)} ساعت مانده{drought}{storm}"


# ─── اثرها ───

async def check_drought() -> bool:
    """تابستان: شانس خشکسالی این فصل (یک‌بار در هر فصل)."""
    row = await current()
    if row.get("season") != "summer":
        return False
    if row.get("drought"):
        return True
    chance = await _num("weather_drought_chance", 20)
    if random.random() * 100 >= chance:
        await db.execute("UPDATE season_weather SET drought=1 WHERE id=?", (row["id"],))
        return False
    await db.execute("UPDATE season_weather SET drought=1 WHERE id=?", (row["id"],))
    return True


async def is_drought() -> bool:
    row = await current()
    return bool(row.get("drought")) and row.get("season") == "summer"


async def is_storm() -> bool:
    row = await current()
    return bool(row.get("storm")) and row.get("season") == "autumn"


async def roll_storm() -> bool:
    row = await current()
    if row.get("season") != "autumn":
        return False
    chance = await _num("weather_storm_chance", 15)
    if random.random() * 100 < chance:
        await db.execute("UPDATE season_weather SET storm=1 WHERE id=?", (row["id"],))
        return True
    return False


async def attack_multiplier() -> float:
    """کندی عملیات نظامی در زمستان/طوفان."""
    if not await enabled():
        return 1.0
    mult = 1.0
    if await season_key() == "winter":
        mult *= 1.0 - await _num("weather_winter_attack_pct", 12) / 100
    if await is_storm():
        mult *= 1.0 - await _num("weather_storm_attack_pct", 10) / 100
    return round(mult, 3)


async def energy_extra_pct() -> float:
    """مصرف بیشتر انرژی در زمستان."""
    if not await enabled():
        return 0.0
    if await season_key() != "winter":
        return 0.0
    return await _num("weather_winter_energy_pct", 18)


async def water_penalty_pct() -> float:
    """افت آب تولیدی در تابستان/خشکسالی."""
    if not await enabled():
        return 0.0
    pct = await _num("weather_summer_water_pct", 15)
    if await season_key() == "summer":
        return pct
    return 0.0


async def income_bonus(user_id: int) -> int:
    """بونوس برداشت پاییز (به پول) — یک‌بار در هر دورهٔ درآمد."""
    if not await enabled():
        return 0
    if await season_key() != "autumn":
        return 0
    bonus = int(await _num("weather_harvest_bonus_m", 25) * 1_000_000)
    try:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM player_assets a JOIN buildings b ON b.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='building' AND b.sector='food'", (user_id,))
        farms = int((row or {}).get("c") or 0)
    except Exception:
        farms = 0
    return bonus if farms > 0 else int(bonus * 0.3)


async def tick_country(user_id: int) -> list[str]:
    """اثر فصل روی یک کشور در هر دوره (آب/رضایت)."""
    lines: list[str] = []
    if not await enabled():
        return lines
    if await is_drought():
        try:
            await db.execute(
                "UPDATE states SET water=MAX(0, CAST(water*0.85 AS INTEGER)) WHERE user_id=?",
                (user_id,))
            await db.execute(
                "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-1) WHERE user_id=?",
                (user_id,))
            lines.append("☀️ خشکسالی: ۱۵٪ ذخایر آب تبخیر شد و رضایت کمی افت کرد.")
        except Exception:
            log.exception("drought tick failed")
    extra = await energy_extra_pct()
    if extra:
        try:
            await db.execute(
                "UPDATE states SET energy=MAX(0, CAST(energy * ? AS INTEGER)) WHERE user_id=?",
                (1.0 - extra / 100, user_id))
            lines.append(f"❄️ سرمای زمستان: {round(extra)}٪ انرژی بیشتری مصرف شد.")
        except Exception:
            pass
    return lines

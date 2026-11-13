"""⚡ حملهٔ سایبری با اثر آبشاری — از شبکهٔ برق تا پمپ آب و بیمارستان.

واقعیت: حمله به شبکهٔ برق فقط لامپ‌ها را خاموش نمی‌کند؛ پمپ‌های آب، سردخانهٔ
دارو، خطوط تولید و مخابرات هم می‌خوابند. تعمیرش زمان و پول می‌خواهد.

مکانیک: هر خرابکاری موفق در «⚡ نیروگاه برق» (یا 🌐 اینترنت) یک **قطعی واقعی**
می‌سازد (`states.blackout_power` ساعت‌ها بالا می‌رود و `grid_until` ثبت می‌شود):
  • درآمد کشور به ازای هر ساعت قطعی `grid_income_penalty_pct`٪ کم می‌شود.
  • رضایت مردم هر ساعت افت می‌کند و ناآرامی بالا می‌رود (به `core/unrest.py` وصل است).
  • بازیکن می‌تواند با هزینهٔ «ترمیم اضطراری» ساعت‌ها را کم کند.
همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging

from core.db import db, get_setting
from core.utils import add_hours, fmt, hours_left, iso

log = logging.getLogger(__name__)

DEFAULT_HOURS_PER_SUCCESS = 6.0
DEFAULT_MAX_HOURS = 24.0
DEFAULT_INCOME_PCT = 6.0
DEFAULT_REPAIR_M = 12.0
DEFAULT_SAT_HIT = 1.2


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
        return await get_setting("sec_grideffect", "1") == "1"
    except Exception:
        return True


async def strike(user_id: int, kind: str = "power") -> dict:
    """اعمال یک قطعی آبشاری پس از خرابکاری موفق در شبکه."""
    if not await enabled():
        return {"hours": 0}
    per = await _num("grid_hours_per_success", DEFAULT_HOURS_PER_SUCCESS)
    if kind == "internet":
        per = per * 0.5
    await add_hours_to_grid(user_id, per)
    hours = await hours_left(user_id)
    sat = await _num("grid_satisfaction_hit", DEFAULT_SAT_HIT)
    await db.execute(
        "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
        (round(sat * per / 2, 1), user_id))
    try:
        from core import unrest as unrest_mod
        await unrest_mod.add_unrest(user_id, min(8.0, per * 0.6))
    except Exception:
        pass
    label = "⚡ شبکهٔ برق" if kind != "internet" else "🌐 زیرساخت اینترنت"
    return {"hours": round(hours, 1), "label": label,
            "line": (f"⚡ <b>اثر آبشاری:</b> {label} از کار افتاد — "
                     f"<b>{round(hours, 1)} ساعت</b> خاموشی (پمپ آب، صنعت و بیمارستان‌ها "
                     "هم آسیب دیدند).")}


async def add_hours_to_grid(user_id: int, hours: float) -> float:
    """افزودن ساعت خاموشی به وضعیت کشور (سقف‌دار)."""
    cap = await _num("grid_max_hours", DEFAULT_MAX_HOURS)
    st = await db.fetchone("SELECT blackout_power FROM states WHERE user_id=?", (user_id,)) or {}
    current = float(st.get("blackout_power") or 0)
    new = min(cap, current + float(hours))
    await db.execute("UPDATE states SET blackout_power=? WHERE user_id=?", (new, user_id))
    return new


async def hours_left(user_id: int) -> float:
    """ساعت خاموشی باقی‌مانده (تخمینی از ستون blackout_power)."""
    row = await db.fetchone("SELECT blackout_power FROM states WHERE user_id=?", (user_id,))
    return round(max(0.0, float((row or {}).get("blackout_power") or 0)), 1)


async def income_multiplier(user_id: int) -> float:
    """افت درآمد به ازای هر ساعت خاموشی."""
    if not await enabled():
        return 1.0
    hours = await hours_left(user_id)
    if hours <= 0:
        return 1.0
    pct = await _num("grid_income_penalty_pct", DEFAULT_INCOME_PCT) / 100
    return round(max(0.25, 1.0 - hours * pct), 3)


async def decay_tick(user_id: int) -> float:
    """کاهش تدریجی ساعت خاموشی با گذشت زمان (تعمیر خودکار)."""
    hours = await hours_left(user_id)
    if hours <= 0:
        return 0.0
    new = max(0.0, hours - 1.0)
    await db.execute("UPDATE states SET blackout_power=? WHERE user_id=?", (new, user_id))
    return new


async def repair(user_id: int) -> tuple[bool, str]:
    """🔧 ترمیم اضطراری شبکه با پول (کاهش ساعت خاموشی)."""
    hours = await hours_left(user_id)
    if hours <= 0:
        return False, "✅ شبکهٔ برق شما سالم است؛ خاموشی‌ای وجود ندارد."
    per_hour = int(await _num("grid_repair_cost_m", DEFAULT_REPAIR_M) * 1_000_000)
    cost = int(per_hour * hours)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, (f"❌ ترمیم اضطراری {round(hours, 1)} ساعت خاموشی "
                       f"{fmt(cost)} می‌خواهد (بودجه: {fmt(money)}).")
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    await db.execute("UPDATE states SET blackout_power=0 WHERE user_id=?", (user_id,))
    await db.execute(
        "UPDATE states SET satisfaction=MIN(100, COALESCE(satisfaction,50)+2) WHERE user_id=?",
        (user_id,))
    return True, (f"🔧 <b>شبکه ترمیم شد.</b>\n"
                  f"⚡ {round(hours, 1)} ساعت خاموشی برطرف شد.\n"
                  f"💰 هزینه: {fmt(cost)}")


async def grid_line(user_id: int) -> str:
    hours = await hours_left(user_id)
    if hours <= 0:
        return ""
    mult = await income_multiplier(user_id)
    return (f"⚡ <b>خاموشی شبکه:</b> {hours} ساعت مانده "
            f"(درآمد ×{mult}، پمپ آب و صنعت مختل)")

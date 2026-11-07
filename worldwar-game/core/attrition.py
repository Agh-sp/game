"""⚔️ جنگ فرسایشی و نابودی واقعی کشورها.

به‌درخواست کاربر، حملات باید **اثر تجمعی واقعی** داشته باشند تا با چند حملهٔ
پشت‌سرهم (هر ۳ دقیقه) بتوان یک کشور را به زانو درآورد — مثل جنگ واقعی.

مکانیک اصلی: **فرسایش تجمعی** (`wear`) که در جدول `country_attrition` ذخیره
می‌شود. هر حملهٔ موفق درصدی به آن اضافه می‌کند و اثرش به‌صورت زنجیره‌ای:

| اثر | فرمول |
|---|---|
| 🛡 ضعف پدافند | توان دفاعی مدافع × (۱ − wear×0.6) |
| 😞 ریزش روحیه | رضایت مردم − (پایه + wear×ضریب) در هر حمله |
| 🏭 افت تولید | درآمد مدافع × (۱ − wear) |
| 💀 تلفات بیشتر | تلفات تجهیزات و سرباز مدافع × (۱ + wear) |
| 🗺 تصرف آسان‌تر | شانس دفاع استان × (۱ − wear×0.7) |

`wear` هر ۶ ساعت به‌اندازهٔ ۲۵٪ آب می‌رود (کشور خودش را بازسازی می‌کند) و با
**صلح/تسخیر** صفر می‌شود. همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging

from core.db import db, get_setting
from core.utils import iso

log = logging.getLogger(__name__)

DEFAULT_MAX_WEAR = 90.0        # سقف فرسایش (٪)
DEFAULT_PER_STRIKE = 12.0      # فرسایش اضافه‌شده به ازای هر حملهٔ موفق
DEFAULT_DECAY_PER_HOUR = 6.0   # آب‌رفتن فرسایش در هر ساعت (٪)


async def _num(key: str, default: float) -> float:
    try:
        raw = await get_setting(key, "")
    except Exception:
        return default
    try:
        return float(str(raw).strip()) if str(raw).strip() else default
    except (TypeError, ValueError):
        return default


async def get(user_id: int) -> dict:
    """وضعیت فرسایش یک کشور: {"wear": 0..max, "strikes": n, "last_at": ...}"""
    row = await db.fetchone(
        "SELECT * FROM country_attrition WHERE user_id=?", (user_id,))
    if not row:
        return {"user_id": user_id, "wear": 0.0, "strikes": 0, "last_at": None,
                "recovering": 0}
    wear = float(row.get("wear") or 0)
    # ⏳ بازیابی تدریجی: هر ساعت مقداری از فرسایش کم می‌شود
    decay_per_hour = await _num("attrition_decay_per_hour", DEFAULT_DECAY_PER_HOUR)
    try:
        from core.utils import parse, now
        then = parse(row.get("last_at"))
        if then and wear > 0 and decay_per_hour > 0:
            hours = max(0.0, (now() - then).total_seconds() / 3600)
            wear = max(0.0, wear - hours * decay_per_hour)
    except Exception:
        pass
    return {"user_id": user_id, "wear": round(wear, 1),
            "strikes": int(row.get("strikes") or 0),
            "last_at": row.get("last_at"),
            "recovering": int(row.get("recovering") or 0)}


async def wear_of(user_id: int) -> float:
    return float((await get(user_id))["wear"])


async def add_strike(user_id: int, attacker_id: int, amount: float | None = None) -> dict:
    """⛓ ثبت یک حملهٔ موفق و افزایش فرسایش کشور مدافع."""
    st = await get(user_id)
    max_wear = await _num("attrition_max_wear", DEFAULT_MAX_WEAR)
    per = await _num("attrition_per_strike", DEFAULT_PER_STRIKE)
    gain = per if amount is None else float(amount)
    wear = min(max_wear, st["wear"] + gain)
    await db.execute(
        "INSERT INTO country_attrition(user_id, wear, strikes, last_at, last_attacker) "
        "VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET wear=excluded.wear, "
        "strikes=excluded.strikes, last_at=excluded.last_at, "
        "last_attacker=excluded.last_attacker",
        (user_id, wear, st["strikes"] + 1, iso(), attacker_id))
    return {"wear": round(wear, 1), "strikes": st["strikes"] + 1,
            "gain": round(wear - st["wear"], 1)}


async def reset(user_id: int) -> None:
    """♻️ پاک‌کردن فرسایش (صلح، تسخیر کامل یا ریست ادمین)."""
    try:
        await db.execute("DELETE FROM country_attrition WHERE user_id=?", (user_id,))
    except Exception:
        log.exception("attrition reset failed")


async def defense_multiplier(user_id: int) -> float:
    """🛡 ضریب توان دفاعی: کشور فرسوده کمتر مقاومت می‌کند (حداقل ۳۵٪ توان)."""
    wear = await wear_of(user_id)
    ratio = await _num("attrition_defense_penalty", 0.6)
    return round(max(0.35, 1.0 - (wear / 100.0) * ratio), 3)


async def income_multiplier(user_id: int) -> float:
    """🏭 افت تولید اقتصاد فرسوده (حداقل ۱۵٪)."""
    wear = await wear_of(user_id)
    ratio = await _num("attrition_income_penalty", 1.0)
    return round(max(0.15, 1.0 - (wear / 100.0) * ratio), 3)


async def loss_multiplier(user_id: int) -> float:
    """💀 تلفات بیشتر برای کشور فرسوده (تا ۲ برابر)."""
    wear = await wear_of(user_id)
    return round(1.0 + (wear / 100.0), 3)


async def satisfaction_hit(user_id: int) -> float:
    """😞 ریزش روحیهٔ تجمعی در هر حملهٔ موفق."""
    wear = await wear_of(user_id)
    base = await _num("attrition_morale_base", 3.0)
    per_wear = await _num("attrition_morale_per_wear", 0.12)
    return round(base + wear * per_wear, 2)


async def province_defense_multiplier(user_id: int) -> float:
    """🗺 شانس دفاع استان برای کشور فرسوده کمتر می‌شود (حداقل ۲۰٪)."""
    wear = await wear_of(user_id)
    return round(max(0.2, 1.0 - (wear / 100.0) * 0.7), 3)


async def apply_after_attack(attacker_id: int, defender_id: int, won: bool) -> dict:
    """پس از هر نبرد: فرسایش، روحیه و گزارش متنی.

    خروجی: {"wear", "strikes", "gain", "morale", "lines": [..]}
    """
    if not won:
        # حملهٔ ناموفق هم کمی مدافع را خسته می‌کند (اثر فرسایشی نبرد)
        partial = await _num("attrition_failed_strike_share", 0.35)
        per = await _num("attrition_per_strike", DEFAULT_PER_STRIKE)
        st = await add_strike(defender_id, attacker_id, per * partial)
    else:
        st = await add_strike(defender_id, attacker_id)
    lines: list[str] = []
    if st["gain"] > 0:
        lines.append(f"⛓ <b>فرسایش دشمن:</b> +{st['gain']}٪ (مجموع "
                     f"<b>{st['wear']}٪</b> — {st['strikes']} حملهٔ ثبت‌شده)")
    if won:
        hit = await satisfaction_hit(defender_id)
        if hit > 0:
            await db.execute(
                "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) "
                "WHERE user_id=?", (hit, defender_id))
            lines.append(f"😞 <b>ریزش روحیه:</b> رضایت مردم دشمن −{hit}٪ "
                         "(اثر تجمعی جنگ فرسایشی)")
    return {**st, "lines": lines}


async def wear_line(user_id: int) -> str:
    """📊 خط وضعیت فرسایش برای نمایش به بازیکن."""
    st = await get(user_id)
    if st["wear"] <= 0:
        return ""
    d = await defense_multiplier(user_id)
    i = await income_multiplier(user_id)
    p = await province_defense_multiplier(user_id)
    return (f"⛓ <b>فرسایش جنگ:</b> <b>{st['wear']}٪</b> "
            f"({st['strikes']} حمله)\n"
            f"   🛡 توان دفاعی ×{d} | 🏭 درآمد ×{i} | 🗺 دفاع استان ×{p}\n"
            "   💡 هر ۶ ساعت خودبه‌خود بازیابی می‌شود؛ صلح آن را صفر می‌کند.")


async def collapse_check(user_id: int) -> bool:
    """💀 آیا کشور از فرسایش کامل به زانو درآمده است؟"""
    max_wear = await _num("attrition_max_wear", DEFAULT_MAX_WEAR)
    threshold = await _num("attrition_collapse_threshold", 85.0)
    threshold = min(max_wear, threshold)
    st = await get(user_id)
    return st["wear"] >= threshold

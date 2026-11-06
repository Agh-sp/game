"""موتور درآمد دوره‌ای بازی — سه منبع مستقل و همیشه فعال.

منابع (هر `income_interval_minutes` دقیقه، پیش‌فرض ۵ دقیقه):

1. 💰 **مالیات مردم** — پایه ۱۰ میلیون + ضریب اقتصاد کشور
   (چین/آمریکا/روسیه چند برابر یونان/افغانستان) × رضایت × نرخ مالیات × ضریب ارتقا
2. 🛢 **فروش نفت** — `oil_income_base` هر کشور (میلیون) × سطح تجهیزات × ضریب ارتقا
   برخلاف گذشته **بدون نیاز به دکل** به‌صورت خودکار پرداخت می‌شود.
3. ⚓ **عوارض تنگه‌ها** — مالک هر تنگه مبلغ ثابت ۱۴ میلیون × ضریب ارتقا
   (برخلاف گذشته مستقل از تجارت دیگران است).

ضریب ارتقا (`growth_multiplier`) از پیشرفت واقعی بازیکن می‌آید تا کشورهای ضعیف
بتوانند با بازی درست به ابرقدرت تبدیل شوند (سقف ۳ برابر):

- پروژه‌های کامل‌شدهٔ اقتصادی/علمی → هر کدام +۸٪
- سطح تجهیزات استخراج نفت (بالاتر از ۱) → هر سطح +۶٪
- سطح شرکت‌ها → هر سطح +۴٪
- رضایت بالای ۵۰٪ → تا +۲۰٪
- تعداد استان‌های تحت کنترل (بیش از ۵) → هر استان +۵٪

همهٔ اعداد از پنل ادمین قابل تغییرند (کلیدهای `income_*`).
"""
from __future__ import annotations

import logging

from core.db import db, get_setting
from core.utils import fmt_money

log = logging.getLogger(__name__)

# ─── پیش‌فرض‌ها (همه از پنل ادمین قابل تغییر) ───
DEFAULT_TAX_BASE_M = 10.0        # میلیون — پایهٔ مالیات برای ضریب ۱
DEFAULT_TAX_STEP_M = 8.0         # میلیون — به ازای هر واحد ضریب اقتصاد کشور
DEFAULT_OIL_UNIT_M = 1.0         # میلیون — ضریب تبدیل oil_income_base به پول
DEFAULT_STRAIT_M = 14.0          # میلیون — هر تنگه برای مالکش
DEFAULT_GROWTH_CAP = 3.0         # سقف ضریب ارتقا

# ضرایب ارتقا
PROJECT_BONUS = 0.08
RIG_BONUS = 0.06
COMPANY_BONUS = 0.04
SATISFACTION_BONUS = 0.20
PROVINCE_BONUS = 0.05


async def _num_setting(key: str, default: float) -> float:
    """خواندن تنظیم عددی با مقاومت در برابر مقدار خالی/خراب."""
    try:
        raw = await get_setting(key, "")
    except Exception:
        return default
    try:
        return float(str(raw).strip()) if str(raw).strip() else default
    except (TypeError, ValueError):
        return default


async def get_minutes() -> int:
    """فاصلهٔ پرداخت به دقیقه (حداقل ۱)."""
    try:
        minutes = int(float(await get_setting("income_interval_minutes", "5") or 5))
    except (TypeError, ValueError):
        minutes = 5
    return max(1, minutes)


async def growth_multiplier(user_id: int) -> dict:
    """ضریب ارتقای درآمد بازیکن + جزئیات برای نمایش به بازیکن.

    خروجی: {mult, base_mult, project, rig, company, satisfaction, province, cap}
    """
    cap = await _num_setting("income_growth_cap", DEFAULT_GROWTH_CAP)
    details = {"mult": 1.0, "project": 0.0, "rig": 0.0, "company": 0.0,
               "satisfaction": 0.0, "province": 0.0, "cap": cap}

    # ۱) پروژه‌های کامل‌شدهٔ زیرساختی/علمی (نه نظامی)
    try:
        rows = await db.fetchall(
            "SELECT COUNT(*) c FROM player_projects p "
            "JOIN buildings b ON b.id=p.building_id "
            "WHERE p.user_id=? AND p.status='done' "
            "AND (b.sector IN ('science','power','water','gas','food','health','housing','fun') "
            "     OR b.name LIKE '%نیروگاه%' OR b.name LIKE '%کارخانه%' "
            "     OR b.name LIKE '%بندر%' OR b.name LIKE '%فرودگاه%')",
            (user_id,))
        count = int((rows[0]["c"] if rows else 0) or 0)
        details["project"] = count * PROJECT_BONUS
    except Exception:
        pass

    # ۲) سطح تجهیزات استخراج نفت بالاتر از ۱
    try:
        row = await db.fetchone("SELECT level FROM oil_business WHERE user_id=?", (user_id,))
        level = int((row or {}).get("level") or 1)
        details["rig"] = max(0, level - 1) * RIG_BONUS
    except Exception:
        pass

    # ۳) شرکت‌های اقتصادی (هر شرکت فعال +۴٪)
    try:
        rows = await db.fetchall(
            "SELECT COUNT(*) c FROM companies WHERE owner_id=?", (user_id,))
        count = int((rows[0]["c"] if rows else 0) or 0)
        details["company"] = count * COMPANY_BONUS
    except Exception:
        pass

    # ۴) رضایت بالای ۵۰٪
    try:
        row = await db.fetchone("SELECT satisfaction FROM states WHERE user_id=?", (user_id,))
        sat = float((row or {}).get("satisfaction") or 0)
        if sat > 50:
            details["satisfaction"] = min(1.0, (sat - 50) / 50) * SATISFACTION_BONUS
    except Exception:
        pass

    # ۵) استان‌های اضافه (بیش از ۵ استان پایه)
    try:
        row = await db.fetchone(
            "SELECT COALESCE(SUM(province_count),0) s FROM provinces WHERE owner_id=?",
            (user_id,))
        owned = int((row or {}).get("s") or 5) or 5
        details["province"] = max(0, owned - 5) * PROVINCE_BONUS
    except Exception:
        pass

    raw = 1.0 + sum(v for k, v in details.items() if k not in ("mult", "cap"))
    details["mult"] = round(min(cap, raw), 3)
    return details


async def tax_income(user_id: int, growth: float = 1.0) -> dict:
    """💰 درآمد مالیات مردم برای یک دوره."""
    base = await _num_setting("income_tax_base_m", DEFAULT_TAX_BASE_M)
    step = await _num_setting("income_tax_step_m", DEFAULT_TAX_STEP_M)
    row = await db.fetchone(
        "SELECT c.gdp_factor, s.satisfaction, s.tax_rate FROM countries c "
        "JOIN users u ON u.country_id=c.id "
        "LEFT JOIN states s ON s.user_id=u.id WHERE u.id=?", (user_id,))
    if not row:
        return {"amount": 0, "gdp": 1.0, "sat_mult": 1.0, "tax_mult": 1.0, "base": base}
    gdp = float(row["gdp_factor"] or 1)
    sat = 50.0 if row["satisfaction"] is None else float(row["satisfaction"])
    tax = float(row["tax_rate"] or 0)

    base_part = base + max(0.0, gdp - 1.0) * step
    sat_mult = 0.5 + sat / 100          # ۰٪ → ۰٫۵ | ۱۰۰٪ → ۱٫۵
    tax_mult = 1 + tax                  # ۰٪ → ۱ | ۵۰٪ → ۱٫۵
    amount = int(base_part * 1_000_000 * sat_mult * tax_mult * growth)
    return {"amount": amount, "gdp": gdp, "sat_mult": round(sat_mult, 2),
            "tax_mult": round(tax_mult, 2), "base": base_part}


async def oil_income(user_id: int, growth: float = 1.0) -> dict:
    """🛢 درآمد فروش نفت برای یک دوره (خودکار، بدون نیاز به دکل)."""
    unit = await _num_setting("income_oil_unit_m", DEFAULT_OIL_UNIT_M)
    row = await db.fetchone(
        "SELECT c.oil_income_base FROM countries c JOIN users u ON u.country_id=c.id "
        "WHERE u.id=?", (user_id,))
    base_m = int((row or {}).get("oil_income_base") or 2)
    level_mult = 1.0
    try:
        r = await db.fetchone("SELECT level FROM oil_business WHERE user_id=?", (user_id,))
        level = int((r or {}).get("level") or 1)
        level_mult = 1.0 + max(0, level - 1) * 0.15
    except Exception:
        pass
    amount = int(base_m * unit * 1_000_000 * level_mult * growth)
    return {"amount": amount, "base_m": base_m, "level_mult": round(level_mult, 2)}


async def strait_income(user_id: int, growth: float = 1.0) -> dict:
    """⚓ عوارض تنگه‌ها برای مالک (مبلغ ثابت برای هر تنگه)."""
    per = await _num_setting("income_strait_m", DEFAULT_STRAIT_M)
    if await get_setting("sec_straits", "1") != "1":
        return {"amount": 0, "count": 0, "per_m": per}
    try:
        rows = await db.fetchall(
            "SELECT s.id FROM straits s JOIN countries c ON c.owner_id=s.owner_id "
            "WHERE s.is_active=1 AND s.owner_id=? AND c.has_sea=1", (user_id,))
        count = len(rows)
    except Exception:
        return {"amount": 0, "count": 0, "per_m": per}
    amount = int(count * per * 1_000_000 * growth)
    return {"amount": amount, "count": count, "per_m": per}


async def income_sources(user_id: int) -> dict:
    """برآورد کامل هر سه منبع برای یک دوره (برای نمایش به بازیکن)."""
    growth = await growth_multiplier(user_id)
    mult = growth["mult"]
    tax = await tax_income(user_id, mult)
    oil = await oil_income(user_id, mult)
    strait = await strait_income(user_id, mult)
    return {
        "minutes": await get_minutes(),
        "growth": growth,
        "tax": tax,
        "oil": oil,
        "strait": strait,
        "total": tax["amount"] + oil["amount"] + strait["amount"],
    }


async def income_summary_text(user_id: int) -> str:
    """متن خلاصهٔ درآمد برای نمایش در «امپراطوری من»."""
    src = await income_sources(user_id)
    g = src["growth"]
    lines = [
        f"💵 <b>درآمد هر {src['minutes']} دقیقه: {fmt_money(src['total'])}</b>",
        f"  • 💰 مالیات مردم: <b>{fmt_money(src['tax']['amount'])}</b>",
        f"  • 🛢 فروش نفت: <b>{fmt_money(src['oil']['amount'])}</b>",
        f"  • ⚓ عوارض تنگه‌ها: <b>{fmt_money(src['strait']['amount'])}</b> "
        f"({src['strait']['count']} تنگه)",
        f"  📈 ضریب ارتقا: <b>×{g['mult']}</b> (سقف ×{g['cap']})",
    ]
    bonuses = [("پروژه‌ها", g["project"]), ("تجهیزات نفت", g["rig"]),
               ("شرکت‌ها", g["company"]), ("رضایت", g["satisfaction"]),
               ("استان‌ها", g["province"])]
    active = [f"{n} +{round(v * 100)}٪" for n, v in bonuses if v > 0]
    if active:
        lines.append("  🔧 " + " • ".join(active))
    elif g["mult"] < g["cap"]:
        lines.append("  🔧 برای افزایش درآمد، پروژه/شرکت/تجهیزات نفت را ارتقا بده "
                     f"(تا ×{g['cap']})")
    return "\n".join(lines)

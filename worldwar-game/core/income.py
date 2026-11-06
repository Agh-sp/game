"""موتور درآمد دوره‌ای بازی — سه منبع مستقل و همیشه فعال.

منابع (هر `income_interval_minutes` دقیقه، پیش‌فرض ۵ دقیقه):

1. 💰 **مالیات مردم** — پایه ۱۰ میلیون + ضریب اقتصاد کشور
   (چین/آمریکا/روسیه چند برابر یونان/افغانستان) × رضایت × نرخ مالیات × ضریب ارتقا
2. 🛢 **فروش نفت** — `oil_income_base` هر کشور (میلیون) × سطح تجهیزات × ضریب ارتقا
   برخلاف گذشته **بدون نیاز به دکل** به‌صورت خودکار پرداخت می‌شود.
3. ⚓ **عوارض تنگه‌ها** — مالک هر تنگه مبلغ ثابت ۱۴ میلیون × ضریب ارتقا
   (برخلاف گذشته مستقل از تجارت دیگران است).

📈 **رشد با ارتقا** — هر چیزی که بازیکن می‌سازد یا ارتقا می‌دهد درآمدش را بالا می‌برد
تا کشور ضعیف با تلاش به ابرقدرت تبدیل شود (سقف پیش‌فرض ×۵):

- 🛢 **هر دکل نفتی: +۸٪** (اصلی‌ترین محرک — دکل بیشتر، درآمد نفتی بیشتر)
- 🔥 هر دکل گازی: +۴٪
- 🏗 هر ساختمان ساخته‌شده: +۲٪
- 🏢 هر شرکت اقتصادی: +۴٪
- 🛠 هر سطح تجهیزات استخراج: +۶٪
- 🙂 رضایت بالای ۵۰٪: تا +۲۰٪
- 🗺 هر استان اضافه: +۵٪
- 🧬 هر مرحلهٔ غنی‌سازی: +۵٪
- 🏗️ هر پروژهٔ کامل‌شده: +۳٪

درآمد نفت جداگانه هم با تعداد دکل به‌صورت خطی زیاد می‌شود
(`oil_rig_bonus_percent` درصد به ازای هر دکل).

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
DEFAULT_OIL_FLOOR_M = 12.0       # میلیون — کف پایهٔ درآمد نفتی هر دوره
DEFAULT_STRAIT_M = 14.0          # میلیون — هر تنگه برای مالکش
DEFAULT_GROWTH_CAP = 5.0         # سقف ضریب ارتقا
DEFAULT_RIG_BONUS_PCT = 8.0      # درصد افزایش درآمد نفت به ازای هر دکل نفتی

# ضرایب ارتقا (هر کدام از پنل ادمین قابل تغییر)
OIL_RIG_BONUS = 0.08             # 🛢 هر دکل نفتی
GAS_RIG_BONUS = 0.04             # 🔥 هر دکل گازی
BUILDING_BONUS = 0.02            # 🏗 هر ساختمان ساخته‌شده
COMPANY_BONUS = 0.04             # 🏢 هر شرکت
RIG_LEVEL_BONUS = 0.06           # 🛠 هر سطح تجهیزات استخراج
SATISFACTION_BONUS = 0.20        # 🙂 رضایت بالای ۵۰٪
PROVINCE_BONUS = 0.05            # 🗺 هر استان اضافه
ENRICHMENT_BONUS = 0.05          # 🧬 هر مرحلهٔ غنی‌سازی
PROJECT_BONUS = 0.03             # 🏗️ هر پروژهٔ کامل‌شده


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


async def asset_counts(user_id: int) -> dict:
    """شمارش دارای‌های بازیکن که درآمد را بالا می‌برند."""
    out = {"rigs": 0, "gas_rigs": 0, "buildings": 0, "companies": 0,
           "oil_level": 1, "enrich_stage": 0}
    # 🛢 دکل نفتی و 🔥 دکل گازی
    try:
        rows = await db.fetchall(
            "SELECT b.name AS name, COALESCE(SUM(a.quantity),0) q FROM player_assets a "
            "JOIN buildings b ON b.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='building' GROUP BY b.name", (user_id,))
        for r in rows:
            name = r["name"] or ""
            qty = int(r["q"] or 0)
            if "دکل نفتی" in name:
                out["rigs"] += qty
            elif "دکل" in name or "گاز" in name:
                out["gas_rigs"] += qty
            out["buildings"] += qty
    except Exception:
        pass
    # 🏢 شرکت‌ها
    try:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM companies WHERE owner_id=?", (user_id,))
        out["companies"] = int((row or {}).get("c") or 0)
    except Exception:
        pass
    # 🛠 سطح تجهیزات استخراج
    try:
        row = await db.fetchone("SELECT level FROM oil_business WHERE user_id=?", (user_id,))
        out["oil_level"] = int((row or {}).get("level") or 1)
    except Exception:
        pass
    # 🧬 مرحلهٔ غنی‌سازی
    try:
        row = await db.fetchone("SELECT stage FROM enrichment WHERE user_id=?", (user_id,))
        out["enrich_stage"] = int((row or {}).get("stage") or 0)
    except Exception:
        pass
    return out


async def growth_multiplier(user_id: int) -> dict:
    """ضریب ارتقای درآمد بازیکن + جزئیات برای نمایش.

    هر چه بازیکن بیشتر بسازد و ارتقا بدهد، درآمدش بیشتر می‌شود.
    خروجی: {"mult", "rigs", "gas_rigs", "buildings", "company", "oil_level",
             "satisfaction", "province", "enrichment", "cap", "capped"}
    """
    cap = await _num_setting("income_growth_cap", DEFAULT_GROWTH_CAP)
    counts = await asset_counts(user_id)
    details: dict = {
        "mult": 1.0, "cap": cap, "capped": False,
        "rigs": 0.0, "gas_rigs": 0.0, "buildings": 0.0, "company": 0.0,
        "oil_level": 0.0, "satisfaction": 0.0, "province": 0.0, "enrichment": 0.0,
        "project": 0.0, "n_projects": 0,
        "n_rigs": counts["rigs"], "n_gas_rigs": counts["gas_rigs"],
        "n_buildings": counts["buildings"], "n_companies": counts["companies"],
        "n_oil_level": counts["oil_level"],
    }

    # 🛢 دکل نفتی — مهم‌ترین محرک
    details["rigs"] = counts["rigs"] * OIL_RIG_BONUS
    # 🔥 دکل گازی
    details["gas_rigs"] = counts["gas_rigs"] * GAS_RIG_BONUS
    # 🏗 ساختمان‌ها (بدون دکل‌ها که جدا حساب شدند)
    plain_buildings = max(0, counts["buildings"] - counts["rigs"] - counts["gas_rigs"])
    details["buildings"] = plain_buildings * BUILDING_BONUS
    # 🏢 شرکت‌ها
    details["company"] = counts["companies"] * COMPANY_BONUS
    # 🛠 سطح تجهیزات استخراج
    details["oil_level"] = max(0, counts["oil_level"] - 1) * RIG_LEVEL_BONUS
    # 🙂 رضایت
    try:
        row = await db.fetchone("SELECT satisfaction FROM states WHERE user_id=?", (user_id,))
        sat = float((row or {}).get("satisfaction") or 0)
        if sat > 50:
            details["satisfaction"] = min(1.0, (sat - 50) / 50) * SATISFACTION_BONUS
    except Exception:
        pass
    # 🗺 استان‌های اضافه
    try:
        row = await db.fetchone(
            "SELECT COALESCE(SUM(province_count),0) s FROM provinces WHERE owner_id=?",
            (user_id,))
        owned = int((row or {}).get("s") or 5) or 5
        details["province"] = max(0, owned - 5) * PROVINCE_BONUS
    except Exception:
        pass
    # 🧬 غنی‌سازی
    details["enrichment"] = counts["enrich_stage"] * ENRICHMENT_BONUS
    # 🏗️ پروژه‌های کامل‌شده
    try:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM player_projects WHERE user_id=? AND status='done'",
            (user_id,))
        done = int((row or {}).get("c") or 0)
        details["project"] = done * PROJECT_BONUS
        details["n_projects"] = done
    except Exception:
        details["project"] = 0.0
        details["n_projects"] = 0

    raw = 1.0 + sum(v for k, v in details.items()
                    if k not in ("mult", "cap", "capped") and not k.startswith("n_"))
    details["mult"] = round(min(cap, raw), 3)
    details["capped"] = raw > cap
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
    """🛢 درآمد فروش نفت برای یک دوره.

    **تعداد دکل نفتی مستقیماً درآمد را زیاد می‌کند**:
        درآمد = پایهٔ نفتی کشور × (۱ + دکل‌ها × oil_rig_bonus_percent٪)
                × سطح تجهیزات × ضریب ارتقا

    با صفر دکل هم پایهٔ کشور پرداخت می‌شود (پیش‌فرض قبلی حفظ شده)، ولی
    هر دکل اضافه سود را چند برابر می‌کند.
    """
    unit = await _num_setting("income_oil_unit_m", DEFAULT_OIL_UNIT_M)
    bonus_pct = await _num_setting("oil_rig_bonus_percent", DEFAULT_RIG_BONUS_PCT)
    floor_m = await _num_setting("income_oil_floor_m", DEFAULT_OIL_FLOOR_M)
    level_bonus = await _num_setting("oil_level_income_bonus", 0.12)
    row = await db.fetchone(
        "SELECT c.oil_income_base FROM countries c JOIN users u ON u.country_id=c.id "
        "WHERE u.id=?", (user_id,))
    base_m = int((row or {}).get("oil_income_base") or 2)

    counts = await asset_counts(user_id)
    rigs = counts["rigs"]
    rig_mult = 1.0 + rigs * (bonus_pct / 100)

    # 🛠 هر سطح تجهیزات استخراج، درآمد نفتی را هم بالاتر می‌برد
    level_mult = 1.0 + max(0, counts["oil_level"] - 1) * level_bonus

    # پایهٔ هر کشور دست‌کم `income_oil_floor_m` میلیون است تا درآمد نفتی همیشه
    # در بازهٔ میلیونی بماند (نه چند صد هزار).
    eff_base = max(base_m * unit, floor_m)
    amount = int(eff_base * 1_000_000 * rig_mult * level_mult * growth)
    return {"amount": amount, "base_m": base_m, "eff_base_m": round(eff_base, 2),
            "rigs": rigs, "rig_mult": round(rig_mult, 2),
            "level_mult": round(level_mult, 2), "bonus_pct": bonus_pct}


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


async def income_breakdown_lines(user_id: int) -> list[str]:
    """خطوط کامل توضیح درآمد (برای نمایش در امپراطوری و بخش درآمد)."""
    src = await income_sources(user_id)
    g = src["growth"]
    oil = src["oil"]
    lines = [
        f"💵 <b>درآمد هر {src['minutes']} دقیقه: {fmt_money(src['total'])}</b>",
        f"  • 💰 مالیات مردم: <b>{fmt_money(src['tax']['amount'])}</b>",
        f"  • 🛢 درآمد نفت: <b>{fmt_money(oil['amount'])}</b>",
        f"     └ پایه {oil['eff_base_m']:g}M × {oil['rigs']} دکل (×{oil['rig_mult']}) "
        f"× سطح تجهیزات (×{oil['level_mult']})",
        f"  • ⚓ عوارض تنگه‌ها: <b>{fmt_money(src['strait']['amount'])}</b> "
        f"({src['strait']['count']} تنگه)",
        f"  📈 ضریب کل ارتقا: <b>×{g['mult']}</b>"
        + (f" (سقف ×{g['cap']} رسیده)" if g.get("capped") else f" از سقف ×{g['cap']}"),
    ]
    parts = []
    if g["rigs"]:
        parts.append(f"🛢 {g['n_rigs']} دکل نفتی +{round(g['rigs'] * 100)}٪")
    if g["gas_rigs"]:
        parts.append(f"🔥 {g['n_gas_rigs']} دکل گازی +{round(g['gas_rigs'] * 100)}٪")
    if g["buildings"]:
        parts.append(f"🏗 {g['n_buildings']} ساختمان +{round(g['buildings'] * 100)}٪")
    if g["company"]:
        parts.append(f"🏢 {g['n_companies']} شرکت +{round(g['company'] * 100)}٪")
    if g["oil_level"]:
        parts.append(f"🛠 تجهیزات سطح {g['n_oil_level']} +{round(g['oil_level'] * 100)}٪")
    if g["satisfaction"]:
        parts.append(f"🙂 رضایت +{round(g['satisfaction'] * 100)}٪")
    if g["province"]:
        parts.append(f"🗺 استان‌ها +{round(g['province'] * 100)}٪")
    if g["enrichment"]:
        parts.append(f"🧬 غنی‌سازی +{round(g['enrichment'] * 100)}٪")
    if g.get("project"):
        parts.append(f"🏗️ {g['n_projects']} پروژه +{round(g['project'] * 100)}٪")
    if parts:
        lines.append("  🔧 " + " • ".join(parts))
    elif g["mult"] < g["cap"]:
        lines.append("  🔧 برای افزایش درآمد، 🛢 دکل نفتی بساز یا چیزها را ارتقا بده "
                     f"(تا ×{g['cap']})")
    return lines


async def income_summary_text(user_id: int) -> str:
    """متن خلاصهٔ درآمد برای نمایش در «امپراطوری من»."""
    return "\n".join(await income_breakdown_lines(user_id))

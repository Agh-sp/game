"""🌐 رفاه اینترنت — زیرساخت دیجیتال کشور.

بازیکن در بخش «🎁 رفاه» می‌تواند زیرساخت اینترنت کشورش را ارتقا بدهد.
هر سطح یک نوع زیرساخت است و سه اثر واقعی دارد:

- 🙂 **رضایت مردم**: پوشش اینترنت به رضایت اضافه می‌کند
  (`internet_satisfaction_bonus` درصد به ازای هر سطح).
- 📈 **اقتصاد دیجیتال**: ضریب ارتقای درآمد را بالا می‌برد
  (`internet_growth_bonus` درصد به ازای هر سطح) — روی مالیات، نفت،
  عوارض تنگه و فروش منابع اثر می‌گذارد.
- 🌐 **پوشش اینترنت** (درصد) که در صفحه نمایش داده می‌شود.

هزینهٔ هر ارتقا از پنل ادمین قابل تغییر است (`internet_upgrade_cost`,
`internet_materials_per_level`). جدول: `internet_infra`.
"""
from __future__ import annotations

import logging

from core.db import db, get_setting
from core.utils import fmt, fmt_money

log = logging.getLogger(__name__)

# سطح → (نام زیرساخت، ایموجی، پوشش ٪)
LEVELS = {
    1: ("اینترنت پرسرعت شهری", "📶", 25),
    2: ("فیبر نوری سراسری", "🔌", 45),
    3: ("شبکه نسل پنجم (5G)", "📡", 65),
    4: ("دیتاسنتر ملی و ابری", "🖥", 82),
    5: ("اینترنت ماهواره‌ای سراسری", "🛰", 97),
}

DEFAULT_MAX_LEVEL = 5


async def _setting_num(key: str, default: float) -> float:
    try:
        raw = await get_setting(key, "")
    except Exception:
        return default
    try:
        return float(str(raw).strip()) if str(raw).strip() else default
    except (TypeError, ValueError):
        return default


async def max_level() -> int:
    return max(1, min(5, int(await _setting_num("internet_max_level", DEFAULT_MAX_LEVEL))))


async def get_level(user_id: int) -> int:
    """سطح زیرساخت اینترنت کشور (۰ = هنوز چیزی ساخته نشده)."""
    try:
        row = await db.fetchone(
            "SELECT level FROM internet_infra WHERE user_id=?", (user_id,))
        return max(0, int((row or {}).get("level") or 0))
    except Exception:
        return 0


async def set_level(user_id: int, level: int) -> int:
    level = max(0, min(await max_level(), int(level)))
    await db.execute(
        "INSERT INTO internet_infra(user_id, level, updated_at) VALUES(?,?,datetime('now')) "
        "ON CONFLICT(user_id) DO UPDATE SET level=excluded.level, "
        "updated_at=excluded.updated_at", (user_id, level))
    return level


def level_info(level: int) -> dict:
    """اطلاعات نمایشی یک سطح (برای سطح ۰ هم مقدار امن برمی‌گرداند)."""
    if level <= 0:
        return {"level": 0, "name": "بدون زیرساخت اینترنت", "emoji": "🚫", "coverage": 0}
    name, emoji, coverage = LEVELS.get(min(5, level), LEVELS[5])
    return {"level": level, "name": name, "emoji": emoji, "coverage": coverage}


def coverage(level: int) -> int:
    return int(level_info(level)["coverage"])


async def growth_bonus(user_id: int) -> float:
    """📈 سهم ضریب ارتقای درآمد از اینترنت (مثلاً ۵٪ به ازای هر سطح)."""
    pct = await _setting_num("internet_growth_bonus", 5.0)
    return await get_level(user_id) * pct / 100.0


async def satisfaction_bonus(user_id: int) -> float:
    """🙂 امتیاز رضایت از پوشش اینترنت."""
    per = await _setting_num("internet_satisfaction_bonus", 2.0)
    return await get_level(user_id) * per


async def upgrade_cost(user_id: int) -> tuple[int, int]:
    """(هزینهٔ پولی، مصالح لازم) برای ارتقا به سطح بعدی."""
    level = await get_level(user_id)
    base = await _setting_num("internet_upgrade_cost", 80_000_000)
    mats = await _setting_num("internet_materials_per_level", 250)
    step = 1.6 ** max(0, level)          # هر سطح گران‌تر
    return int(base * step), int(mats * step)


async def upgrade(user_id: int) -> tuple[bool, str]:
    """🌐 ارتقای زیرساخت اینترنت یک سطح."""
    level = await get_level(user_id)
    top = await max_level()
    if level >= top:
        return False, (f"🌐 زیرساخت اینترنت شما در بالاترین سطح ({top}) است — "
                       "پوشش کشور کامل است.")
    cost, mats = await upgrade_cost(user_id)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    st = await db.fetchone("SELECT COALESCE(materials,0) m FROM states WHERE user_id=?",
                           (user_id,))
    have_mats = int((st or {}).get("m") or 0)
    if money < cost:
        return False, (f"❌ بودجهٔ کافی ندارید.\n💰 نیاز: <b>{fmt_money(cost)}</b> — "
                       f"خزانه: {fmt_money(money)}")
    if have_mats < mats:
        return False, (f"❌ مصالح کافی ندارید.\n🧱 نیاز: <b>{fmt(mats)}</b> واحد — "
                       f"موجودی: {fmt(have_mats)}")
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    await db.execute("UPDATE states SET materials=MAX(0, COALESCE(materials,0)-?) "
                     "WHERE user_id=?", (mats, user_id))
    new_level = await set_level(user_id, level + 1)
    try:
        from core.economy import satisfaction_recompute
        await satisfaction_recompute(user_id)
    except Exception:
        log.exception("satisfaction_recompute بعد از ارتقای اینترنت شکست خورد")
    info = level_info(new_level)
    return True, (f"✅ زیرساخت اینترنت کشور به سطح <b>{new_level}</b> ارتقا یافت!\n\n"
                  f"{info['emoji']} <b>{info['name']}</b>\n"
                  f"🌐 پوشش اینترنت: <b>{info['coverage']}%</b>\n"
                  f"💰 هزینه: {fmt_money(cost)} | 🧱 مصالح: {fmt(mats)}\n\n"
                  "این ارتقا رضایت مردم و ضریب درآمد کشور را بالا برد.")


async def internet_text(user_id: int) -> str:
    """متن کامل صفحهٔ رفاه اینترنت."""
    level = await get_level(user_id)
    top = await max_level()
    info = level_info(level)
    nxt = level_info(min(top, level + 1))
    sat_bonus = await satisfaction_bonus(user_id)
    growth = await growth_bonus(user_id)
    per_sat = await _setting_num("internet_satisfaction_bonus", 2.0)
    per_growth = await _setting_num("internet_growth_bonus", 5.0)
    cost, mats = await upgrade_cost(user_id) if level < top else (0, 0)

    lines = [
        "🌐 <b>رفاه اینترنت و زیرساخت دیجیتال</b>\n",
        f"🏗 سطح فعلی: <b>{level}</b> از {top} — {info['emoji']} {info['name']}",
        f"📶 پوشش اینترنت کشور: <b>{info['coverage']}%</b>",
        f"🙂 اثر روی رضایت: <b>+{sat_bonus:g}</b> امتیاز "
        f"(هر سطح +{per_sat:g})",
        f"📈 اثر روی درآمد: <b>+{round(growth * 100, 1)}%</b> "
        f"(هر سطح +{per_growth:g}%)",
        "",
    ]
    if level < top:
        lines += [
            f"⬆️ سطح بعدی: {nxt['emoji']} <b>{nxt['name']}</b> "
            f"(پوشش {nxt['coverage']}%)",
            f"💰 هزینه: <b>{fmt_money(cost)}</b> | 🧱 مصالح: <b>{fmt(mats)}</b> واحد",
            "",
            "💡 اینترنت پرسرعت رضایت مردم را بالا می‌برد و اقتصاد دیجیتال را "
            "روشن می‌کند؛ در نتیجه مالیات، نفت و فروش منابع شما بیشتر می‌شود.",
        ]
    else:
        lines.append("🏆 پوشش اینترنت کشور شما کامل است — همهٔ شهرها و روستاها آنلاین‌اند.")
    return "\n".join(lines)

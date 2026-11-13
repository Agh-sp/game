"""💸 اقتصاد کلان — تورم، چاپ پول، بدهی ملی و قیمت جهانی نفت.

واقعیت: هیچ دولتی بی‌نهایت پول ندارد. یا مالیات می‌گیرد، یا وام می‌گیرد (بهره
می‌پردازد) یا پول چاپ می‌کند (تورم و نارضایتی). هم‌زمان، قیمت جهانی نفت تعیین
می‌کند درآمد نفتی کشورها چقدر باشد — جنگ و بسته‌شدن تنگه قیمت را می‌پراند بالا.

اجزا:
  • `print_money` / `inflation` — چاپ پول، تورم و اثر آن بر درآمد و قیمت خرید.
  • `take_loan` / `installment_tick` — وام با بهره که هر دوره از خزانه کسر می‌شود.
  • `oil_price` / `oil_tick` — شاخص جهانی نفت (دلار) با واکنش به جنگ و تنگه‌ها.
همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting
from core.utils import clamp, fmt, iso

log = logging.getLogger(__name__)

DEFAULT_OIL_BASE = 80.0
DEFAULT_WAR_SHOCK = 12.0
DEFAULT_BLOCKADE_SHOCK = 18.0
DEFAULT_DRIFT = 3.0
DEFAULT_MIN = 35.0
DEFAULT_MAX = 180.0
DEFAULT_INCOME_WEIGHT = 0.75
DEFAULT_INFLATION_PRINT_STEP = 4.0
DEFAULT_INFLATION_DECAY = 2.0
DEFAULT_INFLATION_INCOME_WEIGHT = 0.5
DEFAULT_INFLATION_COST_WEIGHT = 0.6
DEFAULT_INFLATION_CAP = 60.0
DEFAULT_LOAN_RATE = 2.0
DEFAULT_LOAN_PERIODS = 10
DEFAULT_LOAN_LIMIT = 300_000_000
DEFAULT_LOAN_MISS_SAT = 3.0


async def _num(key: str, default: float) -> float:
    try:
        raw = await get_setting(key, "")
    except Exception:
        return default
    try:
        return float(str(raw).strip()) if str(raw).strip() else default
    except (TypeError, ValueError):
        return default


# ═══════════ 🛢 قیمت جهانی نفت ═══════════

async def oil_price() -> float:
    """قیمت فعلی هر بشکه به دلار (از جدول market؛ نبودِ ردیف → قیمت پایه)."""
    try:
        row = await db.fetchone("SELECT price FROM market WHERE key='oil'")
        if row and float(row["price"] or 0) > 0:
            return round(float(row["price"]), 2)
    except Exception:
        pass
    return await _num("oil_market_base_usd", DEFAULT_OIL_BASE)


async def oil_multiplier() -> float:
    """ضریب درآمد نفتی نسبت به قیمت پایه (با وزنی که ادمین تعیین می‌کند)."""
    base = await _num("oil_market_base_usd", DEFAULT_OIL_BASE)
    weight = await _num("oil_market_income_weight", DEFAULT_INCOME_WEIGHT)
    price = await oil_price()
    if base <= 0:
        return 1.0
    ratio = price / base
    return round(max(0.2, 1.0 + (ratio - 1.0) * weight), 3)


async def _set_oil(price: float) -> float:
    lo = await _num("oil_market_min_usd", DEFAULT_MIN)
    hi = await _num("oil_market_max_usd", DEFAULT_MAX)
    price = round(clamp(price, lo, hi), 2)
    await db.execute(
        "INSERT INTO market(key, name, price, prev_price, updated_at) "
        "VALUES('oil','🛢 نفت برنت',?,?,?) ON CONFLICT(key) DO UPDATE SET "
        "prev_price=price, price=excluded.price, updated_at=excluded.updated_at",
        (price, price, iso()))
    await db.execute("INSERT INTO market_history(key, price, created_at) VALUES('oil',?,?)",
                     (price, iso()))
    # تاریخچهٔ طولانی را کوتاه نگه می‌داریم
    try:
        await db.execute(
            "DELETE FROM market_history WHERE key='oil' AND id NOT IN "
            "(SELECT id FROM market_history WHERE key='oil' ORDER BY id DESC LIMIT 200)")
    except Exception:
        pass
    return price


async def oil_tick(bot=None) -> dict:
    """به‌روزرسانی قیمت جهانی: نوسان تصادفی + شوک جنگ‌ها و تنگه‌های بسته."""
    old = await oil_price()
    drift_pct = await _num("oil_market_drift_pct", DEFAULT_DRIFT)
    war_shock = await _num("oil_market_shock_war_pct", DEFAULT_WAR_SHOCK)
    blockade_shock = await _num("oil_market_shock_blockade_pct", DEFAULT_BLOCKADE_SHOCK)
    drift = random.uniform(-drift_pct, drift_pct) / 100
    try:
        wars = await db.fetchone("SELECT COUNT(*) c FROM wars WHERE status='active'")
        active_wars = int((wars or {}).get("c") or 0)
    except Exception:
        active_wars = 0
    try:
        blk = await db.fetchone("SELECT COUNT(*) c FROM strait_blockades")
        blockades = int((blk or {}).get("c") or 0)
    except Exception:
        blockades = 0
    shock = (1.0 + drift) * (1.0 + active_wars * war_shock / 100) \
        * (1.0 + blockades * blockade_shock / 100)
    # شوک‌ها هر تیک کامل اعمال نمی‌شوند؛ سهم کوچکی برای حرکت نرم قیمت
    new = old * (1.0 + (shock - 1.0) * 0.25)
    price = await _set_oil(new)
    change = (price - old) / old * 100 if old else 0
    if bot and abs(change) >= 10:
        try:
            from core.economy import announce_news
            arrow = "📈" if change > 0 else "📉"
            await announce_news(
                bot, f"{arrow} بازار جهانی نفت تکان خورد",
                [f"🛢 قیمت هر بشکه: <b>{price:.1f} دلار</b>",
                 f"{arrow} تغییر: <b>{change:+.1f}٪</b>",
                 f"⚔️ جنگ‌های فعال: {active_wars} | ⚓ تنگه‌های بسته: {blockades}",
                 "💰 درآمد نفتی کشورها با این قیمت بالا/پایین می‌رود."],
                section="oil")
        except Exception:
            pass
    return {"price": price, "old": old, "change": round(change, 2),
            "wars": active_wars, "blockades": blockades}


async def oil_market_text() -> str:
    price = await oil_price()
    mult = await oil_multiplier()
    base = await _num("oil_market_base_usd", DEFAULT_OIL_BASE)
    try:
        rows = await db.fetchall(
            "SELECT price, created_at FROM market_history WHERE key='oil' ORDER BY id DESC LIMIT 8")
    except Exception:
        rows = []
    lines = ["🛢 <b>بازار جهانی نفت</b>", "",
             f"💵 قیمت هر بشکه: <b>{price:.1f} دلار</b> (پایه {base:.0f})",
             f"💰 اثر روی درآمد نفتی: <b>×{mult}</b>"]
    if len(rows) > 1:
        lines.append("\n📉 <b>نمودار قیمت (اخیر → قدیم):</b>")
        lines.append("  " + " ".join(f"{float(r['price']):.0f}" for r in rows))
    lines.append("\n💡 جنگ‌های فعال و تنگه‌های بسته قیمت را بالا می‌برند؛ "
                 "آرامش و صلح آن را پایین می‌آورد.")
    return "\n".join(lines)


# ═══════════ 💸 تورم و چاپ پول ═══════════

async def inflation(user_id: int) -> float:
    row = await db.fetchone("SELECT inflation FROM users WHERE id=?", (user_id,))
    return round(float((row or {}).get("inflation") or 0), 1)


async def inflation_income_multiplier(user_id: int) -> float:
    """تورم قدرت خرید درآمد را می‌خورد."""
    value = await inflation(user_id)
    if value <= 0:
        return 1.0
    weight = await _num("inflation_income_weight", DEFAULT_INFLATION_INCOME_WEIGHT)
    return round(max(0.4, 1.0 - value / 100 * weight), 3)


async def price_multiplier(user_id: int) -> float:
    """ضریب گرانی خریدها برای کشوری که اسکناس چاپ کرده است."""
    value = await inflation(user_id)
    weight = await _num("inflation_cost_weight", DEFAULT_INFLATION_COST_WEIGHT)
    return round(1.0 + value / 100 * weight, 3)


async def add_inflation(user_id: int, delta: float) -> float:
    cap = await _num("inflation_cap", DEFAULT_INFLATION_CAP)
    current = await inflation(user_id)
    new = round(clamp(current + delta, 0.0, cap), 1)
    await db.execute("UPDATE users SET inflation=? WHERE id=?", (new, user_id))
    return new


async def print_money(user_id: int, amount: int | None = None) -> tuple[bool, str]:
    """🏦 چاپ پول: پول فوری، ولی تورم می‌آورد (و تورم رضایت را می‌خورد)."""
    if amount is None:
        amount = int(await _num("print_money_amount_m", 80.0) * 1_000_000)
    amount = max(1_000_000, int(amount))
    step = await _num("inflation_print_step", DEFAULT_INFLATION_PRINT_STEP)
    scale = min(3.0, amount / max(1.0, 100_000_000.0))
    new_inf = await add_inflation(user_id, step * scale)
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (amount, user_id))
    await db.execute(
        "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
        (min(8.0, 2.0 * scale), user_id))
    try:
        from core.events import log_event
        await log_event("currency", f"چاپ پول: {fmt(amount)} — تورم به {new_inf}٪ رسید")
    except Exception:
        pass
    return True, (f"🏦 <b>پول چاپ شد.</b>\n"
                  f"💰 به خزانه: <b>{fmt(amount)}</b>\n"
                  f"💸 تورم کشور: <b>{new_inf}٪</b> (قدرت خرید و رضایت مردم افت کرد)\n"
                  "⚠️ تورم خریدهای دولتی را گران می‌کند؛ با وام یا مالیات مدیریتش کنید.")


async def inflation_decay_tick(user_id: int) -> float:
    """تیک هر دوره: تورم کمی فروکش می‌کند (اگر سیاست انقباضی باشد)."""
    decay = await _num("inflation_decay", DEFAULT_INFLATION_DECAY)
    current = await inflation(user_id)
    if current <= 0 or decay <= 0:
        return current
    new = await add_inflation(user_id, -decay)
    return new


# ═══════════ 🏦 بدهی ملی و وام ═══════════

async def debt(user_id: int) -> dict | None:
    row = await db.fetchone("SELECT * FROM debts WHERE user_id=?", (user_id,))
    if not row or int(row.get("remaining") or 0) <= 0:
        return None
    return row


async def loan_limit(user_id: int) -> int:
    """سقف وام بر اساس درآمد دوره‌ای کشور."""
    try:
        from core import income as inc
        src = await inc.income_sources(user_id)
        per_period = int(src.get("total") or 0)
    except Exception:
        per_period = 0
    base = int(await _num("loan_limit_m", DEFAULT_LOAN_LIMIT / 1_000_000) * 1_000_000)
    return max(base // 2, min(base * 3, per_period * 4))


async def borrow(user_id: int, amount: int | None = None) -> tuple[bool, str]:
    """🏦 گرفتن وام از بانک مرکزی/خارجی با بهره."""
    if await debt(user_id):
        return False, "❌ شما وام فعال دارید؛ اول آن را تسویه کنید."
    limit = await loan_limit(user_id)
    amount = int(amount or limit)
    if amount <= 0:
        return False, "❌ مبلغ وام نامعتبر است."
    if amount > limit:
        return False, f"❌ سقف وام شما {fmt(limit)} است."
    rate = await _num("loan_rate_percent", DEFAULT_LOAN_RATE)
    periods = int(await _num("loan_periods", DEFAULT_LOAN_PERIODS))
    periods = max(1, periods)
    total = int(amount * (1 + rate / 100 * periods))
    installment = int(total / periods)
    await db.execute(
        "INSERT INTO debts(user_id, principal, remaining, rate_percent, periods, taken_at, updated_at) "
        "VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET principal=excluded.principal, "
        "remaining=excluded.remaining, rate_percent=excluded.rate_percent, "
        "periods=excluded.periods, taken_at=excluded.taken_at, updated_at=excluded.updated_at",
        (user_id, amount, total, rate, periods, iso(), iso()))
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (amount, user_id))
    return True, (f"🏦 <b>وام دریافت شد.</b>\n"
                  f"💰 مبلغ: {fmt(amount)} | 💸 بازپرداخت کل: {fmt(total)} "
                  f"(بهرهٔ {rate:g}٪ × {periods} دوره)\n"
                  f"📅 قسط هر دوره: {fmt(installment)} — خودکار از درآمد کسر می‌شود.")


async def repay(user_id: int, amount: int | None = None) -> tuple[bool, str]:
    """پرداخت پیش از موعد بدهی."""
    d = await debt(user_id)
    if not d:
        return False, "❌ بدهی فعالی ندارید."
    remaining = int(d["remaining"])
    pay = int(amount or remaining)
    pay = max(1, min(pay, remaining))
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < pay:
        return False, f"❌ بودجه کافی نیست — نیاز: {fmt(pay)} (بدهی: {fmt(remaining)})"
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (pay, user_id))
    new = remaining - pay
    if new <= 0:
        await db.execute("DELETE FROM debts WHERE user_id=?", (user_id,))
        return True, f"✅ <b>بدهی کامل تسویه شد.</b> ({fmt(remaining)} پرداخت شد)"
    await db.execute("UPDATE debts SET remaining=?, updated_at=? WHERE user_id=?",
                     (new, iso(), user_id))
    return True, f"✅ {fmt(pay)} از بدهی پرداخت شد. باقی‌مانده: <b>{fmt(new)}</b>"


async def installment_tick(user_id: int) -> dict:
    """کسر قسط دوره‌ای از خزانه؛ کمبود بودجه → بدهی بیشتر + نارضایتی."""
    d = await debt(user_id)
    if not d:
        return {"paid": 0}
    remaining = int(d["remaining"])
    periods = max(1, int(d["periods"] or 1))
    rate = float(d["rate_percent"] or 0)
    base_installment = max(1, int(int(d["principal"] or 0) * (1 + rate / 100 * periods) / periods))
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    pay = min(base_installment, remaining, money)
    lines: list[str] = []
    if pay > 0:
        await db.execute("UPDATE users SET money=money-? WHERE id=?", (pay, user_id))
        remaining -= pay
        lines.append(f"🏦 قسط بدهی: <b>-{fmt(pay)}</b> (باقی‌مانده {fmt(remaining)})")
    if remaining <= 0:
        await db.execute("DELETE FROM debts WHERE user_id=?", (user_id,))
        lines.append("✅ بدهی کشور تسویه شد.")
        return {"paid": pay, "lines": lines, "cleared": True}
    if pay < base_installment:
        missed = base_installment - pay
        remaining += int(missed * 0.1)   # جریمهٔ تأخیر
        sat_hit = await _num("loan_miss_satisfaction", DEFAULT_LOAN_MISS_SAT)
        await db.execute(
            "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
            (sat_hit, user_id))
        try:
            from core import unrest as unrest_mod
            await unrest_mod.add_unrest(user_id, sat_hit)
        except Exception:
            pass
        lines.append(f"⚠️ <b>قسط پرداخت نشد!</b> جریمهٔ تأخیر {fmt(missed * 0.1)} به بدهی اضافه شد "
                     f"و رضایت مردم −{sat_hit}.")
    await db.execute("UPDATE debts SET remaining=?, updated_at=? WHERE user_id=?",
                     (remaining, iso(), user_id))
    return {"paid": pay, "lines": lines, "remaining": remaining}


async def economy_text(user_id: int) -> str:
    """متن وضعیت اقتصادی کشور: تورم، بدهی و قیمت نفت."""
    inf = await inflation(user_id)
    d = await debt(user_id)
    price = await oil_price()
    mult = await oil_multiplier()
    lines = ["💸 <b>اقتصاد کلان</b>", "",
             f"💸 تورم: <b>{inf}٪</b>",
             f"   📉 اثر روی درآمد: ×{await inflation_income_multiplier(user_id)}",
             f"   🛒 اثر روی قیمت خرید: ×{await price_multiplier(user_id)}"]
    if d:
        lines.append(f"\n🏦 <b>بدهی ملی:</b> {fmt(int(d['remaining']))} از {fmt(int(d['principal']))}")
        lines.append(f"   💸 نرخ بهره: {float(d['rate_percent']):g}٪ × {int(d['periods'])} دوره")
    else:
        lines.append(f"\n🏦 <b>بدهی ملی:</b> ندارد ✅ (سقف وام: {fmt(await loan_limit(user_id))})")
    lines.append(f"\n🛢 <b>نفت جهانی:</b> {price:.1f} دلار/بشکه — اثر درآمد نفتی ×{mult}")
    lines.append("\n💡 چاپ پول سریع است ولی تورم و ناآرامی می‌آورد؛ وام ارزان‌تر است "
                 "ولی هر دوره قسطش کسر می‌شود.")
    return "\n".join(lines)

"""🚚 زنجیرهٔ تأمین، مهمات و سوخت — «گلوله قبل از سرباز تمام می‌شود».

واقعیت: در هر جنگ واقعی، مهمات و سوخت زودتر از نیرو تمام می‌شود؛ ارتشی که
تدارکات ندارد نمی‌تواند حمله کند و حتی نمی‌تواند از خودش دفاع کند.

مکانیک:
  • هر کشور یک انبار (جدول `supply_stock`) با دو قلم دارد: **مهمات** (amo) و **سوخت** (fuel).
  • تولید هر دورهٔ درآمد از پالایشگاه‌ها، شرکت‌ها و تیک صنعتی می‌آید
    (`supply_ammo_per_tick` / `supply_fuel_per_tick`).
  • هر حمله به اندازهٔ یگان‌های اعزامی مهمات و سوخت می‌سوزاند؛ انبار خالی
    قدرت حمله را تا `supply_penalty_cap`٪ کم می‌کند.
  • هر دوره، تدارکات روزانهٔ هر سرباز از انبار کسر می‌شود؛ اگر نرسد، کشور
    «گوش‌به‌زنگ تدارکات» می‌شود و توان دفاعی‌اش می‌افتد.
  • خرابکاری در پالایشگاه/مخازن، سهمی از انبار را می‌سوزاند (`supply_sabotage_pct`).

همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging

from core.db import db, get_setting
from core.utils import fmt, iso

log = logging.getLogger(__name__)

DEFAULT_AMMO_PER_TICK = 120.0
DEFAULT_FUEL_PER_TICK = 150.0
DEFAULT_AMMO_PER_UNIT = 2.5
DEFAULT_FUEL_PER_UNIT = 3.0
DEFAULT_ATTACK_PENALTY = 0.55
DEFAULT_PENALTY_CAP = 45.0
DEFAULT_RATION = 3.0
DEFAULT_UNFED_PENALTY = 0.35
DEFAULT_SABOTAGE_PCT = 0.08
DEFAULT_BUY_PRICE = 60_000
DEFAULT_FUEL_PRICE = 50_000

KIND_LABELS = {"ammo": "📦 مهمات", "fuel": "⛽ سوخت"}


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
        return await get_setting("sec_supply", "1") == "1"
    except Exception:
        return True


# ─── انبار ───

async def _ensure(user_id: int) -> None:
    """ساخت ردیف انبار با موجودی اولیهٔ سه‌دوره‌ای (فقط بار اول)."""
    row = await db.fetchone("SELECT user_id FROM supply_stock WHERE user_id=?", (user_id,))
    if row:
        return
    ammo = await _num("supply_ammo_per_tick", DEFAULT_AMMO_PER_TICK) * 3
    fuel = await _num("supply_fuel_per_tick", DEFAULT_FUEL_PER_TICK) * 3
    await db.execute(
        "INSERT OR IGNORE INTO supply_stock(user_id, ammo, fuel, updated_at) VALUES(?,?,?,?)",
        (user_id, ammo, fuel, iso()))


async def get(user_id: int) -> dict:
    """موجودی انبار تأمین یک کشور."""
    try:
        await _ensure(user_id)
        row = await db.fetchone("SELECT * FROM supply_stock WHERE user_id=?", (user_id,))
    except Exception:
        log.exception("supply get failed")
        row = None
    row = row or {}
    return {
        "user_id": user_id,
        "ammo": round(float(row.get("ammo") or 0), 1),
        "fuel": round(float(row.get("fuel") or 0), 1),
        "updated_at": row.get("updated_at") or "",
    }


async def add(user_id: int, ammo: float = 0, fuel: float = 0) -> dict:
    """افزودن مهمات/سوخت به انبار."""
    await _ensure(user_id)
    await db.execute(
        "UPDATE supply_stock SET ammo=MAX(0, ammo+?), fuel=MAX(0, fuel+?), updated_at=? "
        "WHERE user_id=?", (float(ammo), float(fuel), iso(), user_id))
    return await get(user_id)


async def take(user_id: int, ammo: float = 0, fuel: float = 0) -> dict:
    """کسر از انبار؛ خروجی: مقدار واقعاً کسرشده و کمبود."""
    st = await get(user_id)
    taken_ammo = min(st["ammo"], max(0.0, float(ammo)))
    taken_fuel = min(st["fuel"], max(0.0, float(fuel)))
    if taken_ammo or taken_fuel:
        await db.execute(
            "UPDATE supply_stock SET ammo=MAX(0, ammo-?), fuel=MAX(0, fuel-?), updated_at=? "
            "WHERE user_id=?", (taken_ammo, taken_fuel, iso(), user_id))
    return {
        "taken_ammo": round(taken_ammo, 1), "taken_fuel": round(taken_fuel, 1),
        "short_ammo": round(max(0.0, float(ammo) - taken_ammo), 1),
        "short_fuel": round(max(0.0, float(fuel) - taken_fuel), 1),
    }


async def burn_share(user_id: int, pct: float | None = None) -> dict:
    """سوزاندن سهمی از انبار (اثر خرابکاری در تأسیسات صنعتی)."""
    share = pct if pct is not None else await _num("supply_sabotage_pct", DEFAULT_SABOTAGE_PCT)
    st = await get(user_id)
    ammo = int(st["ammo"] * share)
    fuel = int(st["fuel"] * share)
    if ammo or fuel:
        await db.execute(
            "UPDATE supply_stock SET ammo=MAX(0, ammo-?), fuel=MAX(0, fuel-?), updated_at=? "
            "WHERE user_id=?", (ammo, fuel, iso(), user_id))
    return {"ammo": ammo, "fuel": fuel}


# ─── تولید ───

async def production(user_id: int) -> dict:
    """تولید هر دورهٔ مهمات/سوخت + منابع آن."""
    base_ammo = await _num("supply_ammo_per_tick", DEFAULT_AMMO_PER_TICK)
    base_fuel = await _num("supply_fuel_per_tick", DEFAULT_FUEL_PER_TICK)
    refineries = 0
    companies = 0
    try:
        row = await db.fetchone(
            "SELECT COALESCE(SUM(a.quantity),0) q FROM player_assets a JOIN buildings b ON b.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='building' AND b.name LIKE '%پالایشگاه%'", (user_id,))
        refineries = int((row or {}).get("q") or 0)
    except Exception:
        pass
    try:
        row = await db.fetchone("SELECT COUNT(*) c FROM companies WHERE owner_id=?", (user_id,))
        companies = int((row or {}).get("c") or 0)
    except Exception:
        pass
    mult = 1.0 + refineries * 0.25 + companies * 0.08
    # ⚠️ پالایشگاه ویران‌شده → تولید نصف
    try:
        row = await db.fetchone("SELECT supply_loss_until FROM states WHERE user_id=?", (user_id,))
        until = (row or {}).get("supply_loss_until")
        if until and str(until) > iso():
            mult *= 0.5
    except Exception:
        pass
    return {
        "ammo": round(base_ammo * mult, 1),
        "fuel": round(base_fuel * mult, 1),
        "refineries": refineries, "companies": companies,
        "mult": round(mult, 2),
    }


async def tick(user_id: int) -> dict:
    """تیک تولید صنعتی (هر دورهٔ درآمد/تیک آرام)."""
    if not await enabled():
        return {"ammo": 0, "fuel": 0, "skipped": True}
    prod = await production(user_id)
    await add(user_id, prod["ammo"], prod["fuel"])
    return prod


async def ration_tick(user_id: int) -> dict:
    """🍞 تدارکات روزانهٔ سربازان؛ اگر نرسد کشور گوش‌به‌زنگ می‌شود.

    خروجی: {"soldiers", "need_ammo", "need_fuel", "fed", "lines"}
    """
    if not await enabled():
        return {"soldiers": 0, "fed": True, "lines": []}
    try:
        row = await db.fetchone(
            "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
            (user_id,))
        soldiers = int((row or {}).get("c") or 0)
    except Exception:
        soldiers = 0
    if soldiers <= 0:
        return {"soldiers": 0, "fed": True, "lines": []}
    per = await _num("supply_ration_per_soldier", DEFAULT_RATION)
    need = soldiers * per
    res = await take(user_id, ammo=need, fuel=need * 0.4)
    fed = res["short_ammo"] <= 0 and res["short_fuel"] <= 0
    lines: list[str] = []
    if not fed:
        rows = max(1, int(soldiers * 0.12))
        try:
            await db.execute(
                "UPDATE states SET supply_loss_until=? WHERE user_id=?",
                (iso_plus_hours(6), user_id))
            cat = await db.fetchone(
                "SELECT item_id FROM player_assets WHERE user_id=? AND item_type='soldier' "
                "AND quantity>0 ORDER BY quantity DESC LIMIT 1", (user_id,))
            if cat:
                await db.execute(
                    "UPDATE player_assets SET quantity=MAX(0, quantity-?) "
                    "WHERE user_id=? AND item_type='soldier' AND item_id=?",
                    (rows, user_id, cat["item_id"]))
        except Exception:
            log.exception("ration penalty failed")
        lines.append(f"🍞 <b>کمبود تدارکات!</b> {fmt(rows)} سرباز فرار کردند "
                     "(مهمات/سوخت برای تغذیهٔ ارتش کافی نبود).")
    return {"soldiers": soldiers, "need_ammo": round(need, 1), "fed": fed, "lines": lines}


def iso_plus_hours(hours: float) -> str:
    from core.utils import add_hours
    return add_hours(hours)


# ─── اثر نظامی ───

async def need_for_attack(user_id: int, units: int) -> dict:
    """مهمات/سوخت لازم برای اعزام `units` یگان."""
    if not await enabled():
        return {"ammo": 0.0, "fuel": 0.0}
    ammo = await _num("supply_ammo_per_soldier", DEFAULT_AMMO_PER_UNIT)
    fuel = await _num("supply_fuel_per_soldier", DEFAULT_FUEL_PER_UNIT)
    return {"ammo": round(units * ammo, 1), "fuel": round(units * fuel, 1)}


async def factor(user_id: int) -> float:
    """ضریب قدرت ناشی از موجودی انبار (۱ = کامل، حداقل ۱−cap)."""
    if not await enabled():
        return 1.0
    st = await get(user_id)
    prod = await production(user_id)
    need_ammo = max(1.0, prod["ammo"])
    need_fuel = max(1.0, prod["fuel"])
    ratio = min(1.0, st["ammo"] / need_ammo, st["fuel"] / need_fuel)
    cap = await _num("supply_penalty_cap", DEFAULT_PENALTY_CAP) / 100
    penalty = await _num("supply_attack_penalty", DEFAULT_ATTACK_PENALTY)
    return round(max(1.0 - cap, 1.0 - (1.0 - ratio) * (1.0 - penalty) * 2), 3)


async def unfed_factor(user_id: int) -> float:
    """ضریب دفاعی در گوش‌به‌زنگ تدارکات (انبار خالی)."""
    if not await enabled():
        return 1.0
    st = await get(user_id)
    if st["ammo"] > 0 and st["fuel"] > 0:
        return 1.0
    penalty = await _num("supply_unfed_penalty", DEFAULT_UNFED_PENALTY)
    return round(max(0.3, 1.0 - penalty * 0.5), 3)


async def consume_attack(user_id: int, units: int) -> dict:
    """کسر تدارکات یک حمله + ضریب قدرت. خروجی: {"factor", "lines", ...}."""
    if not await enabled():
        return {"factor": 1.0, "lines": [], "ammo": 0, "fuel": 0}
    need = await need_for_attack(user_id, max(1, int(units)))
    res = await take(user_id, need["ammo"], need["fuel"])
    fac = await factor(user_id)
    lines: list[str] = []
    if res["short_ammo"] > 0 or res["short_fuel"] > 0:
        short = []
        if res["short_ammo"] > 0:
            short.append(f"{fmt(res['short_ammo'])} مهمات")
        if res["short_fuel"] > 0:
            short.append(f"{fmt(res['short_fuel'])} سوخت")
        lines.append(f"🚚 <b>کمبود تدارکات:</b> {' و '.join(short)} کم بود — "
                     f"قدرت حمله <b>{round((1 - fac) * 100)}٪</b> افت کرد. "
                     "از 🚚 تأمین، مهمات و سوخت بخرید.")
    if fac < 1.0 and not lines:
        lines.append(f"🚚 انبار تدارکات سبک است — قدرت حمله <b>{round((1 - fac) * 100)}٪</b> کم شد.")
    return {"factor": fac, "lines": lines, **res, "need": need}


# ─── خرید ───

async def buy(user_id: int, kind: str, qty: int) -> tuple[bool, str]:
    """خرید مهمات/سوخت از بازار داخلی با پول خزانه."""
    kind = "ammo" if kind not in ("ammo", "fuel") else kind
    qty = max(0, int(qty))
    if qty <= 0:
        return False, "❌ تعداد نامعتبر است."
    price_key = "supply_buy_price" if kind == "ammo" else "supply_fuel_price"
    default = DEFAULT_BUY_PRICE if kind == "ammo" else DEFAULT_FUEL_PRICE
    unit = int(await _num(price_key, default))
    cost = unit * qty
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, (f"❌ بودجه کافی نیست — نیاز: {fmt(cost)} پول "
                       f"({fmt(qty)} {KIND_LABELS[kind]} × {fmt(unit)})")
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    if kind == "ammo":
        await add(user_id, ammo=qty)
    else:
        await add(user_id, fuel=qty)
    return True, (f"✅ {fmt(qty)} {KIND_LABELS[kind]} به انبار اضافه شد.\n"
                  f"💰 هزینه: {fmt(cost)}")


# ─── نمایش ───

async def status_text(user_id: int, produced: dict | None = None) -> str:
    """متن وضعیت تأمین برای منوی بازیکن (شامل تناسب موجودی و اثر آن)."""
    st = await get(user_id)
    prod = produced or await production(user_id)
    fac = await factor(user_id)
    ammo_ratio = st["ammo"] / max(1.0, prod["ammo"])
    fuel_ratio = st["fuel"] / max(1.0, prod["fuel"])
    def _bar(r: float) -> str:
        filled = max(0, min(5, int(round(r))))
        return "█" * filled + "░" * (5 - filled)
    lines = [
        "🚚 <b>زنجیرهٔ تأمین و مهمات</b>",
        "",
        f"📦 مهمات: <b>{fmt(st['ammo'])}</b> {_bar(ammo_ratio)} ({ammo_ratio:.1f} دوره)",
        f"⛽ سوخت: <b>{fmt(st['fuel'])}</b> {_bar(fuel_ratio)} ({fuel_ratio:.1f} دوره)",
        "",
        f"🏭 تولید هر دوره: {fmt(prod['ammo'])} مهمات + {fmt(prod['fuel'])} سوخت",
    ]
    if prod.get("refineries") or prod.get("companies"):
        lines.append(f"   └ {prod['refineries']} پالایشگاه، {prod['companies']} شرکت (×{prod['mult']})")
    lines.append(f"🎯 اثر فعلی روی قدرت حمله: <b>×{fac}</b>")
    if fac < 1.0:
        lines.append("   ⚠️ انبار سبک است؛ پیش از حمله تدارکات بخرید.")
    buy_ammo = int(await _num("supply_buy_price", DEFAULT_BUY_PRICE))
    buy_fuel = int(await _num("supply_fuel_price", DEFAULT_FUEL_PRICE))
    lines += [
        "",
        f"🛒 قیمت بازار داخلی: هر مهمات {fmt(buy_ammo)} | هر سوخت {fmt(buy_fuel)}",
        "💡 هر حمله به اندازهٔ یگان‌های اعزامی از انبار کم می‌کند و هر دوره، "
        "تدارکات ارتش هم کسر می‌شود.",
    ]
    return "\n".join(lines)

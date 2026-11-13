"""موتور نبرد واقعی (Real Combat Engine).

هر حمله‌ای در بازی با همین موتور حل می‌شود: توان واقعی دو طرف از تجهیزات و
سربازهای موجودشان محاسبه می‌شود، «استراتژی حمله» بر اساس ترکیب نیروها انتخاب
می‌شود، نتیجه با شانس مبتنی بر نسبت توان تعیین می‌گردد و **هر دو طرف** تلفات
واقعی (کسر از انبار تجهیزات/سرباز) می‌دهند. سپس یک گزارش استاندارد برای کانال
ساخته می‌شود که نوع استراتژی و خسارات دو طرف را نشان می‌دهد.
"""
from __future__ import annotations

import random

from core.db import db
from core.economy import sub_asset
from core.utils import clamp, fmt

# ─── استراتژی‌های حمله ───
# atk/def: ضریب توان | atk_loss/def_loss: ضریب پایه تلفات هر طرف
STRATEGIES: dict[str, dict] = {
    "naval_assault": {
        "name": "یورش ناوگان سطحی", "emoji": "⚓",
        "desc": "ناوها و ناوشکن‌ها با آتش پشتیبان به خطوط دفاعی آبراه یورش می‌برند.",
        "atk": 1.00, "def": 1.00, "atk_loss": 0.16, "def_loss": 0.22,
    },
    "naval_blockade": {
        "name": "محاصره دریایی", "emoji": "🚧",
        "desc": "قطع خطوط تدارک و بستن دهانه تنگه، سپس فشار تدریجی برای تسلیم پادگان.",
        "atk": 0.88, "def": 0.78, "atk_loss": 0.10, "def_loss": 0.26,
    },
    "amphibious": {
        "name": "عملیات آبی‌خاکی", "emoji": "🪖",
        "desc": "پیاده‌کردن نیروی زمینی روی سواحل و تصرف مواضع ساحلی با پشتیبانی دریایی.",
        "atk": 1.12, "def": 1.05, "atk_loss": 0.22, "def_loss": 0.20,
    },
    "sub_surprise": {
        "name": "کمین زیردریایی", "emoji": "🌊",
        "desc": "ضربه غافلگیرکننده زیردریایی‌ها به ناوگان مدافع پیش از شروع درگیری سطحی.",
        "atk": 1.18, "def": 0.85, "atk_loss": 0.12, "def_loss": 0.28,
    },
    "blitz": {
        "name": "یورش برق‌آسای زرهی", "emoji": "🪖",
        "desc": "نفوذ سریع یگان‌های زرهی و پیاده به عمق خاک دشمن.",
        "atk": 1.10, "def": 0.95, "atk_loss": 0.18, "def_loss": 0.24,
    },
    "air_supremacy": {
        "name": "برتری هوایی و بمباران", "emoji": "✈️",
        "desc": "پاکسازی آسمان و بمباران مواضع پدافندی و صنعتی دشمن.",
        "atk": 1.05, "def": 1.00, "atk_loss": 0.14, "def_loss": 0.20,
    },
    "missile_strike": {
        "name": "ضربه موشکی غافلگیرکننده", "emoji": "🚀",
        "desc": "شلیک موج اول موشک‌های کروز/بالستیک برای فلج‌کردن سامانه‌های فرماندهی.",
        "atk": 1.15, "def": 0.90, "atk_loss": 0.10, "def_loss": 0.22,
    },
    "space_strike": {
        "name": "ضربه از مدار (تسلیحات فضایی)", "emoji": "🛰️",
        "desc": "حمله از مدار با سلاح‌های فضایی؛ ضربه‌ای گران اما کاری.",
        "atk": 1.25, "def": 0.90, "atk_loss": 0.08, "def_loss": 0.26,
    },
    "combined": {
        "name": "عملیات مشترک ترکیبی", "emoji": "🔀",
        "desc": "هماهنگی هم‌زمان نیروی دریایی، هوایی، زمینی و موشکی.",
        "atk": 1.12, "def": 0.95, "atk_loss": 0.17, "def_loss": 0.24,
    },
    "garrison": {
        "name": "استقرار ناوگان بدون درگیری", "emoji": "🛟",
        "desc": "تنگه بدون مدافع مستقر بود؛ ناوگان بدون نبرد موضع را تصرف کرد.",
        "atk": 1.00, "def": 1.00, "atk_loss": 0.02, "def_loss": 0.00,
    },
}

# نگاشت نوع حملهٔ کشور → استراتژی پیش‌فرض
ATYPE_STRATEGY = {
    "sea": "naval_assault", "air": "air_supremacy", "land": "blitz",
    "missile": "missile_strike", "space": "space_strike", "mixed": "combined",
}


def strategy(key: str) -> dict:
    s = dict(STRATEGIES.get(key, STRATEGIES["combined"]))
    s["key"] = key if key in STRATEGIES else "combined"
    return s


def pick_strategy(atype: str = "mixed", composition: dict | None = None,
                  defender_has_navy: bool = True, allow_blockade: bool = True) -> dict:
    """انتخاب استراتژی بر اساس نوع حمله و ترکیب واقعی نیروهای مهاجم."""
    comp = {k: int(v or 0) for k, v in (composition or {}).items()}
    total = sum(comp.values()) or 1
    share = {k: v / total for k, v in comp.items()}

    if atype == "sea":
        if share.get("submarine", 0) >= 0.35:
            return strategy("sub_surprise")
        if share.get("soldier", 0) >= 0.25:
            return strategy("amphibious")
        if allow_blockade and defender_has_navy and random.random() < 0.35:
            return strategy("naval_blockade")
        if share.get("air", 0) >= 0.20:
            return strategy("air_supremacy")
        return strategy("naval_assault")
    if atype == "land":
        return strategy("blitz")
    if atype == "air":
        return strategy("air_supremacy")
    if atype == "missile":
        return strategy("missile_strike")
    if atype == "space":
        return strategy("space_strike")
    return strategy("combined")


def battle_chance(atk_power: float, def_power: float, exponent: float = 1.4) -> float:
    """شانس پیروزی مهاجم؛ ۵٪ تا ۹۵٪ (توان برابر ≈ ۵۰٪)."""
    a = max(1.0, float(atk_power or 0)) ** exponent
    d = max(1.0, float(def_power or 0)) ** exponent
    return clamp(a / (a + d), 0.05, 0.95)


def loss_ratios(chance: float, strat: dict) -> tuple[float, float]:
    """درصد تلفات هر طرف. نبرد نزدیک خونین‌تر است و طرف بازنده بیشتر می‌بازد."""
    closeness = 1.0 - abs(chance - 0.5)          # 0.5 (نابرابر) … 1.0 (نزدیک)
    intensity = 0.75 + 0.5 * closeness
    atk = clamp(strat["atk_loss"] * intensity * (0.65 + (1.0 - chance)), 0.03, 0.65)
    dfn = clamp(strat["def_loss"] * intensity * (0.65 + chance), 0.03, 0.75)
    return round(atk, 3), round(dfn, 3)


# ─── کسر تلفات از انبار واقعی بازیکن ───

async def equipment_rows(user_id: int, cat_keys: tuple[str, ...] | None = None,
                         only_ids: list[int] | None = None) -> list[dict]:
    sql = ("SELECT a.item_id AS id, a.quantity, e.name, e.emoji, e.subcategory, c.key AS cat_key "
           "FROM player_assets a JOIN equipment e ON e.id=a.item_id "
           "LEFT JOIN equipment_categories c ON c.id=e.category_id "
           "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0")
    args: list = [user_id]
    if cat_keys:
        sql += " AND c.key IN (%s)" % ",".join("?" * len(cat_keys))
        args += list(cat_keys)
    if only_ids:
        sql += " AND a.item_id IN (%s)" % ",".join("?" * len(only_ids))
        args += [int(i) for i in only_ids]
    return await db.fetchall(sql, tuple(args))


async def soldier_rows(user_id: int) -> list[dict]:
    return await db.fetchall(
        "SELECT a.item_id AS id, a.quantity, s.name, s.emoji FROM player_assets a "
        "JOIN soldier_types s ON s.id=a.item_id "
        "WHERE a.user_id=? AND a.item_type='soldier' AND a.quantity>0", (user_id,))


def _lost_count(qty: int, ratio: float) -> int:
    if qty <= 0 or ratio <= 0:
        return 0
    raw = qty * ratio
    lost = int(round(raw))
    if lost == 0 and qty >= 3 and raw >= 0.9:   # یگان‌های بزرگ همیشه کمی آسیب می‌بینند
        lost = 1
    return min(lost, qty)


async def apply_losses(user_id: int, rows: list[dict], ratio: float,
                       item_type: str = "equipment") -> tuple[list[str], int]:
    """کسر تلفات از روی ردیف‌های واقعی؛ خروجی: (لیست متنی، تعداد کل منهدم‌شده)"""
    out: list[str] = []
    total = 0
    for r in rows:
        lost = _lost_count(int(r["quantity"] or 0), ratio)
        if lost <= 0:
            continue
        if await sub_asset(user_id, item_type, int(r["id"]), lost):
            out.append(f"{fmt(lost)}× {r['emoji'] or '▫️'} {r['name']}")
            total += lost
    return out, total


# ─── 🎯 مدل تلفات واقعی نبرد ───
# برای هر نبرد ثبت می‌شود: چه یگان‌هایی با چه تعدادی اعزام شدند، نوع عملیات چه بود
# و مدافع چه تعداد یگان و سرباز در جبهه داشت. سپس تلفات *فقط* روی همان چیزی
# محاسبه می‌شود که واقعاً جنگیده است:
#
#   • یگان‌های اعزامی → تلفات بر اساس همان تعداد ارسالی (نه کل انبار)؛
#   • ذخیره‌گاه (یگان‌های نرفته) → فرسایش ناچیز و قابل تنظیم؛
#   • مدافع → فقط تجهیزات هم‌جبهه (دریایی در برابر دریایی، زمینی در برابر زمینی…)
#     و سقف کل تلفات = یگان اعزامی مهاجم × `battle_defender_kill_ratio`؛
#   • حملهٔ فقط-سرباز → تجهیزات ذخیرهٔ مهاجم دست‌نخورده می‌ماند.
_DEPLOYED: dict[tuple[int, str], dict[int, int]] = {}     # (uid, type) → {item_id: تعداد اعزامی}
_BATTLE_CTX: dict[str, dict] = {}                          # زمینهٔ آخرین نبرد برای گزارش

# جبههٔ هر نوع عملیات: تجهیزات مدافع که در آن جبهه واقعاً درگیر می‌شوند
FRONT_CATS: dict[str, tuple[str, ...]] = {
    "sea": ("sea", "air"),          # نبرد دریایی: ناوها + پوشش هوایی
    "air": ("air", "sea"),          # پوشش هوایی/حامل‌ها
    "land": ("land", "air"),        # زرهی/پیاده + پشتیبانی هوایی
    "missile": ("air", "land", "missile", "sea"),   # پدافند، سامانه‌های زمینی و بندرها
    "space": ("space", "air", "missile", "sea", "land"),
    "mixed": ("sea", "air", "land", "missile", "space"),
}


def set_deployed(user_id: int, item_type: str, ids, quantities: dict | None = None) -> None:
    """ثبت یگان‌هایی که در این نبرد واقعاً شرکت کرده‌اند (با تعداد اعزامی)."""
    if isinstance(ids, dict):
        quantities = ids
        ids = list(ids.keys())
    ids = [int(i) for i in (ids or [])]
    qty = {int(k): int(v) for k, v in (quantities or {}).items()}
    _DEPLOYED[(int(user_id), item_type)] = {i: max(0, qty.get(i, 0)) or 1 for i in ids}


def deployed_map(user_id: int, item_type: str = "equipment") -> dict[int, int]:
    return dict(_DEPLOYED.get((int(user_id), item_type), {}))


def deployed_total(user_id: int, item_type: str = "equipment") -> int:
    return sum(_DEPLOYED.get((int(user_id), item_type), {}).values())


def clear_deployed(user_id: int, item_type: str = "equipment") -> None:
    _DEPLOYED.pop((int(user_id), item_type), None)


def set_battle_context(**kw) -> None:
    """ذخیرهٔ زمینهٔ نبرد (نوع عملیات، تعداد یگان‌های مدافع در جبهه…) برای گزارش."""
    _BATTLE_CTX.clear()
    _BATTLE_CTX.update(kw)


def battle_context() -> dict:
    return dict(_BATTLE_CTX)


def _deployed_ids(user_id: int, item_type: str) -> set[int]:
    return set(_DEPLOYED.get((int(user_id), item_type), {}))


def _loss_rows(user_id: int, rows: list[dict], item_type: str) -> tuple[list, list]:
    """جدا کردن یگان‌های درگیر از ذخیره‌گاه."""
    ids = _deployed_ids(user_id, item_type)
    if not ids:
        return list(rows), []
    deployed = [r for r in rows if int(r.get("id") or 0) in ids]
    reserve = [r for r in rows if int(r.get("id") or 0) not in ids]
    return deployed, reserve


async def apply_capped_losses(user_id: int, rows: list[dict], ratio: float,
                              cap_total: int, item_type: str = "equipment"
                              ) -> tuple[list[str], int]:
    """تلفات با **سقف کل یگان** — یک یورش کوچک نمی‌تواند کل انبار را نابود کند.

    `cap_total` بیشترین تعداد یگانی است که در همین نبرد می‌تواند از بین برود
    (مثلاً ۵ کشتی مهاجم حداکثر می‌توانند ۷ یگان مدافع را از کار بیندازند،
    نه ۱۰۰ ناو هواپیمابر).
    """
    if not rows or ratio <= 0 or cap_total <= 0:
        return [], 0
    budget = int(cap_total)
    out: list[str] = []
    total = 0
    # حق تلفات متناسب با اندازهٔ هر یگان تقسیم می‌شود تا همیشه یک یگان کوچک
    # همهٔ سهم را نبلعد (نه اینکه فقط «کم‌تعدادها» بمیرند).
    weights = {}
    for r in rows:
        lost = _lost_count(int(r.get("quantity") or 0), ratio)
        if lost > 0:
            weights[int(r["id"])] = lost
    if not weights:
        return [], 0
    all_lost = sum(weights.values())
    scale = min(1.0, budget / all_lost)
    for r in sorted(rows, key=lambda x: weights.get(int(x["id"]), 0)):
        if budget <= 0:
            break
        want = weights.get(int(r["id"]), 0)
        if want <= 0:
            continue
        lost = min(want if scale >= 1.0 else max(1, int(round(want * scale))), budget,
                   int(r.get("quantity") or 0))
        if lost <= 0:
            continue
        if await sub_asset(user_id, item_type, int(r["id"]), lost):
            out.append(f"{fmt(lost)}× {r.get('emoji') or '▫️'} {r['name']}")
            total += lost
            budget -= lost
    return out, total


async def attacker_deployed_units(user_id: int) -> int:
    """تعداد یگان‌های اعزامی مهاجم در نبرد جاری (تعداد، نه تنوع)."""
    return deployed_total(user_id, "equipment")


async def defend_cap(attacker_id: int, attacker_units: int,
                     per_unit: float | None = None) -> int:
    """سقف یگان‌های مدافع که در این نبرد می‌توانند از بین بروند."""
    from core.db import get_setting
    if per_unit is None:
        try:
            per_unit = float(str(await get_setting("battle_defender_kill_ratio", "1.5")) or 1.5)
        except Exception:
            per_unit = 1.5
    units = attacker_units or deployed_total(attacker_id, "equipment")
    return max(1, int(round(units * per_unit)))


async def apply_attrition_losses(user_id: int, rows: list[dict], ratio: float,
                                 item_type: str = "equipment"
                                 ) -> tuple[list[str], int, str]:
    """🎯 تلفات واقعی بر اساس **نبرد** نه بر اساس کل انبار.

    باگ گزارش‌شده: «۵ کشتی می‌فرستم، دشمن یکی دو هواپیما دارد، بعد می‌بینم
    ۱۰۰ ناو هواپیمابر نابود شده». اکنون:

      • تلفات اصلی فقط از یگان‌های **درگیر** و به نسبت تعداد اعزامی گرفته می‌شود؛
      • انبار ذخیره حداکثر چند درصد فرسایش می‌بیند (قابل تنظیم) و اگر هیچ یگانی
        اعزام نشده باشد (حملهٔ فقط-سرباز) کاملاً دست‌نخورده می‌ماند؛

    خروجی: (فهرست تلفات، مجموع، توضیح شفاف برای گزارش)
    """
    from core.db import get_setting

    try:
        reserve_ratio = float(str(await get_setting("battle_reserve_loss_percent", "2")) or 2) / 100
    except Exception:
        reserve_ratio = 0.02
    reserve_ratio = max(0.0, min(0.2, reserve_ratio))
    deployed_map_ = deployed_map(user_id, item_type)
    deployed, reserve = _loss_rows(user_id, rows, item_type)

    out: list[str] = []
    total = 0
    notes: list[str] = []
    if deployed and deployed_map_:
        # تلفات هر یگان = نسبت تلفات × تعداد واقعاً اعزام‌شده از آن یگان
        scaled: list[dict] = []
        for r in deployed:
            sent = deployed_map_.get(int(r["id"])) or int(r.get("quantity") or 0)
            scaled.append({**r, "quantity": min(sent, int(r.get("quantity") or 0))})
        lines, n = await apply_losses(user_id, scaled, ratio, item_type)
        out.extend(lines)
        total += n
        notes.append(f"تلفات فقط از {fmt(deployed_total(user_id, item_type))} یگانِ اعزامی محاسبه شد")
    elif not deployed_map_:
        # چیزی اعزام نشده (مثلاً حملهٔ فقط-سرباز) → تجهیزات اصلاً درگیر نبوده‌اند
        lines, n = await apply_losses(user_id, deployed, ratio, item_type)
        out.extend(lines)
        total += n
    if reserve and reserve_ratio > 0 and deployed_map_:
        kept: list[str] = []
        spilled = 0
        for r in reserve:
            qty = int(r.get("quantity") or 0)
            # فرسایش ذخیره‌گاه: درصدی از همان یگان (حداکثر ۲ یگان) و تنها اگر
            # انبار واقعاً بزرگ باشد — نه اینکه هر نبرد یک یگان از هر قلم بسوزاند.
            lost = 0
            if qty >= 50 and reserve_ratio > 0:
                lost = min(2, int(qty * reserve_ratio))
                if lost <= 0 and random.random() < reserve_ratio:
                    lost = 1
            if lost and await sub_asset(user_id, item_type, int(r["id"]), lost):
                kept.append(f"{fmt(lost)}× {r.get('emoji') or '▫️'} {r['name']}")
                spilled += lost
        if kept:
            out.extend([f"{x} (ذخیره)" for x in kept[:4]])
            total += spilled
            notes.append("ذخیره‌گاه انبار تقریباً دست‌نخورده ماند")
    note = "؛ ".join(notes)
    return out, total, note


async def apply_sent_losses(user_id: int, rows: list[dict], killed_total: int,
                            sent: dict[int, int] | None = None,
                            item_type: str = "equipment") -> tuple[list[str], int]:
    """⚔️ تلفات مهاجم بر اساس **تعداد اعزامی هر یگان** و تعداد کل کشته‌ها.

    اگر ۱۰۰ کشتی داشته باشی و ۵ تا بفرستی و ۲۶٪ تلفات بدهی، فقط از همان ۵ تا
    کم می‌شود (۲ کشتی)، نه ۲۶ کشتی از کل انبار. اگر سربازی هم همراه نبرد بوده
    بخشی از تلفات به سربازها می‌خورد (متناسب).
    """
    sent = {int(k): int(v) for k, v in (sent or deployed_map(user_id, item_type)).items()}
    if not rows or killed_total <= 0:
        return [], 0
    picked = [r for r in rows if int(r.get("id") or 0) in sent and sent[int(r["id"])] > 0]
    if not picked:
        return [], 0
    sent_total = sum(sent[int(r["id"])] for r in picked)
    if sent_total <= 0:
        return [], 0
    killed = min(int(killed_total), sent_total)
    out: list[str] = []
    total = 0
    left = killed
    for r in sorted(picked, key=lambda x: sent[int(x["id"])], reverse=True):
        if left <= 0:
            break
        share = max(1, int(round(killed * sent[int(r["id"])] / sent_total)))
        take = min(share, left, int(r.get("quantity") or 0), sent[int(r["id"])])
        if take <= 0:
            continue
        if await sub_asset(user_id, item_type, int(r["id"]), take):
            out.append(f"{fmt(take)}× {r.get('emoji') or '▫️'} {r['name']}")
            total += take
            left -= take
    return out, total


async def apply_front_losses(user_id: int, rows: list[dict], ratio: float,
                             cap_total: int, item_type: str = "equipment",
                             fronts: tuple[str, ...] | None = None
                             ) -> tuple[list[str], int]:
    """🛡 تلفات مدافع: فقط تجهیزات هم‌جبهه و با سقف کل.

    اگر `fronts` داده شود، تنها یگان‌هایی آسیب می‌بینند که در آن جبهه واقعاً
    درگیر می‌شوند (تانک در نبرد دریایی نمی‌سوزد). اگر هیچ یگانی در آن جبهه
    نباشد، دفاع صرفاً با سرباز/پدافند است و تجهیزات دست‌نخورده می‌مانند.
    """
    if not rows or ratio <= 0 or cap_total <= 0:
        return [], 0
    pool = rows
    if fronts:
        same = [r for r in rows if (r.get("cat_key") or "") in fronts]
        if same:
            pool = same
        else:
            # هیچ تجهیزی در این جبهه نیست → فقط سرباز/پدافند آسیب می‌بیند
            return [], 0
    return await apply_capped_losses(user_id, pool, ratio, cap_total, item_type)


async def apply_unit_losses(user_id: int, ratio: float, cat_keys: tuple[str, ...],
                            only_ids: list[int] | None = None) -> tuple[list[str], int]:
    rows = await equipment_rows(user_id, cat_keys, only_ids)
    return await apply_losses(user_id, rows, ratio, "equipment")


async def apply_soldier_losses(user_id: int, ratio: float) -> tuple[list[str], int]:
    if ratio <= 0:
        return [], 0
    return await apply_losses(user_id, await soldier_rows(user_id), ratio, "soldier")


# ─── گزارش نبرد برای کانال ───

def _casualty_line(title: str, losses: list[str], units: int, ratio: float) -> str:
    pct = round(ratio * 100)
    head = f"• {title} ({pct}%):"
    if not losses:
        return f"{head} بدون تلفات"
    shown = " ، ".join(losses[:5])
    more = f" و {len(losses) - 5} قلم دیگر" if len(losses) > 5 else ""
    return f"{head}\n   {shown}{more} — مجموع {fmt(units)} یگان"


def battle_report(*, strat: dict, atk_country: dict, def_country: dict,
                  atk_power: float, def_power: float, chance: float, won: bool,
                  atk_losses: list[str], def_losses: list[str],
                  atk_units: int, def_units: int,
                  atk_ratio: float, def_ratio: float,
                  extra_lines: list[str] | None = None,
                  title: str = "گزارش نبرد") -> str:
    """گزارش یکدست: نوع استراتژی، توان دو طرف، نتیجه و خسارات هر دو طرف."""
    lines = [
        f"{strat['emoji']} <b>{title} — استراتژی: {strat['name']}</b>",
        f"طرفین: {atk_country['flag']} <b>{atk_country['name']}</b> ➔ "
        f"{def_country['flag']} <b>{def_country['name']}</b>",
        f"🧠 <i>{strat['desc']}</i>\n",
        f"🗡 توان مهاجم: <b>{fmt(atk_power)}</b>",
        f"🛡 توان مدافع: <b>{fmt(def_power)}</b>",
        f"🎲 شانس پیروزی مهاجم: <b>{round(chance * 100)}%</b>",
    ]
    if extra_lines:
        lines += extra_lines
    lines.append("")
    if won:
        lines.append(f"🏆 <b>پیروزی {atk_country['name']}</b> — استراتژی «{strat['name']}» جواب داد.")
    else:
        lines.append(f"🛡 <b>دفاع موفق {def_country['name']}</b> — حمله «{strat['name']}» دفع شد.")
    lines += ["", "💥 <b>خسارات طرفین:</b>",
              _casualty_line(f"تلفات مهاجم — {atk_country['name']}", atk_losses, atk_units, atk_ratio),
              _casualty_line(f"تلفات مدافع — {def_country['name']}", def_losses, def_units, def_ratio)]
    return "\n".join(lines)

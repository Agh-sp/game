"""🎯 خرابکاری در تأسیسات — زدن هر چیزی که دشمن ساخته است.

به‌درخواست کاربر: «قابلیت زدن تأسیسات هسته‌ای و نفتی و هر چیزی که ساخته باشد».

این ماژول یک موتور واحد برای هدف قرار دادن **سازه‌های ساخته‌شدهٔ دشمن** است:

| هدف | 🎯 چه چیزی از بین می‌رود |
|---|---|
| 🛢 دکل نفتی | یک دکل نابود می‌شود، استخراج و درآمد نفتی افت می‌کند |
| ☢️ تأسیسات هسته‌ای | همان موتور `core.nuclear` (HP، سانتریفیوژ، عقب‌نشینی غنی‌سازی، نشت) |
| ⚡ نیروگاه / سد / بادی | ظرفیت برق کم می‌شود → خاموشی و افت رضایت |
| 💧 تأسیسات آب | ظرفیت آب کم می‌شود |
| 🔥 تأسیسات گاز | ظرفیت گاز کم می‌شود |
| 🏢 شرکت اقتصادی | درآمد شرکت از بین می‌رود |
| 🌐 زیرساخت اینترنت | یک سطح اینترنت پایین می‌آید (رفاه + درآمد) |
| 🎖 پدافند هوایی | بخشی از تجهیزات پدافندی نابود می‌شود |
| 🛡 پالایشگاه / مخازن | سازه‌های اقتصادی نابود می‌شوند |

**واقعیت‌گرایی:**

- 🛡 **پدافند هدف**: هر سازه با استحکام خودش + پدافند هوایی مدافع محافظت می‌شود؛
  اگر مدافع پدافند قوی داشته باشد، حمله رهگیری می‌شود.
- 🎲 **دقت**: احتمال اصابت از نسبت «توان آتش مهاجم / (توان آتش + پدافند هدف)» می‌آید.
- 🕶 **خرابکاری سایبری**: بدون موشک هم ممکن است، اما فقط با تجهیزات سایبری و
  علیه اهداف داده‌محور (اینترنت، شرکت، پدافند).
- ⛓ **اثر تجمعی**: هر ضربه به فرسایش کشور اضافه می‌کند (`core.attrition`).
- 📰 **پیامد سیاسی**: هر حمله به زیرساخت غیرنظامی رضایت مدافع را پایین می‌آورد و
  در کانال رسمی اعلام می‌شود.
- ⏱ **کول‌داون**: بین دو خرابکاری فاصله لازم است (`sabotage_cooldown_minutes`).
- 🧱 **بازسازی**: مدافع می‌تواند با هزینه، سازه‌های آسیب‌دیده را تعمیر کند.

همهٔ اعداد از پنل ادمین قابل تغییرند (`sabotage_*`).
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting
from core.utils import fmt, iso

log = logging.getLogger(__name__)

# ─── انواع هدف ───
TARGET_KINDS: dict[str, dict] = {
    "oil": {
        "title": "🛢 دکل نفتی", "emoji": "🛢", "hp": 60,
        "needs": ("missile", "air", "space", "cyber"),
        "desc": "استخراج و درآمد نفتی دشمن را کم می‌کند",
    },
    "nuclear": {
        "title": "☢️ تأسیسات هسته‌ای", "emoji": "☢️", "hp": 400,
        "needs": ("missile", "air", "space"),
        "desc": "سانتریفیوژها را نابود و غنی‌سازی را عقب می‌راند",
    },
    "power": {
        "title": "⚡ نیروگاه برق", "emoji": "⚡", "hp": 80,
        "needs": ("missile", "air", "space"),
        "desc": "ظرفیت برق را قطع و مردم را در تاریکی می‌گذارد",
    },
    "water": {
        "title": "💧 تأسیسات آب", "emoji": "💧", "hp": 70,
        "needs": ("missile", "air", "space"),
        "desc": "آب شرب و کشاورزی دشمن را قطع می‌کند",
    },
    "gas": {
        "title": "🔥 تأسیسات گاز", "emoji": "🔥", "hp": 75,
        "needs": ("missile", "air", "space"),
        "desc": "گرمایش و صنایع گازی را از کار می‌اندازد",
    },
    "company": {
        "title": "🏢 شرکت اقتصادی", "emoji": "🏢", "hp": 40,
        "needs": ("cyber", "air", "missile"),
        "desc": "درآمد خصوصی دشمن را نابود می‌کند",
    },
    "internet": {
        "title": "🌐 زیرساخت اینترنت", "emoji": "🌐", "hp": 45,
        "needs": ("cyber",),
        "desc": "پوشش اینترنت را یک سطح پایین می‌آورد",
    },
    "airdef": {
        "title": "🎖 پدافند هوایی", "emoji": "🎖", "hp": 90,
        "needs": ("missile", "air", "space", "cyber"),
        "desc": "سپر پدافندی دشمن را برای حملات بعدی می‌شکند",
    },
    "industry": {
        "title": "🏭 پالایشگاه و مخازن", "emoji": "🏭", "hp": 65,
        "needs": ("missile", "air", "space"),
        "desc": "ارزش فروش نفت و ذخایر راهبردی را کم می‌کند",
    },
}

MISSILE_COOLDOWN_KEY = "sabotage_cooldown_minutes"
DEFAULT_COOLDOWN_MIN = 20
DEFAULT_MAX_WEAR_ADD = 8.0      # ⛓ فرسایش اضافه‌شده به مدافع در هر خرابکاری موفق
DEFAULT_SAT_HIT = 3.0           # 😞 افت رضایت مدافع (زیرساخت غیرنظامی)


async def _num(key: str, default: float) -> float:
    try:
        raw = await get_setting(key, "")
    except Exception:
        return default
    try:
        return float(str(raw).strip()) if str(raw).strip() else default
    except (TypeError, ValueError):
        return default


async def cooldown_left(user_id: int) -> int:
    """دقیقه‌های باقی‌مانده تا خرابکاری بعدی (۰ = آزاد)."""
    minutes = int(await _num(MISSILE_COOLDOWN_KEY, DEFAULT_COOLDOWN_MIN))
    if minutes <= 0:
        return 0
    row = await db.fetchone(
        "SELECT last_at FROM sabotage_ops WHERE attacker_id=? "
        "ORDER BY id DESC LIMIT 1", (user_id,))
    if not row or not row.get("last_at"):
        return 0
    try:
        from core.utils import now, parse
        then = parse(row["last_at"])
        if not then:
            return 0
        used = (now() - then).total_seconds() / 60
    except Exception:
        return 0
    return max(0, int(round(minutes - used)))


async def weapon_categories(attacker_id: int) -> set[str]:
    """دسته‌های سلاحی که مهاجم در اختیار دارد (missile/air/space/cyber…)."""
    try:
        rows = await db.fetchall(
            "SELECT c.key AS cat_key, e.name AS name, e.subcategory AS sub, "
            "a.quantity AS q FROM player_assets a "
            "JOIN equipment e ON e.id=a.item_id "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0",
            (attacker_id,))
    except Exception:
        return set()
    cats: set[str] = set()
    for r in rows:
        name = r.get("name") or ""
        # 🛡 سامانه‌های پدافندی سلاح تهاجمی نیستند (پاتریوت/اس‌۴۰۰/تور…)
        if _is_air_defense(name, r.get("sub")):
            continue
        if r.get("cat_key"):
            cats.add(str(r["cat_key"]))
        if "موشک" in name or "راکت" in name:
            cats.add("missile")
        if (r.get("sub") or "") in ("ballistic", "cruise"):
            cats.add("missile")
    return cats


AIR_DEFENSE_WORDS = ("پدافند", "پاتریوت", "اس ۴۰۰", "اس۴۰۰", "تور", "فایروال",
                     "سپر", "رهگیر")


def _is_air_defense(name: str, sub: str | None = None) -> bool:
    """آیا این تجهیز، سامانهٔ پدافندی است (نه سلاح تهاجمی)؟"""
    text = (name or "").lower()
    if (sub or "").lower() == "air_defense":
        return True
    return any(w in text for w in AIR_DEFENSE_WORDS)


async def air_shield(defender_id: int) -> int:
    """🛡 خالص پدافند هوایی کشور (بدون استحکام سازه‌های دیگر)."""
    try:
        rows = await db.fetchall(
            "SELECT e.defense_power AS d, e.name AS name, e.subcategory AS sub, "
            "a.quantity AS q FROM player_assets a "
            "JOIN equipment e ON e.id=a.item_id "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0 "
            "AND (LOWER(COALESCE(e.subcategory,''))='air_defense' OR c.key='air' "
            "     OR e.name LIKE '%پدافند%' OR e.name LIKE '%پاتریوت%' "
            "     OR e.name LIKE '%اس ۴۰۰%' OR e.name LIKE '%تور%')", (defender_id,))
        return sum((r["d"] or 0) * (r["q"] or 0) for r in rows)
    except Exception:
        return 0


async def can_sabotage(attacker_id: int, kind: str) -> tuple[bool, str]:
    """آیا مهاجم سلاح مناسب این هدف را دارد؟"""
    info = TARGET_KINDS.get(kind)
    if not info:
        return False, "❌ هدف نامعتبر است."
    cats = await weapon_categories(attacker_id)
    if not cats & set(info["needs"]):
        need_fa = {"missile": "🚀 موشک بالستیک/کروز", "air": "✈️ بمب‌افکن",
                   "space": "🛰 تسلیحات فضایی", "cyber": "🕶 تجهیزات سایبری"}
        wanted = " یا ".join(need_fa.get(k, k) for k in info["needs"])
        return False, (f"❌ برای زدن {info['title']} به {wanted} نیاز دارید "
                       f"(از 🎖 پادگان بخرید).")
    left = await cooldown_left(attacker_id)
    if left > 0:
        return False, (f"⏱ پس از هر خرابکاری باید {left} دقیقه صبر کنید "
                       f"(کول‌داون {int(await _num(MISSILE_COOLDOWN_KEY, DEFAULT_COOLDOWN_MIN))} دقیقه).")
    return True, ""


# ─── فهرست سازه‌های دشمن ───

async def _buildings_by_sector(user_id: int, sector: str) -> list[dict]:
    """سازه‌های یک بخش (power/water/gas/oil) با تعداد و استحکام."""
    try:
        rows = await db.fetchall(
            "SELECT b.id, b.name, b.emoji, b.sector, SUM(a.quantity) AS qty "
            "FROM player_assets a JOIN buildings b ON b.id=a.item_id "
            "WHERE a.user_id=? AND a.item_type='building' AND b.sector=? "
            "AND a.quantity>0 GROUP BY b.id ORDER BY b.id", (user_id, sector))
    except Exception:
        return []
    return [dict(r) for r in rows if int(r.get("qty") or 0) > 0]


async def facilities(defender_id: int) -> list[dict]:
    """🎯 همهٔ سازه‌های قابل هدف‌گیری یک کشور با وضعیت سلامت."""
    from core import nuclear as nuke

    out: list[dict] = []

    # 🛢 نفت و 🏭 پالایش/مخازن
    for sector, kind, title in (("oil", "oil", "🛢 دکل نفتی"),
                                ("oil", "industry", "🏭 پالایشگاه و مخازن")):
        rows = await _buildings_by_sector(defender_id, sector)
        for r in rows:
            is_rig = "دکل" in (r.get("name") or "")
            if (kind == "oil") != is_rig:
                continue
            out.append({
                "kind": kind, "item_type": "building", "item_id": r["id"],
                "name": f"{r.get('emoji') or ''} {r.get('name')}".strip(),
                "qty": int(r["qty"]), "hp": int(TARGET_KINDS[kind]["hp"]),
                "emoji": r.get("emoji") or TARGET_KINDS[kind]["emoji"],
                "group": "oil",
            })

    # ⚡💧🔥 تأسیسات خدماتی
    for sector, kind in (("power", "power"), ("water", "water"), ("gas", "gas")):
        for r in await _buildings_by_sector(defender_id, sector):
            out.append({
                "kind": kind, "item_type": "building", "item_id": r["id"],
                "name": f"{r.get('emoji') or ''} {r.get('name')}".strip(),
                "qty": int(r["qty"]), "hp": int(TARGET_KINDS[kind]["hp"]),
                "emoji": r.get("emoji") or TARGET_KINDS[kind]["emoji"],
                "group": kind,
            })

    # ☢️ تأسیسات هسته‌ای
    try:
        site = await nuke.sync_stage(defender_id)
    except Exception:
        site = None
    if site and int(site.get("active") or 0) and int(site.get("hp") or 0) > 0:
        out.append({
            "kind": "nuclear", "item_type": "nuclear", "item_id": 0,
            "name": f"{site.get('emoji') or '☢️'} {site.get('kind')}",
            "qty": 1, "hp": int(site.get("hp") or 0),
            "max_hp": int(site.get("max_hp") or 100),
            "emoji": site.get("emoji") or "☢️", "group": "nuclear",
        })

    # 🏢 شرکت‌ها
    try:
        rows = await db.fetchall(
            "SELECT c.id, c.name, ct.emoji AS emoji, c.income_daily FROM companies c "
            "LEFT JOIN company_types ct ON ct.id=c.type_id WHERE c.owner_id=? ORDER BY c.id",
            (defender_id,))
    except Exception:
        rows = []
    for r in rows:
        out.append({
            "kind": "company", "item_type": "company", "item_id": r["id"],
            "name": f"{r.get('emoji') or '🏢'} {r.get('name') or 'شرکت'}",
            "qty": 1, "hp": int(TARGET_KINDS["company"]["hp"]),
            "emoji": r.get("emoji") or "🏢", "group": "company",
        })

    # 🌐 اینترنت
    try:
        row = await db.fetchone("SELECT level FROM internet_infra WHERE user_id=?",
                                (defender_id,))
        level = int((row or {}).get("level") or 0)
    except Exception:
        level = 0
    if level > 0:
        out.append({
            "kind": "internet", "item_type": "internet", "item_id": 0,
            "name": f"🌐 زیرساخت اینترنت (سطح {level})", "qty": 1,
            "hp": int(TARGET_KINDS["internet"]["hp"]), "emoji": "🌐",
            "group": "internet", "level": level,
        })

    # 🎖 پدافند هوایی
    try:
        rows = await db.fetchall(
            "SELECT e.id, e.name, e.emoji, e.defense_power AS d, SUM(a.quantity) AS qty "
            "FROM player_assets a JOIN equipment e ON e.id=a.item_id "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0 "
            "AND (LOWER(COALESCE(e.subcategory,''))='air_defense' OR c.key='air' "
            "     OR e.name LIKE '%پدافند%' OR e.name LIKE '%پاتریوت%' "
            "     OR e.name LIKE '%اس ۴۰۰%' OR e.name LIKE '%تور%') "
            "GROUP BY e.id ORDER BY e.id", (defender_id,))
    except Exception:
        rows = []
    for r in rows:
        out.append({
            "kind": "airdef", "item_type": "equipment", "item_id": r["id"],
            "name": f"{r.get('emoji') or '🎖'} {r.get('name')}", "qty": int(r["qty"]),
            "hp": int(TARGET_KINDS["airdef"]["hp"]), "emoji": r.get("emoji") or "🎖",
            "group": "airdef",
        })
    return out


async def targets_summary(attacker_id: int) -> list[dict]:
    """کشورهای دارای سازهٔ قابل هدف + شماری از دارایی‌هایشان."""
    try:
        rows = await db.fetchall(
            "SELECT u.id, c.name, c.flag FROM users u JOIN countries c ON c.id=u.country_id "
            "WHERE u.banned=0 AND u.id!=? ORDER BY c.population DESC", (attacker_id,))
    except Exception:
        return []
    out = []
    for r in rows:
        fac = await facilities(r["id"])
        if not fac:
            continue
        counts: dict[str, int] = {}
        for f in fac:
            counts[f["kind"]] = counts.get(f["kind"], 0) + int(f["qty"])
        out.append({"user_id": int(r["id"]), "name": r["name"], "flag": r["flag"],
                    "counts": counts, "total": len(fac)})
    return out


# ─── توان و پدافند ───

async def target_defense(defender_id: int, facility: dict) -> int:
    """🛡 پدافند هدف = استحکام خود سازه + پدافند هوایی مدافع (کشور)."""
    from core import nuclear as nuke

    base = int(facility.get("hp") or 60) * 220
    # پدافند اختصاصی تأسیسات هسته‌ای (موتور خودش)
    if facility["kind"] == "nuclear":
        try:
            return int(base + await nuke.defense_power(defender_id))
        except Exception:
            return base
    air = await air_shield(defender_id)
    # سازه‌های غیرهسته‌ای از ۴۰٪ پدافند هوایی کشور بهره می‌برند
    base += int(air * 0.4)
    # ⛓ کشور فرسوده پدافند ضعیف‌تری دارد
    try:
        from core import attrition as attr
        base = int(base * max(0.35, await attr.defense_multiplier(defender_id)))
    except Exception:
        pass
    return max(1, base)


async def attack_power(attacker_id: int, kind: str) -> int:
    """🚀 توان آتش علیه یک نوع هدف."""
    from core.economy import army_power

    cats = await weapon_categories(attacker_id)
    atk_power, _d, cyber = await army_power(attacker_id)
    try:
        rows = await db.fetchall(
            "SELECT e.attack_power AS a, e.cyber_power AS c, a2.quantity AS q, "
            "c2.key AS cat_key FROM player_assets a2 "
            "JOIN equipment e ON e.id=a2.item_id "
            "LEFT JOIN equipment_categories c2 ON c2.id=e.category_id "
            "WHERE a2.user_id=? AND a2.item_type='equipment' AND a2.quantity>0",
            (attacker_id,))
    except Exception:
        rows = []
    offense_rows = [r for r in rows if not _is_air_defense(r.get("name") or "", None)]
    long_power = sum((r["a"] or 0) * (r["q"] or 0) for r in offense_rows
                     if r.get("cat_key") in ("missile", "air", "space"))
    cyber_power = sum((r["c"] or 0) * (r["q"] or 0) for r in rows)
    if kind in ("internet", "company"):
        # 🕶 اهداف داده‌محور: قدرت سایبری تعیین‌کننده است
        power = cyber_power * 0.8 + cyber * 0.5 + long_power * 0.15
    elif kind == "airdef":
        power = long_power * 1.2 + cyber_power * 0.35
    else:
        power = long_power * 1.0 + atk_power * 0.25 + cyber_power * 0.1
    # ⛓ مهاجم فرسوده کمتر می‌تواند بزند
    try:
        from core import attrition as attr
        power *= max(0.4, 1.0 - (await attr.wear_of(attacker_id)) / 200)
    except Exception:
        pass
    if "cyber" in cats:
        power += 500
    return max(1, int(power))


async def outlook(attacker_id: int, defender_id: int, kind: str,
                  item_id: int) -> dict:
    """پیش‌بینی حمله به یک سازه (هیچ‌چیز تغییر نمی‌کند)."""
    facs = await facilities(defender_id)
    target = next((f for f in facs
                   if f["kind"] == kind and int(f["item_id"]) == int(item_id)), None)
    info = TARGET_KINDS.get(kind, {})
    if not target:
        return {"ok": False, "error": "این سازه دیگر وجود ندارد.", "facility": None}
    atk = await attack_power(attacker_id, kind)
    dfn = await target_defense(defender_id, target)
    chance = max(5.0, min(95.0, 100.0 * atk / max(1.0, atk + dfn)))
    return {"ok": True, "facility": target, "atk": atk, "def": dfn,
            "chance": round(chance, 1), "info": info, "kind": kind}


async def _remove_some(user_id: int, item_type: str, item_id: int,
                       qty: int) -> int:
    """حذف تعدادی از دارایی؛ خروجی: تعداد واقعی حذف‌شده."""
    from core.economy import sub_asset
    try:
        row = await db.fetchone(
            "SELECT quantity FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
            (user_id, item_type, item_id))
        have = int((row or {}).get("quantity") or 0)
    except Exception:
        have = 0
    take = max(0, min(qty, have))
    if take <= 0:
        return 0
    ok = await sub_asset(user_id, item_type, item_id, take)
    return take if ok else 0


async def sabotage(bot, attacker_id: int, defender_id: int, kind: str,
                   item_id: int = 0) -> str:
    """🎯 اجرای خرابکاری در یک سازه. خروجی: متن گزارش کامل."""
    from core.economy import announce, get_country
    from core.events import log_event

    if attacker_id == defender_id:
        return "❌ نمی‌توانید تأسیسات خودتان را هدف بگیرید."

    ok, err = await can_sabotage(attacker_id, kind)
    if not ok:
        return err

    look = await outlook(attacker_id, defender_id, kind, item_id)
    if not look.get("ok"):
        return f"❌ {look.get('error') or 'هدف یافت نشد.'}"

    target = look["facility"]
    info = look["info"]
    a_country = await get_country(attacker_id)
    d_country = await get_country(defender_id)
    a_name = f"{a_country['flag']} <b>{a_country['name']}</b>" if a_country else "مهاجم"
    d_name = f"{d_country['flag']} <b>{d_country['name']}</b>" if d_country else "مدافع"

    # ☢️ تأسیسات هسته‌ای موتور اختصاصی خودش را دارد
    if kind == "nuclear":
        from core import nuclear as nuke
        report = await nuke.strike(bot, attacker_id, defender_id)
        await _record(attacker_id, defender_id, kind, item_id, 1, report)
        await _add_wear(defender_id, attacker_id,
                        await _num("sabotage_wear_add", DEFAULT_MAX_WEAR_ADD))
        return report

    chance = look["chance"] / 100
    success = random.random() < chance
    dmg_ratio = min(1.0, 0.45 + 0.55 * (look["atk"] / max(1, look["atk"] + look["def"])))

    lines = [
        f"{info['emoji']} <b>خرابکاری در {info['title']}</b>",
        "",
        f"🎯 مهاجم: {a_name}",
        f"🏭 هدف: {d_name} — {target['name']}",
        "",
        f"🚀 توان حمله: <b>{fmt(look['atk'])}</b>",
        f"🛡 پدافند هدف: <b>{fmt(look['def'])}</b>",
        f"🎲 احتمال اصابت: <b>{look['chance']}%</b>",
        "",
    ]
    destroyed = 0
    if not success:
        lines += [
            "🛡 <b>پدافند هدف حمله را رهگیری کرد!</b>",
            "  • سازه‌های دشمن سالم ماندند.",
            "  • هیچ خسارتی وارد نشد.",
        ]
        await _record(attacker_id, defender_id, kind, item_id, 0, "دفع شد")
        await log_event("war", f"🛡 پدافند {d_country['name'] if d_country else defender_id} "
                              f"حمله به {info['title']} را دفع کرد")
        return "\n".join(lines)

    # ─── آسیب بر اساس نوع هدف ───
    if kind in ("oil", "power", "water", "gas", "industry"):
        take = 1 if dmg_ratio < 0.9 else min(2, int(target["qty"]))
        destroyed = await _remove_some(defender_id, "building", target["item_id"], take)
        sector_fa = {"oil": "نفت", "power": "برق", "water": "آب", "gas": "گاز",
                     "industry": "پالایش"}[kind]
        lines += [
            "💥 <b>اصابت مستقیم!</b>",
            f"  • سازه‌های نابودشده: <b>{fmt(destroyed)}</b> از {fmt(target['qty'])}",
        ]
        if kind == "oil":
            lines.append("  • 📉 استخراج و درآمد نفتی دشمن افت کرد.")
        elif kind in ("power", "water", "gas"):
            lines.append(f"  • ⚠️ ظرفیت {sector_fa} کشور کم شد — خطر قطعی و افت رضایت.")
            try:
                await db.execute(
                    f"UPDATE states SET blackout_{kind}=MIN(24, COALESCE(blackout_{kind},0)+3) "
                    "WHERE user_id=?", (defender_id,))
            except Exception:
                pass
        else:
            lines.append("  • 📉 ارزش صادرات نفت و ذخایر راهبردی افت کرد.")
    elif kind == "company":
        try:
            row = await db.fetchone(
                "SELECT * FROM companies WHERE id=? AND owner_id=?",
                (target["item_id"], defender_id))
        except Exception:
            row = None
        if row:
            await db.execute("DELETE FROM companies WHERE id=?", (target["item_id"],))
            destroyed = 1
            lines += ["💥 <b>شرکت منهدم شد!</b>",
                      f"  • 🏢 <b>{row['name'] or 'شرکت'}</b> از بین رفت."]
        else:
            lines.append("❌ شرکت پیدا نشد (شاید پیش‌تر نابود شده).")
    elif kind == "internet":
        try:
            row = await db.fetchone("SELECT level FROM internet_infra WHERE user_id=?",
                                    (defender_id,))
            level = int((row or {}).get("level") or 0)
            new_level = max(0, level - 1)
            await db.execute("UPDATE internet_infra SET level=?, updated_at=? WHERE user_id=?",
                             (new_level, iso(), defender_id))
            destroyed = 1 if new_level < level else 0
            lines += ["💥 <b>حمله سایبری موفق!</b>",
                      f"  • 🌐 سطح اینترنت: {level} → <b>{new_level}</b>",
                      "  • پوشش اینترنت و ضریب درآمد دشمن افت کرد."]
        except Exception:
            log.exception("sabotage internet failed")
    elif kind == "airdef":
        take = max(1, int(target["qty"] * (0.5 if dmg_ratio < 0.9 else 1.0)))
        destroyed = await _remove_some(defender_id, "equipment", target["item_id"], take)
        lines += ["💥 <b>پدافند هوایی دشمن شکست!</b>",
                  f"  • 🎖 تجهیزات پدافندی نابودشده: <b>{fmt(destroyed)}</b>",
                  "  • 🛡 برای حملات بعدی، سپر دشمن ضعیف‌تر است."]

    # ─── پیامدهای سیاسی و فرسایش ───
    sat_hit = await _num("sabotage_satisfaction_hit", DEFAULT_SAT_HIT)
    if sat_hit:
        try:
            await db.execute(
                "UPDATE states SET satisfaction=MAX(0, satisfaction-?) WHERE user_id=?",
                (sat_hit * (1 + destroyed), defender_id))
        except Exception:
            pass
        lines.append(f"\n😞 رضایت مردم مدافع: <b>-{round(sat_hit * (1 + destroyed), 1)}</b>")
    wear_amount = await _num("sabotage_wear_add", DEFAULT_MAX_WEAR_ADD)
    wear_add = await _add_wear(defender_id, attacker_id, wear_amount)
    if wear_add:
        lines.append(f"⛓ فرسایش کشور مدافع: <b>+{round(wear_add, 1)}٪</b>")

    await _record(attacker_id, defender_id, kind, item_id, 1,
                  f"{destroyed} سازه نابود شد")
    try:
        await log_event("war", f"{info['emoji']} {a_name} به {info['title']} "
                              f"{d_name} حمله کرد — {destroyed} سازه نابود شد")
    except Exception:
        pass
    try:
        await announce(
            bot,
            f"{info['emoji']} <b>خرابکاری در زیرساخت‌های یک کشور</b>\n\n"
            f"🎯 {a_name} به {info['title']} {d_name} حمله کرد.\n"
            f"💥 سازه‌های نابودشده: <b>{fmt(destroyed)}</b>\n"
            f"⚠️ {info['desc']}",
            section="war_attack")
    except Exception:
        pass
    return "\n".join(lines)


async def _record(attacker_id: int, defender_id: int, kind: str, item_id: int,
                  success: int, note: str) -> None:
    try:
        await db.execute(
            "INSERT INTO sabotage_ops(attacker_id, defender_id, kind, item_id, success, "
            "note, last_at) VALUES(?,?,?,?,?,?,?)",
            (attacker_id, defender_id, kind, int(item_id or 0), int(success),
             (note or "")[:200], iso()))
    except Exception:
        log.exception("sabotage_ops insert failed")


async def _add_wear(defender_id: int, attacker_id: int, amount: float) -> float:
    try:
        from core import attrition as attr
        before = await attr.wear_of(defender_id)
        await attr.add_strike(defender_id, attacker_id, amount)
        after = await attr.wear_of(defender_id)
        return max(0.0, after - before)
    except Exception:
        return 0.0


# ─── تاریخچه و متن‌ها ───

async def history(user_id: int, limit: int = 6) -> list[dict]:
    try:
        return await db.fetchall(
            "SELECT * FROM sabotage_ops WHERE attacker_id=? OR defender_id=? "
            "ORDER BY id DESC LIMIT ?", (user_id, user_id, limit))
    except Exception:
        return []


async def my_damage_text(user_id: int) -> str:
    """📋 خلاصهٔ خسارت‌های واردشده به کشور بازیکن (برای مدافع)."""
    rows = await history(user_id, 8)
    if not rows:
        return "🛡 <b>هیچ خرابکاری‌ای علیه شما ثبت نشده است.</b>"
    lines = ["📋 <b>آخرین خرابکاری‌ها روی کشور شما</b>", ""]
    for r in rows:
        info = TARGET_KINDS.get(r["kind"], {})
        who = "شما" if int(r["attacker_id"] or 0) == user_id else fmt(r["attacker_id"])
        mark = "💥" if int(r["success"] or 0) else "🛡"
        lines.append(f"{mark} {info.get('title', r['kind'])} — مهاجم {who} — "
                     f"{r.get('note') or ''}")
    return "\n".join(lines)


async def rebuild_options(user_id: int) -> list[dict]:
    """🔧 سازه‌هایی که مدافع می‌تواند بازسازی/تعمیر کند."""
    opts: list[dict] = []
    try:
        row = await db.fetchone("SELECT level FROM internet_infra WHERE user_id=?",
                                (user_id,))
        level = int((row or {}).get("level") or 0)
        top = 5
        try:
            from core.internet import max_level
            top = await max_level()
        except Exception:
            pass
        if level < top:
            opts.append({"kind": "internet", "title": "🌐 بازسازی زیرساخت اینترنت",
                         "cost_money": 40_000_000 * (level + 1), "cost_mats": 120 * (level + 1),
                         "level": level})
    except Exception:
        pass
    try:
        rows = await db.fetchall(
            "SELECT b.id, b.name, b.emoji, b.cost_money, b.sector FROM buildings b "
            "WHERE b.sector IN ('power','water','gas','oil') ORDER BY b.cost_money")
        lost = await db.fetchall(
            "SELECT kind, item_id, COUNT(*) c FROM sabotage_ops "
            "WHERE defender_id=? AND success=1 AND kind IN "
            "('oil','power','water','gas','industry') GROUP BY kind, item_id "
            "ORDER BY MAX(id) DESC LIMIT 5", (user_id,))
        by_id = {int(r["id"]): r for r in rows}
        for l in lost:
            b = by_id.get(int(l["item_id"] or 0))
            if not b:
                continue
            opts.append({
                "kind": l["kind"], "item_id": int(l["item_id"]),
                "title": f"🔧 بازسازی {b['emoji']} {b['name']}",
                "cost_money": int((b["cost_money"] or 0) // 2),
                "cost_mats": 50,
                "building_id": int(b["id"]),
            })
    except Exception:
        log.exception("rebuild_options failed")
    return opts


async def rebuild(user_id: int, kind: str, item_id: int = 0) -> tuple[bool, str]:
    """🔧 بازسازی یک سازهٔ آسیب‌دیده با هزینهٔ نصف قیمت ساخت."""
    from core.economy import add_asset

    opts = await rebuild_options(user_id)
    choice = next((o for o in opts
                   if o["kind"] == kind
                   and int(o.get("item_id") or 0) == int(item_id or 0)), None)
    if not choice:
        return False, "❌ این سازه برای بازسازی موجود نیست."
    cost = int(choice["cost_money"])
    mats = int(choice.get("cost_mats") or 0)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    st = await db.fetchone("SELECT COALESCE(materials,0) m FROM states WHERE user_id=?",
                           (user_id,))
    have_mats = int((st or {}).get("m") or 0)
    if money < cost:
        return False, (f"❌ بودجهٔ کافی ندارید.\n💰 نیاز: <b>{fmt(cost)}</b> — "
                       f"خزانه: {fmt(money)}")
    if have_mats < mats:
        return False, (f"❌ مصالح کافی ندارید.\n🧱 نیاز: <b>{fmt(mats)}</b> — "
                       f"موجودی: {fmt(have_mats)}")
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    if mats:
        await db.execute("UPDATE states SET materials=MAX(0, COALESCE(materials,0)-?) "
                         "WHERE user_id=?", (mats, user_id))

    if kind == "internet":
        try:
            row = await db.fetchone("SELECT level FROM internet_infra WHERE user_id=?",
                                    (user_id,))
            level = int((row or {}).get("level") or 0)
            if row:
                await db.execute("UPDATE internet_infra SET level=?, updated_at=? "
                                 "WHERE user_id=?", (level + 1, iso(), user_id))
            else:
                await db.execute("INSERT INTO internet_infra(user_id, level, updated_at) "
                                 "VALUES(?,1,?)", (user_id, iso()))
        except Exception:
            log.exception("rebuild internet failed")
        return True, (f"✅ زیرساخت اینترنت بازسازی شد (سطح {level + 1}).\n"
                      f"💰 هزینه: {fmt(cost)} | 🧱 مصالح: {fmt(mats)}")

    bid = int(choice.get("building_id") or 0)
    if not bid:
        return False, "❌ سازه نامعتبر است."
    await add_asset(user_id, "building", bid, 1)
    return True, (f"✅ <b>{choice['title']}</b> بازسازی شد و به دارایی‌های شما برگشت.\n"
                  f"💰 هزینه: {fmt(cost)} | 🧱 مصالح: {fmt(mats)}")


async def targets_text(attacker_id: int, defender_id: int) -> str:
    """متن فهرست سازه‌های یک کشور برای انتخاب هدف."""
    from core.economy import get_country

    facs = await facilities(defender_id)
    c = await get_country(defender_id)
    head = (f"🎯 <b>سازه‌های {c['flag']} {c['name']}</b>"
            if c else "🎯 <b>سازه‌های دشمن</b>")
    if not facs:
        return head + "\n\n— این کشور هیچ سازه‌ای برای هدف قرار دادن ندارد —"
    lines = [head, "", "روی هر سازه بزنید تا شانس اصابت را ببینید:", ""]
    for f in facs:
        lines.append(f"{f['emoji']} <b>{f['name']}</b> — موجودی: {fmt(f['qty'])}")
    return "\n".join(lines)

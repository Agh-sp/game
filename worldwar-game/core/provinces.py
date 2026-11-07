"""استان‌ها — هر کشور ۵ استان دارد؛ هر حملهٔ موفق یک استان می‌گیرد.

منطق:
- هر کشور با ۵ استان آغاز می‌شود (`BASE_PROVINCES`).
- در هر نبرد پیروز، مهاجم **یک** استان از مدافع تصاحب می‌کند.
- اگر مدافع پدافند قوی داشته باشد، شانس دفاع دارد و استان از دست نمی‌رود.
- وقتی مدافع همهٔ استان‌های خودش را از دست بدهد، کشور **سقوط** می‌کند:
  بازیکن مالکیت کشور را از دست می‌دهد و می‌تواند کشور تازه‌ای انتخاب کند.
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting
from core.utils import iso

log = logging.getLogger(__name__)

BASE_PROVINCES = 5
NAME_TEMPLATES = [
    "استان مرکزی", "استان شمالی", "استان جنوبی", "استان شرقی", "استان غربی",
    "استان ساحلی", "استان کوهستانی", "استان صنعتی", "استان کشاورزی",
    "استان مرزی", "استان کویری", "استان جنگلی",
]


async def ensure_provinces() -> int:
    """ساخت استان‌های پایه برای هر کشوری که هنوز استان ندارد (idempotent).

    خروجی: تعداد استان‌های ساخته‌شده.
    """
    created = 0
    countries = await db.fetchall(
        "SELECT id, name, owner_id FROM countries WHERE is_active=1")
    for c in countries:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM provinces WHERE country_id=?", (c["id"],))
        have = int((row or {}).get("c") or 0)
        if have >= BASE_PROVINCES:
            continue
        for idx in range(have, BASE_PROVINCES):
            name = NAME_TEMPLATES[idx % len(NAME_TEMPLATES)]
            await db.execute(
                "INSERT OR IGNORE INTO provinces(country_id, idx, name, owner_id) "
                "VALUES(?,?,?,?)",
                (c["id"], idx, name, c["owner_id"]))
            created += 1
    # همگام‌سازی مالکیت استان‌ها با صاحبان واقعی کشورها
    await sync_owners()
    # همگام‌سازی شمارندهٔ استان‌های هر کشور
    await sync_counts()
    return created


async def sync_owners() -> None:
    """استان‌های بدون مالک را به صاحب واقعی کشور وصل می‌کند.

    مالک واقعی کشور یا از `countries.owner_id` می‌آید یا از `users.country_id`
    (بازی این دو را جدا نگه می‌دارد). اگر کشوری صاحب نداشته باشد،
    استان‌هایش آزاد می‌مانند.
    """
    # ۱) کشورهایی که صاحبشان در users مشخص است
    rows = await db.fetchall(
        "SELECT c.id AS cid, u.id AS uid FROM countries c "
        "JOIN users u ON u.country_id=c.id WHERE u.banned=0")
    for r in rows:
        await db.execute(
            "UPDATE provinces SET owner_id=? WHERE country_id=? AND owner_id IS NULL",
            (r["uid"], r["cid"]))
    # ۲) کشورهایی که در countries.owner_id صاحب دارند
    rows2 = await db.fetchall(
        "SELECT id, owner_id FROM countries WHERE owner_id IS NOT NULL")
    for r in rows2:
        await db.execute(
            "UPDATE provinces SET owner_id=? WHERE country_id=? AND owner_id IS NULL",
            (r["owner_id"], r["id"]))
    # ۳) کشورهای بدون صاحب → استان‌هایشان آزاد
    await db.execute(
        "UPDATE provinces SET owner_id=NULL WHERE country_id IN ("
        "  SELECT c.id FROM countries c WHERE c.owner_id IS NULL "
        "  AND NOT EXISTS (SELECT 1 FROM users u WHERE u.country_id=c.id AND u.banned=0))")


async def sync_counts() -> None:
    """به‌روزرسانی `countries.province_count` بر اساس استان‌های تحت مالکیت صاحب کشور."""
    await db.execute(
        "UPDATE countries SET province_count = ("
        "  SELECT COUNT(*) FROM provinces p WHERE p.owner_id = countries.owner_id"
        ") WHERE owner_id IS NOT NULL")
    # کشورهای بدون بازیکن: همهٔ استان‌ها آزاد
    await db.execute(
        "UPDATE countries SET province_count = ("
        "  SELECT COUNT(*) FROM provinces p WHERE p.country_id = countries.id"
        ") WHERE owner_id IS NULL")


async def provinces_of(country_id: int) -> list[dict]:
    return await db.fetchall(
        "SELECT * FROM provinces WHERE country_id=? ORDER BY idx", (country_id,))


async def owned_provinces(user_id: int) -> list[dict]:
    """استان‌هایی که این بازیکن در اختیار دارد (از هر کشور)."""
    return await db.fetchall(
        "SELECT * FROM provinces WHERE owner_id=? ORDER BY country_id, idx", (user_id,))


async def province_summary(user_id: int) -> dict:
    """خلاصهٔ استان‌های بازیکن برای نمایش.

    🐞 نکتهٔ مهم (باگ گزارش‌شده): اگر برای کشوری استان ساخته نشده باشد
    (مثلاً دیتابیس قدیمی یا کشوری که تازه به بازیکن داده شده)، بازیکن
    «سقوط‌کرده» نشان داده می‌شد در حالی که کشورش سالم بود. این‌جا ابتدا
    استان‌های پایه ساخته و مالکیت هم‌تراز می‌شود، سپس سقوط تشخیص داده می‌شود.
    """
    rows = await owned_provinces(user_id)
    country = await db.fetchone(
        "SELECT c.id, c.name, c.flag FROM countries c JOIN users u ON u.country_id=c.id "
        "WHERE u.id=?", (user_id,))

    # 🛠 خودترمیمی: اگر بازیکن کشور دارد ولی هیچ استانی از کشور خودش در اختیار
    #    ندارد، استان‌های «بدون مالک» آن کشور به او داده می‌شوند. توجه: استانِ
    #    تصاحب‌شده مالک دارد (مهاجم)، پس سقوط واقعی هرگز با این کار باطل نمی‌شود.
    has_home_rows = country and any(r["country_id"] == country["id"] for r in rows)
    if country and not has_home_rows:
        try:
            await ensure_country_provinces(country["id"], user_id)
            rows = await owned_provinces(user_id)
        except Exception:
            pass

    by_country: dict[int, int] = {}
    for r in rows:
        by_country[r["country_id"]] = by_country.get(r["country_id"], 0) + 1
    home = by_country.get(country["id"], 0) if country else 0
    return {"total": len(rows), "home": home, "by_country": by_country,
            "country": country, "collapsed": home == 0 and len(rows) == 0}


async def ensure_country_provinces(country_id: int, owner_id: int | None = None,
                                   normalize: bool = False) -> int:
    """ساخت استان‌های پایهٔ یک کشور (idempotent) و دادنشان به مالک آن.

    اگر کشوری کمتر از `BASE_PROVINCES` استان داشته باشد، استان‌های کم ساخته
    می‌شوند. استان‌های بدون مالکِ این کشور به مالک داده می‌شوند.

    `normalize=True` هنگام واگذاری کشور به بازیکن تازه استفاده می‌شود: همهٔ
    استان‌های آن کشور به مالک جدید داده می‌شوند تا فرماندهٔ تازه با «کشور سقوط
    کرده» روبه‌رو نشود (باگ گزارش‌شده).

    خروجی: تعداد استان‌های ایجادشده.
    """
    created = 0
    row = await db.fetchone(
        "SELECT COUNT(*) c FROM provinces WHERE country_id=?", (country_id,))
    have = int((row or {}).get("c") or 0)
    if have < BASE_PROVINCES:
        for idx in range(have, BASE_PROVINCES):
            name = NAME_TEMPLATES[idx % len(NAME_TEMPLATES)]
            await db.execute(
                "INSERT OR IGNORE INTO provinces(country_id, idx, name, owner_id) "
                "VALUES(?,?,?,?)",
                (country_id, idx, name, owner_id))
            created += 1

    owner = owner_id
    if owner is None:
        c = await db.fetchone("SELECT owner_id FROM countries WHERE id=?", (country_id,))
        owner = (c or {}).get("owner_id")
        if not owner:
            u = await db.fetchone(
                "SELECT id FROM users WHERE country_id=? AND banned=0", (country_id,))
            owner = (u or {}).get("id")
    if owner:
        if normalize:
            # 🏳 کشور تازه واگذار شد: همهٔ استان‌هایش به فرماندهٔ جدید می‌رسد
            await db.execute(
                "UPDATE provinces SET owner_id=?, captured_at=NULL WHERE country_id=?",
                (owner, country_id))
        else:
            await db.execute(
                "UPDATE provinces SET owner_id=? WHERE country_id=? AND owner_id IS NULL",
                (owner, country_id))
    await sync_counts()
    return created


async def defender_can_hold(defender_id: int, attacker_power: float,
                           defender_power: float, conquest: bool = False) -> bool:
    """آیا مدافع می‌تواند استان را نگه دارد؟

    شانس دفاع = نسبت توان دفاعی به توان مهاجم، محدود به بازهٔ تنظیم‌شده.
    در **حملهٔ تسخیر** شانس دفاع مدافع کمتر می‌شود (`capture_province_bonus` درصد)
    تا تصرف استان واقعاً ممکن و ارزشمند باشد.
    """
    lo = float(await get_setting("province_defense_min_chance", "10")) / 100
    hi = float(await get_setting("province_defense_max_chance", "70")) / 100
    # ⛓ کشور فرسوده استان را سخت‌تر نگه می‌دارد
    try:
        from core import attrition as _attr
        mult = await _attr.province_defense_multiplier(defender_id)
        lo, hi = lo * mult, hi * mult
    except Exception:
        pass
    if defender_power <= 0 or attacker_power <= 0:
        return False
    ratio = defender_power / attacker_power
    chance = max(lo, min(hi, ratio * 0.5))
    if conquest:
        bonus = float(await get_setting("capture_province_bonus", "15")) / 100
        chance = max(lo * 0.4, chance - bonus)
    return random.random() < chance


async def capture_province(defender_id: int, attacker_id: int,
                           war_id: int | None = None) -> dict | None:
    """تصاحب یک استان از مدافع و انتقال به مهاجم.

    خروجی: dict استان تصاحب‌شده یا None اگر استان قابل تصاحب نبود.
    """
    row = await db.fetchone(
        "SELECT * FROM provinces WHERE owner_id=? ORDER BY RANDOM() LIMIT 1",
        (defender_id,))
    if not row:
        return None
    await db.execute(
        "UPDATE provinces SET owner_id=?, captured_at=? WHERE id=?",
        (attacker_id, iso(), row["id"]))
    await db.execute(
        "INSERT INTO provinces_history(province_id, from_owner, to_owner, war_id) "
        "VALUES(?,?,?,?)", (row["id"], defender_id, attacker_id, war_id))
    await sync_counts()
    return dict(row)


async def check_collapse(user_id: int) -> bool:
    """آیا کشور این بازیکن سقوط کرده (همهٔ استان‌ها از دست رفته)؟

    در صورت سقوط: کشور از مالکیت بازیکن خارج و آزاد می‌شود.
    خروجی: True اگر سقوط رخ داد.
    """
    summary = await province_summary(user_id)
    if not summary["collapsed"]:
        return False

    country = await db.fetchone(
        "SELECT c.* FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (user_id,))
    if country:
        await db.execute(
            "UPDATE countries SET owner_id=NULL, collapsed=1, province_count=0 WHERE id=?",
            (country["id"],))
        # استان‌های باقی‌ماندهٔ همان کشور آزاد می‌شوند
        await db.execute(
            "UPDATE provinces SET owner_id=NULL WHERE country_id=?", (country["id"],))
    await db.execute("UPDATE users SET country_id=NULL WHERE id=?", (user_id,))
    await db.execute("DELETE FROM companies WHERE owner_id=?", (user_id,))
    await db.execute("DELETE FROM player_assets WHERE user_id=?", (user_id,))
    try:
        from core.events import log_event
        await log_event(
            "war", f"💥 کشور {country['name'] if country else user_id} سقوط کرد — "
                   "همهٔ استان‌ها از دست رفت")
    except Exception:
        pass
    return True


async def infrastructure_strike(bot, attacker_id: int, defender_id: int,
                                atype: str, won: bool,
                                attacker_power: float = 0) -> str:
    """💥 حملهٔ عادی = فقط ضربه به زیرساخت‌ها (استان گرفته نمی‌شود).

    اثرهای واقعی و قابل مشاهده برای مدافع:
      • کاهش رضایت مردم (بین ۲ تا ۸ درصد بر اساس توان حمله)
      • تخریب ذخایر انرژی/آب/گاز و مصالح
      • از بین رفتن بخشی از قدرت دفاعی موقت (تضعیف پدافند)
    """
    from core.utils import fmt

    d_country = await db.fetchone(
        "SELECT c.flag, c.name FROM countries c JOIN users u ON u.country_id=c.id "
        "WHERE u.id=?", (defender_id,))
    d_name = f"{d_country['flag']} {d_country['name']}" if d_country else "مدافع"
    base = 2.0 if atype in ("cyber",) else 4.0
    if atype in ("air", "missile", "space", "mixed"):
        base += 2.0
    power_bonus = min(2.0, (attacker_power or 0) / 500_000)
    damage = round(base + power_bonus, 1)

    state = await db.fetchone("SELECT * FROM states WHERE user_id=?", (defender_id,)) or {}
    energy = int(state.get("energy") or 0)
    water = int(state.get("water") or 0)
    gas = int(state.get("gas") or 0)
    materials = int(state.get("materials") or 0)
    lost_res = {}
    for key, val in (("energy", energy), ("water", water), ("gas", gas),
                     ("materials", materials)):
        cut = int(val * min(0.35, 0.08 + power_bonus * 0.1))
        if cut > 0:
            lost_res[key] = cut
    if lost_res:
        sets = ", ".join(f"{k}=MAX(0, COALESCE({k},0)-?)" for k in lost_res)
        await db.execute(f"UPDATE states SET {sets} WHERE user_id=?",
                         (*lost_res.values(), defender_id))
    await db.execute(
        "UPDATE states SET satisfaction=MAX(0, satisfaction-?) WHERE user_id=?",
        (damage, defender_id))

    labels = {"energy": "برق", "water": "آب", "gas": "گاز", "materials": "مصالح"}
    res_txt = "، ".join(f"{labels[k]} {fmt(v)}" for k, v in lost_res.items()) or "—"
    return ("\n💥 <b>ضربه به زیرساخت‌ها (حملهٔ عادی):</b>\n"
            f"  • رضایت مردم {d_name}: <b>-{damage}٪</b>\n"
            f"  • ذخایر از دست رفته: {res_txt}\n"
            "  • 🗺 در حملهٔ عادی استان گرفته نمی‌شود؛ برای تصرف استان "
            "از «⚔️ حمله به قصد تسخیر» استفاده کنید.")


async def battle_province_effect(bot, attacker_id: int, defender_id: int,
                                 attacker_power: float, defender_power: float,
                                 won: bool, war_id: int | None = None,
                                 conquest: bool = False) -> str:
    """اعمال اثر استان‌ها پس از نبرد و برگرداندن یک خط توضیح برای گزارش.

    - فقط در **حملهٔ تسخیر** (`conquest=True`) استان گرفته می‌شود.
    - در حملهٔ عادی هیچ استانی منتقل نمی‌شود (فقط `infrastructure_strike`).
    - سقوط کشور مدافع در صورت از دست دادن همهٔ استان‌ها
    """
    a_country = await db.fetchone(
        "SELECT c.flag, c.name FROM countries c JOIN users u ON u.country_id=c.id "
        "WHERE u.id=?", (attacker_id,))
    d_country = await db.fetchone(
        "SELECT c.flag, c.name FROM countries c JOIN users u ON u.country_id=c.id "
        "WHERE u.id=?", (defender_id,))
    a_name = f"{a_country['flag']} {a_country['name']}" if a_country else "مهاجم"
    d_name = f"{d_country['flag']} {d_country['name']}" if d_country else "مدافع"

    if not won:
        return ""
    if not conquest:
        # حملهٔ عادی استان نمی‌گیرد
        return ""
    if await defender_can_hold(defender_id, attacker_power, defender_power,
                               conquest=True):
        return (f"\n🛡 <b>پدافند موفق:</b> {d_name} استان را حفظ کرد "
                f"(توان دفاعی {int(defender_power)} در برابر {int(attacker_power)}).")

    captured = await capture_province(defender_id, attacker_id, war_id)
    if not captured:
        return ""
    summary = await province_summary(attacker_id)
    line = (f"\n🗺 <b>استان تصاحب شد:</b> {captured['name']} از {d_name} "
            f"به {a_name} منتقل شد.\n"
            f"🏴 استان‌های شما: <b>{summary['home']}</b> (مجموع {summary['total']})")

    # ⛓ فرسایش با سقوط کامل کشور پاک می‌شود (کشور از نو آغاز می‌کند)
    try:
        from core import attrition as _attr
        await _attr.reset(defender_id)
    except Exception:
        pass

    collapsed = await check_collapse(defender_id)
    if collapsed:
        line += (f"\n\n💥 <b>سقوط {d_name}!</b> همهٔ استان‌ها از دست رفت؛ "
                 "کشور آزاد شد و فرمانده آن باید کشور تازه‌ای انتخاب کند.")
        try:
            from core.economy import announce
            await announce(
                bot,
                f"💥 <b>سقوط یک کشور در جنگ</b>\n\n"
                f"{d_name} پس از از دست دادن همهٔ استان‌هایش سقوط کرد و "
                f"{a_name} بر آن چیره شد. کشور اکنون آزاد است.",
                section="war_attack")
        except Exception:
            pass
        try:
            from gamebot.common import kb
            await bot.send_message(
                defender_id,
                f"💥 <b>کشور شما سقوط کرد!</b>\n\n"
                f"{d_name} همهٔ استان‌های خود را از دست داد.\n"
                "می‌توانید با /start کشور تازه‌ای انتخاب کنید.",
                reply_markup=kb([]))
        except Exception:
            pass
    return line


async def provinces_text(user_id: int) -> str:
    """متن نمایش استان‌ها برای بازیکن."""
    from core.utils import fmt
    summary = await province_summary(user_id)
    if summary["collapsed"]:
        return ("🗺 <b>استان‌های شما</b>\n\n"
                "❌ شما هیچ استانی در اختیار ندارید — کشورتان سقوط کرده است.\n"
                "با /start کشور تازه‌ای انتخاب کنید.")
    lines = [
        "🗺 <b>استان‌های امپراطوری شما</b>\n",
        f"🏴 مجموع استان‌ها: <b>{summary['total']}</b>",
    ]
    if summary["country"]:
        c = summary["country"]
        lines.append(f"{c['flag']} {c['name']} (کشور اصلی): "
                     f"<b>{summary['home']}</b> استان")
    rows = await owned_provinces(user_id)
    per_country: dict[int, list[str]] = {}
    for r in rows:
        per_country.setdefault(r["country_id"], []).append(r["name"])
    if len(per_country) > 1:
        lines.append("\n📍 <b>استان‌های خارج از کشور اصلی:</b>")
        for cid, names in per_country.items():
            if summary["country"] and cid == summary["country"]["id"]:
                continue
            c = await db.fetchone("SELECT name, flag FROM countries WHERE id=?", (cid,))
            label = f"{c['flag']} {c['name']}" if c else f"کشور {cid}"
            lines.append(f"  • {label}: {len(names)} استان")
    lines.append(f"\n💡 هر حملهٔ موفق یک استان می‌گیرد. با از دست دادن همهٔ استان‌ها "
                 f"کشور سقوط می‌کند (هر کشور {BASE_PROVINCES} استان پایه).")
    return "\n".join(lines)

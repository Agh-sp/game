"""☢️ تأسیسات هسته‌ای — هدف قرار دادن، تخریب و بازسازی.

هر کشور با اورانیوم غنی‌شده (مراحل `core.enrichment`) **تأسیسات هسته‌ای** دارد.
این ماژول بخش «🎯 هدف قرار دادن تأسیسات هسته‌ای» در اتاق جنگ را پشتیبانی می‌کند:

- 🎯 **حمله به تأسیسات**: با موشک/هواپیما/فضا (برد بلند) یا خرابکاری سایبری.
- 💥 **تخریب**: تأسیسات از کار می‌افتد؛ مرحلهٔ غنی‌سازی هدف **یک پله** عقب می‌رود و
  بخشی از سانتریفیوژها از بین می‌رود. در حملهٔ سنگین، تأسیسات کامل نابود می‌شود.
- 🛡 **پدافند**: تأسیسات هسته‌ای پدافند اختصاصی دارند (پاتریوت/اس‌۴۰۰ مدافع) که
  شانس رهگیری حمله را بالا می‌برد.
- 🔧 **بازسازی**: صاحب تأسیسات می‌تواند با پرداخت هزینه آن را تعمیر/فعال کند.
- ☢️ **خطر نشت**: در صورت تخریب کامل با شانس کم، نشت رادیواکتیو رضایت مردم مدافع
  را به‌شدت پایین می‌آورد (پیامد واقعی و بازدارنده).

جدول: `nuclear_sites` (یک ردیف برای هر کشور دارای تأسیسات).
"""
from __future__ import annotations

import logging
import random

from core.db import db, get_setting
from core.utils import fmt, fmt_money, iso

log = logging.getLogger(__name__)

# نوع تأسیسات بر اساس مرحلهٔ غنی‌سازی
SITE_KINDS = {
    1: ("رآکتور تحقیقاتی", "🔬"),
    2: ("تأسیسات غنی‌سازی ۲۰٪", "🏭"),
    3: ("تأسیسات غنی‌سازی ۶۰٪", "☢️"),
    4: ("تأسیسات تسلیحاتی ۹۰٪", "💣"),
}

DEFAULT_SITE_HP = 100


async def _add_column() -> None:
    """مهاجرت سبک و idempotent برای ستون‌های اختیاری."""
    try:
        cols = await db.fetchall("PRAGMA table_info(nuclear_sites)")
        names = {c["name"] for c in cols}
        for col, decl in (("hp", f"INTEGER DEFAULT {DEFAULT_SITE_HP}"),
                          ("max_hp", f"INTEGER DEFAULT {DEFAULT_SITE_HP}"),
                          ("centrifuges", "INTEGER DEFAULT 0"),
                          ("destroyed_at", "TEXT"),
                          ("last_attack_at", "TEXT"),
                          ("leaked", "INTEGER DEFAULT 0")):
            if col not in names:
                await db.execute(f"ALTER TABLE nuclear_sites ADD COLUMN {col} {decl}")
    except Exception:
        log.exception("nuclear_sites migration failed")


async def ensure_site(user_id: int) -> dict | None:
    """تأسیسات هسته‌ای کشور را می‌سازد/برمی‌گرداند (فقط اگر غنی‌سازی شروع شده باشد)."""
    from core import enrichment

    row = await db.fetchone("SELECT * FROM nuclear_sites WHERE user_id=?", (user_id,))
    if row:
        return dict(row)
    enr = await enrichment.get_state(user_id)
    stage = int(enr.get("stage") or 0)
    if stage <= 0:
        return None
    kind, emoji = SITE_KINDS.get(min(4, max(1, stage)), SITE_KINDS[1])
    hp = DEFAULT_SITE_HP
    centrifuges = 200 + stage * 300
    await db.execute(
        "INSERT OR IGNORE INTO nuclear_sites(user_id, stage, kind, emoji, hp, max_hp, "
        "centrifuges, active) VALUES(?,?,?,?,?,?,?,1)",
        (user_id, stage, kind, emoji, hp, hp, centrifuges))
    row = await db.fetchone("SELECT * FROM nuclear_sites WHERE user_id=?", (user_id,))
    return dict(row) if row else None


async def sync_stage(user_id: int) -> dict | None:
    """مرحلهٔ تأسیسات را با پیشرفت غنی‌سازی هم‌تراز می‌کند."""
    from core import enrichment

    site = await ensure_site(user_id)
    if not site:
        return None
    enr = await enrichment.get_state(user_id)
    stage = int(enr.get("stage") or 0)
    if stage <= 0:
        return site
    kind, emoji = SITE_KINDS.get(min(4, max(1, stage)), SITE_KINDS[1])
    if site.get("stage") != stage or site.get("kind") != kind:
        await db.execute(
            "UPDATE nuclear_sites SET stage=?, kind=?, emoji=?, centrifuges=MAX(centrifuges,?) "
            "WHERE user_id=?", (stage, kind, emoji, 200 + stage * 300, user_id))
        site = dict(await db.fetchone("SELECT * FROM nuclear_sites WHERE user_id=?", (user_id,)))
    return site


async def is_active(user_id: int) -> bool:
    site = await ensure_site(user_id)
    return bool(site and int(site.get("active") or 0) and int(site.get("hp") or 0) > 0)


async def defense_power(user_id: int) -> int:
    """🛡 پدافند اختصاصی تأسیسات = بخشی از پدافند هوایی + استحکام سازه."""
    try:
        from core.straits import naval_defense  # noqa: F401  (فقط برای سازگاری واردات)
    except Exception:
        pass
    try:
        rows = await db.fetchall(
            "SELECT e.defense_power AS d, a.quantity AS q FROM player_assets a "
            "JOIN equipment e ON e.id=a.item_id "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE a.user_id=? AND a.item_type='equipment' "
            "AND (LOWER(COALESCE(e.subcategory,''))='air_defense' "
            "     OR c.key='air' OR e.name LIKE '%پدافند%' OR e.name LIKE '%اس ۴۰۰%' "
            "     OR e.name LIKE '%پاتریوت%' OR e.name LIKE '%تور%')", (user_id,))
        shield = sum((r["d"] or 0) * (r["q"] or 0) for r in rows) * 0.4
    except Exception:
        shield = 0
    site = await ensure_site(user_id)
    structure = 0
    if site:
        # سازهٔ بتنی تأسیسات: هرچه HP بیشتر، دفاع بیشتر
        structure = int(site.get("max_hp") or DEFAULT_SITE_HP) * 250
    return int(shield + structure)


async def can_target(attacker_id: int) -> tuple[bool, str]:
    """آیا مهاجم سلاح برد بلند (موشک/هواپیما/فضا/سایبری) برای این حمله دارد؟"""
    try:
        rows = await db.fetchall(
            "SELECT e.name AS name, LOWER(COALESCE(e.subcategory,'')) AS sub, "
            "c.key AS cat_key, a.quantity AS q FROM player_assets a "
            "JOIN equipment e ON e.id=a.item_id "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0", (attacker_id,))
    except Exception:
        return False, "❌ خطا در خواندن تجهیزات."
    long_range = [r for r in rows
                  if r["cat_key"] in ("missile", "air", "space")
                  or "موشک" in (r["name"] or "") or "راکت" in (r["name"] or "")
                  or r["sub"] in ("ballistic", "cruise", "space_weapon", "artillery")]
    if not long_range:
        return False, ("❌ برای هدف قرار دادن تأسیسات هسته‌ای به سلاح برد بلند نیاز دارید: "
                       "🚀 موشک بالستیک/کروز، ✈️ بمب‌افکن، 🛰 تسلیحات فضایی "
                       "(از 🎖 پادگان بخرید).")
    return True, ""


async def strike_outlook(attacker_id: int, defender_id: int) -> dict:
    """پیش‌بینی حمله به تأسیسات — هیچ‌چیز را تغییر نمی‌دهد."""
    from core.economy import army_power

    site = await sync_stage(defender_id)
    a_atk, _ad, a_cyber = await army_power(attacker_id)
    _dd, d_def, _dc = await army_power(defender_id)
    shield = await defense_power(defender_id)

    # توان حمله: تجهیزات برد بلند مهاجم + ۳۰٪ توان نظامی کل + اثر سایبری
    long_power = 0
    try:
        rows = await db.fetchall(
            "SELECT e.attack_power AS a, a2.quantity AS q, c.key AS cat_key FROM player_assets a2 "
            "JOIN equipment e ON e.id=a2.item_id "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE a2.user_id=? AND a2.item_type='equipment' "
            "AND (c.key IN ('missile','air','space') OR e.name LIKE '%موشک%' "
            "     OR e.name LIKE '%راکت%')", (attacker_id,))
        long_power = sum((r["a"] or 0) * (r["q"] or 0) for r in rows)
    except Exception:
        long_power = 0
    atk = long_power * 1.0 + a_atk * 0.25 + a_cyber * 0.15
    chance = max(5.0, min(95.0, 100 * atk / max(1.0, atk + shield)))
    return {
        "site": site, "atk_power": int(atk), "shield": int(shield),
        "chance": round(chance, 1), "has_long_range": long_power > 0,
        "hp": int((site or {}).get("hp") or 0),
        "kind": (site or {}).get("kind") or "—",
        "emoji": (site or {}).get("emoji") or "☢️",
        "stage": int((site or {}).get("stage") or 0),
    }


async def has_site(user_id: int) -> bool:
    return (await ensure_site(user_id)) is not None


async def strike(bot, attacker_id: int, defender_id: int) -> str:
    """☢️ اجرای حمله به تأسیسات هسته‌ای دشمن.

    خروجی: متن گزارش کامل برای بازیکن/کانال.
    """
    from core.economy import announce, army_power, get_country
    from core.events import log_event
    from core.utils import add_hours

    ok, err = await can_target(attacker_id)
    if not ok:
        return err
    site = await sync_stage(defender_id)
    if not site:
        return "❌ کشور هدف تأسیسات هسته‌ای ندارد (هنوز غنی‌سازی را شروع نکرده است)."
    if int(site.get("hp") or 0) <= 0 or not int(site.get("active") or 0):
        return ("☢️ تأسیسات هسته‌ای این کشور از قبل از کار افتاده است — "
                "هدف دیگری انتخاب کنید.")

    a_country = await get_country(attacker_id)
    d_country = await get_country(defender_id)
    a_name = f"{a_country['flag']} <b>{a_country['name']}</b>" if a_country else "مهاجم"
    d_name = f"{d_country['flag']} <b>{d_country['name']}</b>" if d_country else "مدافع"

    look = await strike_outlook(attacker_id, defender_id)
    chance = look["chance"] / 100
    success = random.random() < chance

    hp = int(site.get("hp") or 0)
    max_hp = int(site.get("max_hp") or DEFAULT_SITE_HP)
    cent = int(site.get("centrifuges") or 0)
    stage = int(site.get("stage") or 0)

    if success:
        # 💥 آسیب: بین ۳۵ تا ۹۰ درصد HP بر اساس نسبت توان
        ratio = look["atk_power"] / max(1, look["atk_power"] + look["shield"])
        dmg = int(max_hp * (0.35 + 0.55 * min(1.0, ratio * 2)))
        hp_new = max(0, hp - dmg)
        cent_lost = int(cent * min(0.8, dmg / max(1, max_hp)))
        cent_new = max(0, cent - cent_lost)
        fully_destroyed = hp_new <= 0
        stage_new = stage
        if dmg >= max_hp * 0.6 and stage > 0:
            stage_new = stage - 1          # یک پله عقب‌نشینی غنی‌سازی
        await db.execute(
            "UPDATE nuclear_sites SET hp=?, centrifuges=?, stage=?, active=?, "
            "destroyed_at=?, last_attack_at=? WHERE user_id=?",
            (hp_new, cent_new, stage_new, 0 if fully_destroyed else 1,
             iso() if fully_destroyed else None, iso(), defender_id))
        # هم‌ترازی غنی‌سازی با تخریب
        if stage_new < stage:
            try:
                from core import enrichment
                await enrichment.rollback(defender_id, stage_new)
            except Exception:
                log.exception("enrichment rollback failed")
        # ☢️ خطر نشت رادیواکتیو در تخریب کامل
        leak_line = ""
        if fully_destroyed:
            leak_chance = float(await get_setting("nuclear_leak_chance", "35")) / 100
            if random.random() < leak_chance:
                await db.execute(
                    "UPDATE states SET satisfaction=MAX(0, satisfaction-25) WHERE user_id=?",
                    (defender_id,))
                await db.execute("UPDATE nuclear_sites SET leaked=1 WHERE user_id=?",
                                 (defender_id,))
                leak_line = ("\n☢️ <b>نشت رادیواکتیو!</b> تخریب کامل باعث نشت مواد پرتوزا شد: "
                             "رضایت مردم مدافع <b>-۲۵٪</b>.")
        await log_event(
            "war", f"☢️ {a_country['name'] if a_country else attacker_id} تأسیسات هسته‌ای "
                   f"{d_country['name'] if d_country else defender_id} را هدف گرفت")
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-2) WHERE user_id=?",
                         (defender_id,))

        lines = [
            "☢️ <b>حمله به تأسیسات هسته‌ای</b>",
            "",
            f"🎯 مهاجم: {a_name}",
            f"🏭 هدف: {d_name} — {site.get('emoji') or '☢️'} {site.get('kind')}",
            "",
            f"🚀 توان حمله: <b>{fmt(look['atk_power'])}</b>",
            f"🛡 پدافند تأسیسات: <b>{fmt(look['shield'])}</b>",
            f"🎲 شانس موفقیت: <b>{look['chance']}%</b>",
            "",
            "✅ <b>ضربه مستقیم اصابت کرد!</b>",
            f"  • استحکام تأسیسات: <b>{hp}</b> → <b>{hp_new}</b> از {max_hp}",
            f"  • سانتریفیوژهای منهدم‌شده: <b>{fmt(cent_lost)}</b> "
            f"(باقی‌مانده: {fmt(cent_new)})",
        ]
        if stage_new < stage:
            lines.append(f"  • 📉 غنی‌سازی یک پله عقب رفت: مرحلهٔ {stage} → <b>{stage_new}</b>")
        if fully_destroyed:
            lines.append("  • 💥 <b>تأسیسات کامل از کار افتاد!</b>")
        lines.append(leak_line)
        lines.append("\n⚠️ مدافع می‌تواند با «🔧 بازسازی تأسیسات» آن را دوباره فعال کند.")
    else:
        await db.execute("UPDATE nuclear_sites SET last_attack_at=? WHERE user_id=?",
                         (iso(), defender_id))
        await db.execute(
            "INSERT OR IGNORE INTO nuclear_strikes(attacker_id, defender_id, success) VALUES(?,?,0)",
            (attacker_id, defender_id))
        lines = [
            "☢️ <b>حمله به تأسیسات هسته‌ای</b>",
            "",
            f"🎯 مهاجم: {a_name}",
            f"🏭 هدف: {d_name} — {site.get('emoji') or '☢️'} {site.get('kind')}",
            "",
            f"🚀 توان حمله: <b>{fmt(look['atk_power'])}</b>",
            f"🛡 پدافند تأسیسات: <b>{fmt(look['shield'])}</b>",
            f"🎲 شانس موفقیت: <b>{look['chance']}%</b>",
            "",
            "🛡 <b>پدافند تأسیسات حمله را دفع کرد!</b>",
            "  • تأسیسات بدون آسیب ماند.",
            "  • 💡 برای موفقیت، موشک/بمب‌افکن بیشتری بخرید یا قدرت سایبری‌تان را بالا ببرید.",
        ]
        try:
            from core.combat import apply_soldier_losses
            await apply_soldier_losses(attacker_id, 0.02)
        except Exception:
            pass

    # ثبت حمله
    try:
        await db.execute(
            "INSERT INTO nuclear_strikes(attacker_id, defender_id, success, damage, created_at) "
            "VALUES(?,?,?,?,?)",
            (attacker_id, defender_id, 1 if success else 0,
             int(site.get("max_hp") or 0) - int(hp if success else site.get("hp") or 0), iso()))
    except Exception:
        log.exception("nuclear strike log failed")
    # کول‌داون حمله (همان ۳ دقیقهٔ حملهٔ نظامی)
    await db.execute("UPDATE states SET last_attack_at=? WHERE user_id=?", (iso(), attacker_id))

    report = "\n".join(x for x in lines if x is not None)
    try:
        await announce(bot, report, section="war_attack")
    except Exception:
        log.exception("nuclear announce failed")
    try:
        from gamebot.common import dm
        await dm(bot, defender_id, report)
    except Exception:
        pass
    return report


async def rebuild_cost(user_id: int) -> int:
    site = await ensure_site(user_id)
    if not site:
        return 0
    missing = max(0, int(site.get("max_hp") or DEFAULT_SITE_HP) - int(site.get("hp") or 0))
    base = int(float(await get_setting("nuclear_rebuild_cost", "120000000")))
    return int(base * (1 + missing / max(1, DEFAULT_SITE_HP)))


async def rebuild(user_id: int) -> tuple[bool, str]:
    """🔧 بازسازی تأسیسات هسته‌ای با هزینه."""
    site = await sync_stage(user_id)
    if not site:
        return False, "❌ شما تأسیساتی ندارید — اول غنی‌سازی را شروع کنید (☢️ بخش غنی‌سازی)."
    max_hp = int(site.get("max_hp") or DEFAULT_SITE_HP)
    hp = int(site.get("hp") or 0)
    if hp >= max_hp and int(site.get("active") or 0):
        return False, "✅ تأسیسات شما سالم و فعال است."
    cost = await rebuild_cost(user_id)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, (f"❌ بودجهٔ بازسازی کافی نیست.\n💰 نیاز: <b>{fmt_money(cost)}</b>\n"
                       f"💰 خزانه: <b>{fmt_money(money)}</b>")
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    await db.execute(
        "UPDATE nuclear_sites SET hp=?, active=1, destroyed_at=NULL, leaked=0 WHERE user_id=?",
        (max_hp, user_id))
    return True, (f"🔧 <b>تأسیسات هسته‌ای بازسازی شد!</b>\n\n"
                  f"🏭 استحکام: <b>{max_hp}/{max_hp}</b>\n"
                  f"💰 هزینه: {fmt_money(cost)}\n"
                  "✅ تأسیسات دوباره فعال است.")


async def site_text(user_id: int) -> str:
    """متن وضعیت تأسیسات هسته‌ای برای نمایش به صاحبش."""
    site = await sync_stage(user_id)
    if not site:
        return ("☢️ <b>تأسیسات هسته‌ای</b>\n\n"
                "❌ شما هنوز تأسیساتی ندارید.\n"
                "💡 با شروع ☢️ غنی‌سازی اورانیوم (از مدیریت کشور ← ☢️ غنی‌سازی) "
                "اولین تأسیسات شما ساخته می‌شود.")
    hp = int(site.get("hp") or 0)
    max_hp = int(site.get("max_hp") or DEFAULT_SITE_HP)
    active = int(site.get("active") or 0) and hp > 0
    shield = await defense_power(user_id)
    cost = await rebuild_cost(user_id)
    from core.utils import fmt as _fmt
    lines = [
        "☢️ <b>تأسیسات هسته‌ای کشور شما</b>\n",
        f"{site.get('emoji') or '☢️'} نوع: <b>{site.get('kind')}</b>",
        f"📊 مرحلهٔ غنی‌سازی: <b>{site.get('stage')}</b>",
        f"🏗 استحکام: <b>{hp}/{max_hp}</b> {'✅ فعال' if active else '💥 از کار افتاده'}",
        f"🌀 سانتریفیوژها: <b>{_fmt(int(site.get('centrifuges') or 0))}</b>",
        f"🛡 پدافند اختصاصی: <b>{_fmt(shield)}</b>",
    ]
    if not active:
        lines.append(f"\n🔧 هزینهٔ بازسازی: <b>{fmt_money(cost)}</b>")
    if int(site.get("leaked") or 0):
        lines.append("\n☢️ <b>هشدار:</b> این تأسیسات قبلاً نشت رادیواکتیو داشته است.")
    lines.append("\n⚠️ تأسیسات هسته‌ای هدف حملات موشکی و سایبری دشمن است. "
                 "پدافند هوایی بیشتری مستقر کنید.")
    return "\n".join(lines)


async def targets(attacker_id: int) -> list[dict]:
    """کشورهایی که تأسیسات هسته‌ای فعال دارند (برای انتخاب هدف)."""
    try:
        rows = await db.fetchall(
            "SELECT n.*, c.name, c.flag FROM nuclear_sites n "
            "JOIN users u ON u.id=n.user_id JOIN countries c ON c.id=u.country_id "
            "WHERE n.user_id!=? AND n.active=1 AND n.hp>0 AND u.banned=0 "
            "ORDER BY n.stage DESC, n.hp ASC", (attacker_id,))
        return [dict(r) for r in rows]
    except Exception:
        return []

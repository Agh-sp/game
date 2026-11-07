"""🕊 آتش‌بس و صلح واقعی — پایان دادن به جنگ فرسایشی.

در واقعیت هیچ جنگی بی‌پایان نیست: یکی از طرفین آتش‌بس پیشنهاد می‌دهد، طرف
مقابل قبول یا رد می‌کند. این ماژول آن چرخه را پیاده می‌کند:

1. **پیشنهاد آتش‌بس** (`offer`) — جنگ باید فعال باشد.
2. **پذیرش** (`accept`) — جنگ `ended` می‌شود، **فرسایش هر دو طرف صفر** می‌شود
   و پیمان صلح در جدول `treaties` ثبت می‌شود.
3. **رد** (`reject`) — جنگ ادامه می‌یابد و روحیهٔ پیشنهاددهنده کمی می‌افتد.
4. **تسلیم یک‌طرفه** (`surrender`) — کشوری که فرسایشش از آستانه گذشته می‌تواند
   بدون تأیید دشمن تسلیم شود: چند استان به مهاجم می‌دهد ولی جنگ تمام می‌شود.

جدول: `ceasefire_offers`
"""
from __future__ import annotations

import logging

from core.db import db, get_setting
from core.utils import add_hours, fmt, iso

log = logging.getLogger(__name__)


async def active_war(a: int, b: int) -> dict | None:
    """جنگ فعال بین دو کشور (در هر جهت)."""
    return await db.fetchone(
        "SELECT * FROM wars WHERE status='active' AND "
        "((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?)) "
        "ORDER BY id DESC LIMIT 1", (a, b, b, a))


async def wars_of(user_id: int) -> list[dict]:
    """همهٔ جنگ‌های فعال یک کشور با نام و پرچم طرف مقابل."""
    return await db.fetchall(
        "SELECT w.*, "
        "  CASE WHEN w.attacker_id=? THEN uo.id ELSE um.id END AS foe, "
        "  CASE WHEN w.attacker_id=? THEN co.name ELSE cm.name END AS foe_name, "
        "  CASE WHEN w.attacker_id=? THEN co.flag ELSE cm.flag END AS foe_flag, "
        "  CASE WHEN w.attacker_id=? THEN 'attacker' ELSE 'defender' END AS role "
        "FROM wars w "
        "JOIN users um ON um.id=w.attacker_id JOIN countries cm ON cm.id=um.country_id "
        "JOIN users uo ON uo.id=w.defender_id JOIN countries co ON co.id=uo.country_id "
        "WHERE w.status='active' AND (w.attacker_id=? OR w.defender_id=?) "
        "ORDER BY w.id DESC",
        (user_id, user_id, user_id, user_id, user_id, user_id))


async def pending_offer(war_id: int) -> dict | None:
    return await db.fetchone(
        "SELECT * FROM ceasefire_offers WHERE war_id=? AND status='pending' "
        "ORDER BY id DESC LIMIT 1", (war_id,))


async def pending_for(user_id: int) -> list[dict]:
    """پیشنهادهای آتش‌بسی که منتظر پاسخ این کاربر هستند."""
    return await db.fetchall(
        "SELECT c.*, w.attacker_id, w.defender_id FROM ceasefire_offers c "
        "JOIN wars w ON w.id=c.war_id "
        "WHERE c.to_id=? AND c.status='pending' ORDER BY c.id DESC", (user_id,))


async def offer(from_id: int, to_id: int) -> tuple[bool, str]:
    """🕊 پیشنهاد آتش‌بس به طرف مقابل."""
    war = await active_war(from_id, to_id)
    if not war:
        return False, "❌ بین شما و این کشور جنگ فعالی نیست."
    if await pending_offer(war["id"]):
        return False, "⏳ یک پیشنهاد آتش‌بس باز است — منتظر پاسخ طرف مقابل باشید."
    # ⏳ فاصلهٔ مجاز بین دو پیشنهاد از یک کشور
    cooldown = float(await get_setting("ceasefire_cooldown_hours", "6") or 6)
    if cooldown > 0:
        last = await db.fetchone(
            "SELECT created_at FROM ceasefire_offers WHERE from_id=? ORDER BY id DESC LIMIT 1",
            (from_id,))
        if last and last.get("created_at"):
            from core.utils import parse, now
            prev = parse(last["created_at"])
            if prev:
                mins = (now() - prev).total_seconds() / 60
                if mins < cooldown * 60:
                    left = int(cooldown * 60 - mins)
                    return False, (f"⏳ تا ارسال پیشنهاد آتش‌بس بعدی "
                                   f"<b>{left}</b> دقیقه مانده است.")
    hours = float(await get_setting("ceasefire_offer_hours", "24") or 24)
    await db.execute(
        "INSERT INTO ceasefire_offers(war_id, from_id, to_id, ends_at) VALUES(?,?,?,?)",
        (war["id"], from_id, to_id, add_hours(hours)))
    return True, (f"🕊 <b>پیشنهاد آتش‌بس ارسال شد</b>\n\n"
                  f"طرف مقابل تا <b>{fmt(hours)} ساعت</b> فرصت پاسخ دارد.\n"
                  "⚔️ تا تصمیم او حمله‌ها آزاد است — آتش‌بس فوری نیست.")


async def end_war(war_id: int, by_user: int = 0) -> None:
    """پایان دادن به جنگ + پاک‌کردن فرسایش هر دو طرف."""
    war = await db.fetchone("SELECT * FROM wars WHERE id=?", (war_id,))
    if not war:
        return
    await db.execute(
        "UPDATE wars SET status='ended', ended_at=? WHERE id=?", (iso(), war_id))
    try:
        from core import attrition as attr
        await attr.reset(war["attacker_id"])
        await attr.reset(war["defender_id"])
    except Exception:
        log.exception("attrition reset after ceasefire failed")


async def _register_peace_treaty(war: dict, by_user: int) -> None:
    """ثبت پیمان صلح فعال بین دو طرف (اگر از قبل نباشد)."""
    try:
        from core.treaties import find_treaty, create_treaty
        a, b = war["attacker_id"], war["defender_id"]
        existing = await find_treaty(a, b, "peace")
        if existing:
            return
        tid = await create_treaty("peace", a, b, 0, None, 0)
        await db.execute("UPDATE treaties SET status='active', confirmed_at=? WHERE id=?",
                         (iso(), tid))
    except Exception:
        log.exception("peace treaty registration failed")


async def accept(offer_id: int, user_id: int, bot=None) -> tuple[bool, str]:
    """✅ پذیرش آتش‌بس — پایان جنگ، پاک‌شدن فرسایش و ثبت پیمان صلح."""
    off = await db.fetchone("SELECT * FROM ceasefire_offers WHERE id=?", (offer_id,))
    if not off or off["status"] != "pending":
        return False, "❌ این پیشنهاد معتبر یا باز نیست."
    if int(off["to_id"]) != int(user_id):
        return False, "❌ فقط طرف مقابل می‌تواند این پیشنهاد را بپذیرد."
    war = await db.fetchone("SELECT * FROM wars WHERE id=?", (off["war_id"],))
    if not war or war["status"] != "active":
        return False, "❌ این جنگ در حال حاضر فعال نیست."
    await db.execute("UPDATE ceasefire_offers SET status='accepted' WHERE id=?", (offer_id,))
    await end_war(war["id"], user_id)
    await _register_peace_treaty(war, user_id)

    from core.economy import get_country
    a = await get_country(war["attacker_id"])
    b = await get_country(war["defender_id"])
    a_name = f"{a['flag']} {a['name']}" if a else "مهاجم"
    b_name = f"{b['flag']} {b['name']}" if b else "مدافع"
    text = (f"🕊 <b>آتش‌بس امضا شد!</b>\n\n"
            f"جنگ بین {a_name} و {b_name} پایان یافت.\n"
            "⛓ فرسایش هر دو کشور پاک شد و پیمان صلح ثبت گردید.")
    if bot:
        try:
            from core.economy import announce
            await announce(bot, text + "\n\n🕊 سازمان ملل از این توافق استقبال می‌کند.",
                           section="treaty_peace")
        except Exception:
            pass
        for uid in (war["attacker_id"], war["defender_id"]):
            try:
                from gamebot.common import dm
                await dm(bot, uid, text)
            except Exception:
                pass
    return True, text


async def reject(offer_id: int, user_id: int) -> tuple[bool, str]:
    """❌ رد آتش‌بس — جنگ ادامه می‌یابد."""
    off = await db.fetchone("SELECT * FROM ceasefire_offers WHERE id=?", (offer_id,))
    if not off or off["status"] != "pending":
        return False, "❌ این پیشنهاد معتبر نیست."
    if int(off["to_id"]) != int(user_id):
        return False, "❌ فقط طرف مقابل می‌تواند پاسخ دهد."
    await db.execute("UPDATE ceasefire_offers SET status='rejected' WHERE id=?", (offer_id,))
    # رد آتش‌بس، روحیهٔ پیشنهاددهنده را کمی می‌شکند (اثر روانی جنگ)
    try:
        await db.execute(
            "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-2) "
            "WHERE user_id=?", (off["from_id"],))
    except Exception:
        pass
    return True, "❌ آتش‌بس رد شد. جنگ ادامه دارد و پیشنهاددهنده ۲٪ رضایت از دست داد."


async def can_surrender(user_id: int) -> tuple[bool, str]:
    """آیا کشور به‌قدری فرسوده شده که بتواند تسلیم شود؟"""
    war = await db.fetchone(
        "SELECT * FROM wars WHERE status='active' AND defender_id=? "
        "ORDER BY id DESC LIMIT 1", (user_id,))
    if not war:
        # مهاجم هم می‌تواند از ادامهٔ جنگ منصرف شود
        return False, "❌ شما در جایگاه مدافع در جنگ فعالی نیستید."
    from core import attrition as attr
    wear = await attr.wear_of(user_id)
    threshold = float(await get_setting("attrition_surrender_threshold", "60") or 60)
    if wear < threshold:
        return False, (f"❌ تسلیم فقط وقتی ممکن است که فرسایش کشورتان از "
                       f"<b>{fmt(threshold)}٪</b> بگذرد (فرسایش شما: {wear}٪).")
    return True, ""


async def surrender(war: dict, user_id: int, bot=None) -> tuple[bool, str]:
    """🏳 تسلیم یک‌طرفه: چند استان به مهاجم می‌رسد ولی جنگ تمام می‌شود."""
    from core import attrition as attr
    from core.economy import get_country
    count = int(float(await get_setting("surrender_provinces", "2") or 2))
    from core.provinces import capture_province
    moved = []
    for _ in range(max(0, count)):
        cap = await capture_province(user_id, war["attacker_id"], war["id"])
        if not cap:
            break
        moved.append(cap["name"])
    await end_war(war["id"], user_id)
    await _register_peace_treaty(war, user_id)
    a = await get_country(war["attacker_id"])
    b = await get_country(user_id)
    a_name = f"{a['flag']} {a['name']}" if a else "مهاجم"
    b_name = f"{b['flag']} {b['name']}" if b else "مدافع"
    text = (f"🏳 <b>تسلیم!</b>\n\n{b_name} در برابر {a_name} تسلیم شد.\n"
            + (f"🗺 استان‌های واگذارشده: {'، '.join(moved)}\n" if moved else "")
            + "🕊 جنگ پایان یافت و فرسایش هر دو طرف پاک شد.")
    if bot:
        try:
            from core.economy import announce
            await announce(bot, text, section="war_attack")
        except Exception:
            pass
    return True, text


async def offer_line(war_id: int) -> str:
    """خط خلاصهٔ وضعیت آتش‌بس برای منوی جنگ."""
    off = await pending_offer(war_id)
    if not off:
        return ""
    from core.economy import get_country
    who = await get_country(off["from_id"])
    name = f"{who['flag']} {who['name']}" if who else "طرف مقابل"
    return f"🕊 پیشنهاد آتش‌بس از {name} در انتظار پاسخ است."

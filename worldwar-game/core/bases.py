"""📡 پایگاه نظامی خارجی — میزبان پول و امنیت می‌گیرد، مهمان دسترسی و ورود خودکار به جنگ.

واقعیت: پایگاه‌های خارجی (مثل پایگاه آمریکا در قطر یا جیبوتی) فقط یک آشیانه نیستند؛
یک قرارداد امنیتی‌اند: میزبان پول و پشتیبانی می‌گیرد، مهمان در ازای آن متعهد می‌شود
اگر میزبان مورد حمله قرار گرفت وارد جنگ شود.

مکانیک (جدول `bases` — نوع `foreign`):
  • میزبان از هر پایگاه در هر دوره `fbase_pay_m` میلیون می‌گیرد.
  • میزبان `fbase_defense_bonus_pct`٪ بونوس دفاعی می‌گیرد (حضور نیروی خارجی).
  • مهمان `fbase_tech_bonus_pct`٪ بونوس قدرت حمله می‌گیرد (دسترسی/فناوری).
  • بازیکن می‌تواند به‌عنوان مهمان درخواست پایگاه بدهد (همان پایگاه زمینی) و
    طرف مقابل پایگاه را «خارجی» اعلام کند (اگر پیمان نظامی هم برقرار باشد).
  • لغو یک‌طرفه (`terminate`) بحران دیپلماتیک می‌سازد: رضایت و روابط میزبان می‌افتد.
  • اگر میزبان مورد حمله قرار گیرد و `fbase_auto_join` روشن باشد، مهمان خودکار
    وارد جنگ می‌شود (اعلام جنگ رسمی ثبت می‌شود).
همهٔ اعداد از پنل ادمین قابل تغییرند.
"""
from __future__ import annotations

import logging

from core.db import db, get_setting
from core.utils import fmt, iso

log = logging.getLogger(__name__)

DEFAULT_PAY_M = 60.0
DEFAULT_DEF_BONUS = 20.0
DEFAULT_TECH_BONUS = 5.0
DEFAULT_CRISIS_SAT = 10.0
DEFAULT_CRISIS_DIPL = 15.0


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
        return await get_setting("sec_foreign_base", "1") == "1"
    except Exception:
        return True


async def _ensure_kinds() -> None:
    """اطمینان از وجود ستون kind برای پایگاه‌های قدیمی (مهاجرت)."""
    try:
        cols = await db.fetchall("PRAGMA table_info(bases)")
        names = {c["name"] for c in cols}
        if "kind" not in names:
            await db.execute("ALTER TABLE bases ADD COLUMN kind TEXT DEFAULT 'land'")
    except Exception:
        pass


async def declare_foreign(host_id: int, guest_id: int) -> tuple[bool, str]:
    """🏷 اعلام یک پایگاه فعال به‌عنوان «پایگاه خارجی» (قرارداد امنیتی)."""
    if not await enabled():
        return False, "❌ بخش پایگاه خارجی خاموش است."
    await _ensure_kinds()
    base = await db.fetchone(
        "SELECT * FROM bases WHERE host_id=? AND guest_id=? AND status='active' "
        "ORDER BY id DESC LIMIT 1", (host_id, guest_id))
    if not base:
        return False, "❌ اول باید پایگاه فعالی از این کشور در سرزمین شما وجود داشته باشد."
    kind = (base.get("kind") or "land")
    if "foreign" in kind:
        return False, "❌ این پایگاه از قبل قرارداد خارجی دارد."
    new_kind = "foreign" if kind in ("", "land") else f"foreign-{kind}"
    await db.execute("UPDATE bases SET kind=?, name=? WHERE id=?",
                     (new_kind, base.get("name") or "پایگاه مشترک", base["id"]))
    guest = await db.fetchone(
        "SELECT c.name, c.flag FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (guest_id,))
    host = await db.fetchone(
        "SELECT c.name, c.flag FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (host_id,))
    pay = int(await _num("fbase_pay_m", DEFAULT_PAY_M) * 1_000_000)
    try:
        from core.events import log_event
        await log_event(
            "treaty",
            f"📡 قرارداد پایگاه خارجی: {guest['name'] if guest else guest_id} در "
            f"{host['name'] if host else host_id} — میزبان {fmt(pay)} در هر دوره می‌گیرد")
    except Exception:
        pass
    try:
        from gamebot.common import dm
        await dm(None, guest_id,
                 f"📡 <b>قرارداد پایگاه خارجی بسته شد</b>\n"
                 f"کشور {host['flag'] if host else ''} {host['name'] if host else ''} پایگاه شما را "
                 f"«خارجی» اعلام کرد.\n"
                 f"💰 میزبان از این پس {fmt(pay)} در هر دوره دریافت می‌کند و در عوض "
                 "در صورت حمله به او، شما به‌طور خودکار وارد جنگ می‌شوید.")
    except Exception:
        pass
    return True, (f"✅ <b>پایگاه خارجی اعلام شد.</b>\n"
                  f"🏳 میزبان: {host['flag'] if host else ''} {host['name'] if host else ''}\n"
                  f"💰 درآمد هر دوره میزبان: <b>{fmt(pay)}</b>\n"
                  "🛡 بونوس دفاعی میزبان و بونوس فناوری مهمان فعال شد.")


async def income_tick(user_id: int) -> int:
    """درآمد میزبان از پایگاه‌های خارجی (در هر دورهٔ درآمد)."""
    if not await enabled():
        return 0
    await _ensure_kinds()
    try:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM bases WHERE host_id=? AND status='active' "
            "AND kind LIKE '%foreign%'", (user_id,))
        count = int((row or {}).get("c") or 0)
    except Exception:
        return 0
    if not count:
        return 0
    pay = int(await _num("fbase_pay_m", DEFAULT_PAY_M) * 1_000_000) * count
    await db.execute("UPDATE users SET money=money+? WHERE id=?", (pay, user_id))
    return pay


async def defense_bonus(host_id: int) -> float:
    """ضریب دفاع میزبان به‌خاطر حضور نیروی خارجی."""
    if not await enabled():
        return 1.0
    await _ensure_kinds()
    try:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM bases WHERE host_id=? AND status='active' "
            "AND kind LIKE '%foreign%'", (host_id,))
        count = int((row or {}).get("c") or 0)
    except Exception:
        return 1.0
    if not count:
        return 1.0
    pct = await _num("fbase_defense_bonus_pct", DEFAULT_DEF_BONUS) / 100
    return round(1.0 + pct * min(3, count), 3)


async def attack_bonus(guest_id: int) -> float:
    """ضریب قدرت حملهٔ مهمان به‌خاطر حضور در پایگاه‌های خارجی."""
    if not await enabled():
        return 1.0
    await _ensure_kinds()
    try:
        row = await db.fetchone(
            "SELECT COUNT(*) c FROM bases WHERE guest_id=? AND status='active' "
            "AND kind LIKE '%foreign%'", (guest_id,))
        count = int((row or {}).get("c") or 0)
    except Exception:
        return 1.0
    if not count:
        return 1.0
    pct = await _num("fbase_tech_bonus_pct", DEFAULT_TECH_BONUS) / 100
    return round(1.0 + pct * min(3, count), 3)


async def terminate(host_id: int, guest_id: int) -> tuple[bool, str]:
    """✂️ لغو یک‌طرفه قرارداد پایگاه خارجی توسط میزبان (بحران دیپلماتیک)."""
    await _ensure_kinds()
    base = await db.fetchone(
        "SELECT * FROM bases WHERE host_id=? AND guest_id=? AND kind LIKE '%foreign%' "
        "AND status='active' ORDER BY id DESC LIMIT 1", (host_id, guest_id))
    if not base:
        return False, "❌ قرارداد پایگاه خارجی فعالی با این کشور ندارید."
    await db.execute("DELETE FROM bases WHERE id=?", (base["id"],))
    sat_hit = await _num("fbase_crisis_sat", DEFAULT_CRISIS_SAT)
    dipl = await _num("fbase_crisis_diplomacy", DEFAULT_CRISIS_DIPL)
    await db.execute(
        "UPDATE states SET satisfaction=MAX(0, COALESCE(satisfaction,50)-?) WHERE user_id=?",
        (sat_hit, host_id))
    await db.execute(
        "UPDATE states SET diplomacy=MAX(0, COALESCE(diplomacy,50)-?) WHERE user_id=?",
        (dipl, host_id))
    try:
        from core import unrest as unrest_mod
        await unrest_mod.add_unrest(host_id, 8)
    except Exception:
        pass
    try:
        from core.events import log_event
        await log_event("treaty", "📡 یک کشور قرارداد پایگاه خارجی را یک‌طرفه لغو کرد — "
                                  "بحران دیپلماتیک")
    except Exception:
        pass
    return True, (f"✂️ <b>قرارداد پایگاه لغو شد.</b>\n"
                  f"😞 رضایت مردم و روابط بین‌المللی شما افت کرد (−{round(sat_hit)} / "
                  f"−{round(dipl)})\n"
                  "⚠️ کشور مهمان حالا آزاد است و می‌تواند این را توهین تلقی کند.")


async def auto_join_if_attacked(bot, defender_id: int, attacker_id: int) -> list[str]:
    """اگر میزبانِ پایگاه خارجی مورد حمله قرار گرفت، مهمان خودکار وارد جنگ می‌شود."""
    if not await enabled():
        return []
    if await get_setting("fbase_auto_join", "1") != "1":
        return []
    await _ensure_kinds()
    rows = await db.fetchall(
        "SELECT guest_id FROM bases WHERE host_id=? AND status='active' AND kind LIKE '%foreign%'",
        (defender_id,))
    lines: list[str] = []
    for r in rows:
        guest = int(r.get("guest_id") or 0)
        if not guest or guest == attacker_id:
            continue
        party = await db.fetchone(
            "SELECT c.name, c.flag FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
            (guest,))
        if not party:
            continue
        try:
            await db.execute(
                "INSERT INTO wars(attacker_id, defender_id, reason, status, started_at) "
                "VALUES(?,?,?,'active',?)",
                (guest, attacker_id, "دفاع از میزبان پایگاه خارجی", iso()))
        except Exception:
            log.exception("auto join war failed")
        lines.append(f"📡 طبق قرارداد پایگاه، {party['flag']} <b>{party['name']}</b> "
                     "خودکار وارد جنگ شد.")
        try:
            from gamebot.common import dm
            if bot:
                await dm(bot, guest,
                         f"📡 <b>وظیفهٔ قراردادی فعال شد!</b>\n"
                         f"به میزبان پایگاه شما حمله شد؛ طبق قرارداد وارد جنگ با مهاجم شدید.")
                await dm(bot, defender_id,
                         "📡 <b>پشتیبانی قراردادی</b>\nطبق قرارداد پایگاه خارجی، "
                         f"{party['flag']} {party['name']} وارد جنگ شد.")
        except Exception:
            pass
        try:
            from core.events import log_event
            await log_event("war", f"📡 {party['name']} طبق قرارداد پایگاه خارجی وارد جنگ شد")
        except Exception:
            pass
    return lines


async def bases_text(user_id: int) -> str:
    """متن وضعیت پایگاه‌های خارجی کشور."""
    await _ensure_kinds()
    hosted = await db.fetchall(
        "SELECT b.*, c.name, c.flag FROM bases b JOIN users u ON u.id=b.guest_id "
        "JOIN countries c ON c.id=u.country_id WHERE b.host_id=? AND b.status IN ('active','pending')",
        (user_id,))
    guests = await db.fetchall(
        "SELECT b.*, c.name, c.flag FROM bases b JOIN users u ON u.id=b.host_id "
        "JOIN countries c ON c.id=u.country_id WHERE b.guest_id=? AND b.status IN ('active','pending')",
        (user_id,))
    pay = int(await _num("fbase_pay_m", DEFAULT_PAY_M) * 1_000_000)
    lines = ["📡 <b>پایگاه نظامی خارجی</b>", "",
             f"💰 درآمد هر پایگاه میزبان: {fmt(pay)} در هر دوره",
             f"🛡 بونوس دفاعی میزبان: +{round(await _num('fbase_defense_bonus_pct', DEFAULT_DEF_BONUS))}٪",
             f"⚔️ بونوس حملهٔ مهمان: +{round(await _num('fbase_tech_bonus_pct', DEFAULT_TECH_BONUS))}٪",
             "", "🏳 <b>پایگاه‌های کشورهای دیگر در سرزمین شما:</b>"]
    if not hosted:
        lines.append("  — ندارید —")
    for b in hosted:
        status = "✅ فعال" if b["status"] == "active" else "⏳ در انتظار"
        foreign = "📡 خارجی" if "foreign" in (b.get("kind") or "") else "🚚 زمینی"
        lines.append(f"  {status} | {foreign} | {b['flag']} {b['name']}")
    lines.append("\n🌍 <b>پایگاه‌های شما در کشورهای دیگر:</b>")
    if not guests:
        lines.append("  — ندارید —")
    for b in guests:
        foreign = "📡 خارجی" if "foreign" in (b.get("kind") or "") else "🚚 زمینی"
        lines.append(f"  {'✅ فعال' if b['status'] == 'active' else '⏳ در انتظار'} | {foreign} | "
                     f"{b['flag']} {b['name']}")
    lines.append("\n💡 پایگاه خارجی = قرارداد امنیتی: میزبان پول و بونوس دفاعی می‌گیرد، "
                 "مهمان بونوس حمله و تعهد ورود خودکار به جنگ.")
    return "\n".join(lines)

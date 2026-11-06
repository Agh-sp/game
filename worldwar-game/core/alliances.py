"""اتحاد بین کشورها — عضوگیری، تأیید دوطرفه و کمک دفاعی متحدان.

قواعد:
- هر بازیکن در هر لحظه فقط در **یک** اتحاد می‌تواند باشد.
- برای ورود، یکی از اعضا دعوت می‌فرستد و طرف مقابل تأیید می‌کند.
- در دفاع، هر متحد تا `alliance_defense_percent` درصد از توان دفاعی خود را به
  مدافع اضافه می‌کند (پیش‌فرض ۳۰٪).
- اگر مدافع عضو اتحاد باشد و متحدی هم در جنگ شریک شود، در گزارش نبرد نمایش داده می‌شود.
"""
from __future__ import annotations

import logging

from core.db import db, get_setting

log = logging.getLogger(__name__)

DEFAULT_DEFENSE_PERCENT = 30
MAX_MEMBERS_DEFAULT = 8


async def my_alliance(user_id: int) -> dict | None:
    """اتحاد فعال بازیکن (یا None)."""
    row = await db.fetchone(
        "SELECT a.* FROM alliances a JOIN alliance_members m ON m.alliance_id=a.id "
        "WHERE m.user_id=? AND a.status='active'", (user_id,))
    return row


async def alliance_members(alliance_id: int) -> list[dict]:
    return await db.fetchall(
        "SELECT m.user_id, m.role, m.joined_at, c.flag, c.name AS country "
        "FROM alliance_members m "
        "LEFT JOIN users u ON u.id=m.user_id "
        "LEFT JOIN countries c ON c.id=u.country_id "
        "WHERE m.alliance_id=? ORDER BY m.joined_at", (alliance_id,))


async def allies_of(user_id: int) -> list[int]:
    """آیدی بازیکنان هم‌اتحاد (بدون خودِ بازیکن)."""
    al = await my_alliance(user_id)
    if not al:
        return []
    rows = await db.fetchall(
        "SELECT user_id FROM alliance_members WHERE alliance_id=? AND user_id!=?",
        (al["id"], user_id))
    return [int(r["user_id"]) for r in rows]


async def defense_bonus(defender_id: int) -> dict:
    """توان دفاعی افزوده از سوی متحدان.

    خروجی: {"percent": 30, "allies": [..], "bonus": درصد واقعی}
    """
    percent = int(float(await get_setting("alliance_defense_percent",
                                          DEFAULT_DEFENSE_PERCENT)))
    allies = await allies_of(defender_id)
    if not allies:
        return {"percent": percent, "allies": [], "bonus": 0.0}
    return {"percent": percent, "allies": allies, "bonus": percent / 100}


async def create_alliance(user_id: int, name: str) -> tuple[bool, str]:
    """ساخت اتحاد جدید توسط بازیکن (رهبر اتحاد)."""
    if await my_alliance(user_id):
        return False, "❌ شما همین حالا عضو یک اتحاد هستید. اول از آن خارج شوید."
    name = (name or "").strip()
    if len(name) < 3:
        return False, "❌ نام اتحاد باید حداقل ۳ حرف باشد."
    if len(name) > 40:
        return False, "❌ نام اتحاد حداکثر ۴۰ حرف."
    exists = await db.fetchone(
        "SELECT id FROM alliances WHERE name=? AND status='active'", (name,))
    if exists:
        return False, "❌ اتحادی با این نام از قبل وجود دارد."
    aid = await db.execute(
        "INSERT INTO alliances(name, leader_id, status) VALUES(?,?,'active')",
        (name, user_id))
    await db.execute(
        "INSERT INTO alliance_members(alliance_id, user_id, role) VALUES(?,?,'leader')",
        (aid, user_id))
    try:
        from core.events import log_event
        await log_event("treaty", f"🤝 اتحاد «{name}» تأسیس شد")
    except Exception:
        pass
    return True, f"✅ <b>اتحاد «{name}» تأسیس شد.</b>\nشما رهبر این اتحاد هستید."


async def invite(alliance_id: int, inviter_id: int, invitee_id: int) -> tuple[bool, str]:
    """دعوت بازیکن دیگر به اتحاد."""
    al = await db.fetchone("SELECT * FROM alliances WHERE id=? AND status='active'",
                           (alliance_id,))
    if not al:
        return False, "❌ اتحاد یافت نشد."
    member = await db.fetchone(
        "SELECT user_id FROM alliance_members WHERE alliance_id=? AND user_id=?",
        (alliance_id, inviter_id))
    if not member:
        return False, "❌ شما عضو این اتحاد نیستید."
    if await my_alliance(invitee_id):
        return False, "❌ این بازیکن همین حالا عضو یک اتحاد است."
    max_members = int(float(await get_setting("alliance_max_members",
                                              str(MAX_MEMBERS_DEFAULT))))
    count = await db.fetchone(
        "SELECT COUNT(*) c FROM alliance_members WHERE alliance_id=?", (alliance_id,))
    if int((count or {}).get("c") or 0) >= max_members:
        return False, f"❌ اتحاد پر است (حداکثر {max_members} عضو)."
    dup = await db.fetchone(
        "SELECT id FROM alliance_invites WHERE alliance_id=? AND invitee_id=? "
        "AND status='pending'", (alliance_id, invitee_id))
    if dup:
        return False, "⏳ برای این بازیکن دعوت‌نامهٔ باز وجود دارد."
    await db.execute(
        "INSERT INTO alliance_invites(alliance_id, inviter_id, invitee_id) VALUES(?,?,?)",
        (alliance_id, inviter_id, invitee_id))
    return True, "✅ دعوت‌نامه ارسال شد."


async def pending_invites(user_id: int) -> list[dict]:
    return await db.fetchall(
        "SELECT i.*, a.name AS alliance_name FROM alliance_invites i "
        "JOIN alliances a ON a.id=i.alliance_id "
        "WHERE i.invitee_id=? AND i.status='pending' AND a.status='active'", (user_id,))


async def accept_invite(invite_id: int, user_id: int) -> tuple[bool, str]:
    inv = await db.fetchone(
        "SELECT * FROM alliance_invites WHERE id=? AND invitee_id=? AND status='pending'",
        (invite_id, user_id))
    if not inv:
        return False, "❌ دعوت‌نامه یافت نشد."
    if await my_alliance(user_id):
        return False, "❌ شما همین حالا عضو یک اتحاد هستید."
    al = await db.fetchone("SELECT * FROM alliances WHERE id=? AND status='active'",
                           (inv["alliance_id"],))
    if not al:
        return False, "❌ این اتحاد منحل شده است."
    await db.execute(
        "INSERT OR IGNORE INTO alliance_members(alliance_id, user_id, role) "
        "VALUES(?,?,'member')", (al["id"], user_id))
    await db.execute("UPDATE alliance_invites SET status='accepted' WHERE id=?", (invite_id,))
    return True, f"✅ شما به اتحاد «{al['name']}» پیوستید."


async def decline_invite(invite_id: int, user_id: int) -> tuple[bool, str]:
    inv = await db.fetchone(
        "SELECT * FROM alliance_invites WHERE id=? AND invitee_id=? AND status='pending'",
        (invite_id, user_id))
    if not inv:
        return False, "❌ دعوت‌نامه یافت نشد."
    await db.execute("UPDATE alliance_invites SET status='declined' WHERE id=?", (invite_id,))
    return True, "✅ دعوت‌نامه رد شد."


async def leave_alliance(user_id: int) -> tuple[bool, str]:
    al = await my_alliance(user_id)
    if not al:
        return False, "❌ شما عضو هیچ اتحادی نیستید."
    members = await alliance_members(al["id"])
    await db.execute("DELETE FROM alliance_members WHERE alliance_id=? AND user_id=?",
                     (al["id"], user_id))
    if int(al["leader_id"] or 0) == user_id:
        others = [m for m in members if int(m["user_id"]) != user_id]
        if others:
            new_leader = int(others[0]["user_id"])
            await db.execute("UPDATE alliances SET leader_id=? WHERE id=?",
                             (new_leader, al["id"]))
            await db.execute(
                "UPDATE alliance_members SET role='leader' WHERE alliance_id=? AND user_id=?",
                (al["id"], new_leader))
        else:
            await db.execute(
                "UPDATE alliances SET status='dissolved', dissolved_at=datetime('now') "
                "WHERE id=?", (al["id"],))
            return True, f"🚪 از اتحاد «{al['name']}» خارج شدید و اتحاد منحل شد."
    return True, f"🚪 از اتحاد «{al['name']}» خارج شدید."


async def list_alliances() -> list[dict]:
    return await db.fetchall(
        "SELECT a.*, (SELECT COUNT(*) FROM alliance_members m WHERE m.alliance_id=a.id) members "
        "FROM alliances a WHERE a.status='active' ORDER BY members DESC, a.id")


async def alliance_text(user_id: int) -> str:
    """متن وضعیت اتحاد بازیکن."""
    from core.utils import fmt
    al = await my_alliance(user_id)
    if not al:
        invites = await pending_invites(user_id)
        lines = ["🤝 <b>اتحاد شما</b>\n",
                 "شما عضو هیچ اتحادی نیستید.",
                 "\n💡 با ساخت یا پیوستن به اتحاد، متحدان در دفاع "
                 f"{await get_setting('alliance_defense_percent', '30')}٪ از توان دفاعی خود را به شما اضافه می‌کنند."]
        if invites:
            lines.append(f"\n📨 <b>{len(invites)} دعوت‌نامهٔ باز</b> دارید — از دکمه‌های زیر ببینید.")
        return "\n".join(lines)

    members = await alliance_members(al["id"])
    lines = [
        f"🤝 <b>اتحاد «{al['name']}»</b>\n",
        f"👑 رهبر: {'شما' if int(al['leader_id'] or 0) == user_id else 'بازیکن دیگر'}",
        f"👥 اعضا: <b>{len(members)}</b>",
        f"🛡 کمک دفاعی هر متحد: <b>{await get_setting('alliance_defense_percent', '30')}٪</b>\n",
        "<b>اعضای اتحاد:</b>",
    ]
    for m in members:
        flag = m["flag"] or "🏳"
        name = m["country"] or f"بازیکن {m['user_id']}"
        role = "👑" if m["role"] == "leader" else "•"
        me = " <i>(شما)</i>" if int(m["user_id"]) == user_id else ""
        lines.append(f"  {role} {flag} {name}{me}")
    return "\n".join(lines)

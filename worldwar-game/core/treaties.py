"""پیمان‌ها (معاهدات) — ساخت، تأیید، فعال‌سازی، اعلان با عکس و خیانت.

انواع پیمان:
  military  → پیمان نظامی (دفاع مشترک در برابر اعلان جنگ)
  trade     → رفیقای تجاری (درصدی از فروش به هم)
  peace     → پیمان صلح (فقط حین جنگ فعال؛ جنگ را تمام می‌کند)
  trust     → اعتماد (دیدن لحظه‌ای اطلاعات کامل کشور مقابل؛ نیازمند شاهد سوم)
  brothers  → برادران تنی (چند پیمان به‌صورت یکجا)
"""
from core.db import db, get_setting
from core.economy import get_country
from core.events import log_event
from core.images import announce_img
from core.utils import fmt, iso

TREATY_KINDS = {
    "military": ("🤝 پیمان نظامی",
                 "کشور میزبان و مهمان قرارداد می‌بندند که در صورت اعلان جنگ یک کشور به یکی از این دو، "
                 "آن کشور دیگر در جبهه‌ی این کشور بوده و در جنگ کمکِ حالش است."),
    "trade": ("💼 رفیقای تجاری",
              "هر دو کشور، درصدی دلخواه از پول فروش کالایشان به یکدیگر را می‌گیرند. "
              "در صورت امتناع از پرداخت، طرف مقابل می‌تواند قرارداد را بهم بزند (خیانت)."),
    "peace": ("🕊 پیمان صلح",
              "فقط حین جنگ فعال بین دو طرف ممکن است؛ با تأیید، جنگ پایان می‌یابد."),
    "trust": ("🤫 اعتماد",
              "دیدن آنی تجهیزات نظامی و تمام اطلاعات کشور مقابل از دکمه «اعتماد» در امپراطوری من. "
              "نیازمند تأیید و امضای کشور سوم به‌عنوان شاهد است."),
    "brothers": ("👥 برادران تنی",
                 "تمام پیمان‌های قبلی (نظامی/تجاری/اعتماد و در صورت جنگ، صلح) به‌صورت یکجا یا دلخواه."),
}

WITNESS_KINDS = {"trust"}


async def treaty_required_confirmers(t: dict) -> list[int]:
    """چه کسانی باید پیمان را تأیید کنند (غیر از سازنده)."""
    ids = [t["party_b"]]
    if t["witness_id"]:
        ids.append(t["witness_id"])
    return [i for i in ids if i]


async def create_treaty(kind: str, party_a: int, party_b: int,
                        neg_id: int = 0, witness_id: int | None = None,
                        trade_percent: float = 0) -> int:
    """ساخت پیمان در وضعیت pending؛ سازنده خودش تأییدشده است."""
    tid = await db.execute(
        "INSERT INTO treaties(kind, party_a, party_b, witness_id, neg_id, trade_percent, status) "
        "VALUES(?,?,?,?,?,?,'pending')",
        (kind, party_a, party_b, witness_id, neg_id, trade_percent))
    await db.execute(
        "INSERT OR IGNORE INTO treaty_confirms(treaty_id, user_id) VALUES(?,?)",
        (tid, party_a))
    await log_event("treaty", f"پیمان {TREATY_KINDS[kind][0]} پیشنهاد شد (#{tid})")
    return tid


async def confirm_treaty(treaty_id: int, user_id: int) -> str:
    """ثبت تأیید یک طرف؛ در صورت تکمیل، فعال‌سازی و اعلان. خروجی: پیام نتیجه."""
    t = await db.fetchone("SELECT * FROM treaties WHERE id=?", (treaty_id,))
    if not t or t["status"] != "pending":
        return "❌ پیمان یافت نشد یا نهایی شده است."
    await db.execute(
        "INSERT OR IGNORE INTO treaty_confirms(treaty_id, user_id) VALUES(?,?)",
        (treaty_id, user_id))
    need = await treaty_required_confirmers(t)
    rows = await db.fetchall("SELECT user_id FROM treaty_confirms WHERE treaty_id=?", (treaty_id,))
    confirmed = {r["user_id"] for r in rows}
    if all(i in confirmed for i in need):
        await db.execute(
            "UPDATE treaties SET status='active', confirmed_at=? WHERE id=?",
            (iso(), treaty_id))
        await _announce_active(t)
        return "✅ پیمان نهایی و فعال شد!"
    return "✅ تأیید شما ثبت شد — در انتظار تأیید سایر طرف‌ها."


async def reject_treaty(treaty_id: int, user_id: int) -> str:
    t = await db.fetchone("SELECT * FROM treaties WHERE id=?", (treaty_id,))
    if not t or t["status"] != "pending":
        return "❌ پیمان یافت نشد."
    await db.execute("UPDATE treaties SET status='rejected' WHERE id=?", (treaty_id,))
    await log_event("treaty", f"پیمان #{treaty_id} رد شد")
    return "❌ پیمان رد شد."


async def _announce_active(t: dict) -> None:
    a = await get_country(t["party_a"])
    b = await get_country(t["party_b"])
    w = await get_country(t["witness_id"]) if t["witness_id"] else None
    title = TREATY_KINDS.get(t["kind"], ("پیمان", ""))[0]
    names = f"کشور {a['name']} و کشور {b['name']}"
    if w:
        names += f" و کشور شاهد {w['name']}"
    extra = f" (درصد تجاری: {round(t['trade_percent'] or 0)}٪)" if t["kind"] == "trade" else ""
    text = f"📜 {title} امضا شد!\nاین قرارداد توسط {names} انجام شد{extra}."
    await log_event("treaty", f"{title} فعال شد: {a['name']} و {b['name']}" +
                    (f" با شاهد {w['name']}" if w else ""))
    # اعلان فقط با ربات بازی انجام می‌شود؛ متن در صف رویداد می‌ماند
    return text, t


async def announce_treaty(bot, t: dict) -> None:
    """اعلان پیمان فعال در کانال با عکس کتابخانه ادمین."""
    text, _ = await _announce_active(t)
    section = f"treaty_{t['kind']}"
    await announce_img(bot, text, section)


async def active_treaties(user_id: int, kind: str = "") -> list[dict]:
    """پیمان‌های فعال یک کاربر (با هر طرفی)."""
    q = ("SELECT * FROM treaties WHERE status='active' AND (party_a=? OR party_b=?)")
    params = [user_id, user_id]
    if kind:
        q += " AND kind=?"
        params.append(kind)
    return await db.fetchall(q + " ORDER BY id DESC", tuple(params))


async def find_treaty(user_a: int, user_b: int, kind: str, status: str = "active") -> dict | None:
    return await db.fetchone(
        "SELECT * FROM treaties WHERE kind=? AND status=? AND "
        "((party_a=? AND party_b=?) OR (party_a=? AND party_b=?))",
        (kind, status, user_a, user_b, user_b, user_a))


async def pact_allies(user_id: int) -> list[int]:
    """متحدان نظامی فعال (پیمان نظامی/برادران تنی شامل نظامی)."""
    rows = await active_treaties(user_id)
    out = []
    for t in rows:
        if t["kind"] in ("military", "brothers"):
            other = t["party_b"] if t["party_a"] == user_id else t["party_a"]
            if other != user_id:
                out.append(other)
    return out


async def trust_partners(user_id: int) -> list[dict]:
    """کشورهای دارای پیمان اعتماد فعال با این کاربر."""
    rows = await active_treaties(user_id, "trust")
    out = []
    for t in rows:
        other = t["party_b"] if t["party_a"] == user_id else t["party_a"]
        c = await get_country(other)
        if c:
            out.append({"user_id": other, "country": c, "treaty": t})
    return out


async def diplomacy_add(user_id: int, delta: float) -> None:
    await db.execute("UPDATE states SET diplomacy=MAX(0,MIN(100,diplomacy+?)) WHERE user_id=?",
                     (delta, user_id))


async def break_treaty(t: dict, bot=None, by_user: int = 0) -> None:
    """شکستن پیمان (خیانت) — دیپلماسی طرفین کم می‌شود و در کانال اعلام می‌شود."""
    await db.execute("UPDATE treaties SET status='broken', broken_at=? WHERE id=?",
                     (iso(), t["id"]))
    a, b = t["party_a"], t["party_b"]
    await diplomacy_add(a, -10)
    await diplomacy_add(b, -10)
    ca, cb = await get_country(a), await get_country(b)
    title = TREATY_KINDS.get(t["kind"], ("پیمان",))[0]
    text = (f"💥 خیانت! {title} بین کشور {ca['name']} و کشور {cb['name']} شکسته شد.\n"
            "دیپلماسی هر دو کشور کاهش یافت.")
    await log_event("treaty", f"شکستن {title}: {ca['name']} و {cb['name']}")
    if bot:
        await announce_img(bot, text, "betray")
    for uid in {a, b}:
        try:
            if bot:
                await bot.send_message(uid, f"💥 پیمان «{title}» شکسته شد! دیپلماسی کشور شما ۱۰ واحد کم شد.")
        except Exception:
            pass

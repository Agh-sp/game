"""سازمان مراقبت از جنگ‌زدگان (سازمان نجات) — رزرو انرژی اهدایی و رای‌گیری کمک.

برای هر جنگ فعال یک بخش/کمپین مجزا باز می‌شود؛ کشورها با اهدای انرژی رأی می‌دهند
(فقط اهداکنندگان حق رأی دارند). اکثریت رأی → ۱۰٪ ذخیره سازمان به کشور برگزیده
پرداخت می‌شود. نتیجه در کانال با عکس اعلام می‌شود ولی مقدار ذخیره مخفی می‌ماند.
"""
from core.db import db, get_setting, set_setting
from core.economy import get_country
from core.events import log_event
from core.images import announce_img
from core.utils import fmt, iso, add_hours


async def ensure_campaign(war_id: int) -> int:
    """ساخت کمپین نجات برای جنگ (هر جنگ یک بخش مجزا)."""
    row = await db.fetchone("SELECT id FROM rescue_campaigns WHERE war_id=?", (war_id,))
    if row:
        return row["id"]
    hours = float(await get_setting("rescue_vote_hours", "24"))
    return await db.execute(
        "INSERT INTO rescue_campaigns(war_id, ends_at) VALUES(?,?)",
        (war_id, add_hours(hours)))


async def campaign_list() -> list[dict]:
    return await db.fetchall(
        "SELECT rc.*, w.attacker_id, w.defender_id, w.status AS war_status "
        "FROM rescue_campaigns rc LEFT JOIN wars w ON w.id=rc.war_id "
        "WHERE rc.status='open' ORDER BY rc.id DESC")


async def reserve_amount() -> int:
    """ذخیره پولی سازمان (از ارزش انرژی اهدایی)."""
    rows = await db.fetchall(
        "SELECT energy FROM rescue_donations")
    price = int(await get_setting("rescue_energy_price", "2000"))
    return sum(r["energy"] or 0 for r in rows) * price


async def donate(bot, campaign_id: int, user_id: int, energy: int, voted_for: int) -> str:
    """اهدای انرژی + ثبت رأی (هر اهدا رأی آخر را مشخص می‌کند)."""
    state = await db.fetchone("SELECT energy FROM states WHERE user_id=?", (user_id,))
    if (state or {}).get("energy", 0) < energy:
        return f"❌ انرژی کافی ندارید (موجود: {fmt(state.get('energy', 0))} kWh)."
    if energy <= 0:
        return "❌ مقدار انرژی باید مثبت باشد."
    price = int(await get_setting("rescue_energy_price", "2000"))
    await db.execute("UPDATE states SET energy=energy-? WHERE user_id=?", (energy, user_id))
    await db.execute(
        "INSERT INTO rescue_donations(campaign_id, user_id, energy, voted_for) VALUES(?,?,?,?)",
        (campaign_id, user_id, energy, voted_for))
    await log_event("rescue", f"کشور {await _cname(user_id)} {fmt(energy)}kWh انرژی به سازمان نجات اهدا کرد")
    return (f"🏥 {fmt(energy)} kWh انرژی به سازمان نجات اهدا شد (معادل {fmt(energy * price)} پول در ذخیره سازمان).\n"
            f"🗳 رأی شما برای {await _cname(voted_for)} ثبت شد.")


async def donors_of(campaign_id: int) -> list[dict]:
    """آخرین رأی هر اهداکننده در این کمپین."""
    return await db.fetchall(
        "SELECT d.* FROM rescue_donations d WHERE d.campaign_id=? AND d.id IN "
        "(SELECT MAX(id) FROM rescue_donations WHERE campaign_id=? GROUP BY user_id)",
        (campaign_id, campaign_id))


async def close_campaign(bot, campaign: dict) -> None:
    """پایان کمپین: اکثریت رأی → پرداخت ۱۰٪ ذخیره + اعلان کانال (بدون مبلغ ذخیره)."""
    cid = campaign["id"]
    donors = await donors_of(cid)
    tally: dict[int, int] = {}
    for d in donors:
        tally[d["voted_for"]] = tally.get(d["voted_for"], 0) + 1
    winner = None
    if tally:
        top = max(tally.values())
        leaders = [k for k, v in tally.items() if v == top]
        if len(leaders) == 1:  # اکثریت با یک نفر
            winner = leaders[0]
    payout = 0
    if winner:
        pct = float(await get_setting("rescue_payout_percent", "10")) / 100
        reserve = await reserve_amount()
        payout = int(reserve * pct)
        if payout > 0:
            await db.execute("UPDATE users SET money=money+? WHERE id=?", (payout, winner))
    await db.execute(
        "UPDATE rescue_campaigns SET status='closed', winner_id=?, distributed=?, closed_at=? WHERE id=?",
        (winner, payout, iso(), cid))
    wc = await get_country(winner) if winner else None
    voters = []
    for d in donors:
        voters.append(await _cname(d["user_id"]))
    text = "🏥 <b>سازمان نجات — نتیجه حمایت از جنگ‌زدگان</b>\n\n"
    if wc:
        text += (f"🤲 کشورهای حامی تصمیم گرفتند کمک سازمان را به "
                 f"{wc['flag']} <b>{wc['name']}</b> برسانند.\n")
    else:
        text += "🗳 اکثریتی شکل نگرفت؛ در این نوبت کمکی پرداخت نشد.\n"
    if voters:
        text += "👥 کشورهای رأی‌دهنده: " + "، ".join(voters) + "\n"
    text += "\n(مقدار ذخیره سازمان محرمانه است)"
    await log_event("rescue", f"کمپین نجات #{cid} بسته شد؛ برنده: {wc['name'] if wc else '—'}")
    if bot:
        await announce_img(bot, text, "rescue")
        if winner:
            try:
                await bot.send_message(
                    winner, f"🎁 سازمان نجات کمکی به کشور شما پرداخت! (مقدار: مخفی — خزانه را ببینید)")
            except Exception:
                pass


async def _cname(user_id: int) -> str:
    c = await get_country(user_id)
    return f"{c['flag']} {c['name']}" if c else "؟"

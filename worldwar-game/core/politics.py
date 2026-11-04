"""سیاست و رهبری — رئیس‌جمهور هر کشور، ترور رهبر، انقلاب و مهار آن.

چرخهٔ کار:
  ترور موفق رهبر (سایبری) → کشور وارد «انقلاب» می‌شود (شدت + مهلت) →
  بازیکن باید سریع یکی از سه راه را انتخاب کند:
    ۱) انتخابات فوری و انتخاب رئیس‌جمهور جدید
    ۲) سرکوب با پول‌پاشی (هر پرداخت شدت را کم می‌کند)
    ۳) سرکوب نظامی با ارتش (شانس‌دار، تلفات سرباز)
  اگر مهلت تمام شود و کاری نکند، انقلاب پیروز می‌شود: افت شدید رضایت،
  غارت بخشی از خزانه و روی کار آمدن «شورای انقلابی».
"""
from __future__ import annotations

import random

from core.db import db, get_setting, set_setting
from core.economy import announce, get_country, get_state
from core.events import log_event
from core.utils import add_hours, clamp, fmt, fmt_hm, hours_ago, hours_left, iso

# شغل‌ها/گرایش‌های نامزدهای انتخابات و اثر فوری هرکدام
CANDIDATE_KINDS = [
    ("economist", "💰 اقتصاددان", "کاهش شدت انقلاب با بستهٔ اقتصادی و آرام‌سازی بازارها", 40, 6),
    ("general", "🎖 سرلشکر", "سرکوب سریع ناآرامی‌ها با نیروی ارتش", 55, -2),
    ("populist", "🗣 سیاستمدار مردمی", "آرام‌کردن خیابان‌ها با وعده‌های مردمی", 35, 14),
]

ACTING_TITLES = ("کفیل", "شورا")


# ─── رهبر ───


async def country_leader(country: dict | None) -> dict:
    """اطلاعات رهبر یک کشور: عنوان، نام و زمان شروع."""
    if not country:
        return {"title": "—", "name": "—", "since": ""}
    return {
        "title": country.get("leader_title") or "رئیس‌جمهور",
        "name": country.get("leader_name") or "کفیل موقت",
        "since": country.get("leader_since") or "",
    }


async def my_leader(user_id: int) -> dict:
    return await country_leader(await get_country(user_id))


async def all_leaders() -> list[dict]:
    """فهرست رهبران همهٔ کشورها (برای نمایش در منو و کانال)."""
    rows = await db.fetchall(
        "SELECT c.*, u.id AS player_id FROM countries c LEFT JOIN users u ON u.country_id=c.id "
        "WHERE c.is_active=1 ORDER BY c.name")
    out = []
    for r in rows:
        leader = await country_leader(r)
        rev = await db.fetchone(
            "SELECT * FROM revolutions WHERE country_id=? AND status='active' ORDER BY id DESC LIMIT 1",
            (r["id"],))
        out.append({**r, "leader": leader, "revolution": rev})
    return out


def _leader_pool() -> list[str]:
    from core.seed import LEADER_POOL
    return list(LEADER_POOL)


async def _new_leader_name(exclude: str = "") -> str:
    pool = [n for n in _leader_pool() if n != exclude] or _leader_pool()
    return random.choice(pool)


async def set_leader(country_id: int, name: str, title: str = "رئیس‌جمهور") -> None:
    await db.execute(
        "UPDATE countries SET leader_name=?, leader_title=?, leader_since=? WHERE id=?",
        (name, title, iso(), country_id))


# ─── انقلاب ───


async def active_revolution(user_id: int) -> dict | None:
    rows = await db.fetchall(
        "SELECT * FROM revolutions WHERE user_id=? AND status='active' ORDER BY id DESC", (user_id,))
    return rows[0] if rows else None


async def income_multiplier(user_id: int) -> float:
    """ضریب درآمد در زمان انقلاب (۵۵٪ پیش‌فرض)."""
    if await active_revolution(user_id):
        try:
            return float(await get_setting("revolution_income_penalty", "0.55"))
        except (TypeError, ValueError):
            return 0.55
    return 1.0


async def start_revolution(user_id: int, trigger: str = "assassination",
                           bot=None, by_user: int | None = None) -> dict:
    """شروع انقلاب در کشور یک بازیکن؛ اگر از قبل انقلاب فعال باشد، شدت بالا می‌رود."""
    country = await get_country(user_id)
    if not country:
        return {}
    minutes = int(float(await get_setting("revolution_minutes", "30")))
    severity = int(float(await get_setting("revolution_initial_severity", "65")))
    existing = await active_revolution(user_id)
    if existing:
        severity = min(100, int(existing["severity"]) + 15)
        await db.execute("UPDATE revolutions SET severity=?, ends_at=? WHERE id=?",
                         (severity, add_hours(minutes / 60), existing["id"]))
        rev_id = existing["id"]
    else:
        rev_id = await db.execute(
            "INSERT INTO revolutions(user_id, country_id, severity, started_at, ends_at, status, trigger) "
            "VALUES(?,?,?,?,?, 'active', ?)",
            (user_id, country["id"], severity, iso(), add_hours(minutes / 60), trigger))
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-8) WHERE user_id=?",
                         (user_id,))
    await log_event("politics", f"انقلاب در {country['name']} آغاز شد (شدت {severity}٪)")
    if bot:
        await announce(
            bot,
            f"🔥 <b>انقلاب در {country['flag']} {country['name']}!</b>\n\n"
            f"{'ترور' if trigger == 'assassination' else 'بحران'} رهبر کشور، پایتخت را به آشوب کشید.\n"
            f"شدت ناآرامی: <b>{severity}٪</b> | مهلت مهار: <b>{minutes} دقیقه</b>\n"
            "دولت باید فوراً رئیس‌جمهور جدید انتخاب کند یا انقلاب را سرکوب کند.",
            section="revolution")
        try:
            from gamebot.common import dm
            await dm(bot, user_id,
                     f"🔥 <b>انقلاب در کشور شما!</b>\n\n"
                     f"رهبر کشور از میان رفت و ناآرامی اوج گرفت.\n"
                     f"شدت انقلاب: <b>{severity}٪</b>\n"
                     f"⏳ تنها <b>{minutes} دقیقه</b> فرصت دارید تا با «🏛 رهبری و انقلاب» "
                     "رئیس‌جمهور جدید انتخاب کنید یا انقلاب را سرکوب کنید.")
        except Exception:
            pass
    return {"id": rev_id, "severity": severity, "minutes": minutes}


async def _close(rev: dict, status: str, outcome: str) -> None:
    await db.execute("UPDATE revolutions SET status=?, outcome=?, ends_at=? WHERE id=?",
                     (status, outcome, iso(), rev["id"]))


async def _severity_after(rev: dict, delta: int) -> int:
    new_sev = clamp(int(rev["severity"]) - delta, 0, 100)
    await db.execute("UPDATE revolutions SET severity=? WHERE id=?", (new_sev, rev["id"]))
    return new_sev


async def revolution_status(user_id: int) -> dict:
    """خلاصهٔ وضعیت انقلاب برای منوها."""
    rev = await active_revolution(user_id)
    if not rev:
        return {"active": False, "severity": 0, "left": "", "id": 0}
    return {"active": True, "severity": int(rev["severity"]), "id": rev["id"],
            "left": fmt_hm(hours_left(rev["ends_at"])) if rev.get("ends_at") else "—",
            "ends_at": rev.get("ends_at"), "trigger": rev.get("trigger")}


# ─── انتخابات ───


def candidates(rev_id: int) -> list[dict]:
    """سه نامزد ثابت برای هر انقلاب (بر اساس شناسهٔ انقلاب)."""
    pool = _leader_pool()
    out = []
    for i, (key, label, desc, severity_cut, satisfaction) in enumerate(CANDIDATE_KINDS):
        name = pool[(rev_id * 3 + i) % len(pool)]
        out.append({"key": key, "label": label, "desc": desc,
                    "severity_cut": severity_cut, "satisfaction": satisfaction,
                    "name": name, "idx": i})
    return out


async def elect_president(user_id: int, idx: int, bot=None) -> tuple[bool, str]:
    """انتخاب فوری رئیس‌جمهور جدید؛ انقلاب با آرام‌سازی خاتمه می‌یابد."""
    country = await get_country(user_id)
    if not country:
        return False, "❌ کشوری ندارید."
    rev = await active_revolution(user_id)
    if not rev:
        leader = await country_leader(country)
        if (leader["title"] or "") not in ACTING_TITLES and \
                "کفیل" not in (leader["name"] or "") and "شورا" not in (leader["name"] or ""):
            return False, "🕊 انقلابی در جریان نیست — رهبر فعلی در قدرت است."
        rev = {"id": 0, "severity": 0}
    cands = candidates(rev["id"] or 1)
    if not (0 <= idx < len(cands)):
        return False, "❌ نامزد نامعتبر است."
    cand = cands[idx]
    await set_leader(country["id"], cand["name"], "رئیس‌جمهور")
    await db.execute(
        "UPDATE states SET satisfaction=MIN(100, satisfaction+?) WHERE user_id=?",
        (cand["satisfaction"], user_id))
    if rev.get("id"):
        await _close(rev, "resolved", f"انتخابات — {cand['name']} ({cand['key']})")
    await log_event("politics", f"{country['name']} رئیس‌جمهور جدید خود را انتخاب کرد: {cand['name']}")
    msg = (f"🗳 <b>{cand['label']} {cand['name']} رئیس‌جمهور {country['name']} شد!</b>\n\n"
           f"🧠 {cand['desc']}\n"
           f"😊 رضایت: {'+' if cand['satisfaction'] >= 0 else ''}{cand['satisfaction']}\n"
           "✅ انقلاب با مسیر سیاسی مهار شد و کشور به آرامش بازگشت.")
    if bot:
        await announce(
            bot,
            f"🗳 <b>انتخابات فوری در {country['flag']} {country['name']}</b>\n\n"
            f"{cand['label']} <b>{cand['name']}</b> با رأی اضطراری مجلس به ریاست‌جمهوری رسید "
            "و ناآرامی‌ها را پایان داد.",
            section="politics")
    return True, msg


# ─── سرکوب ───


async def suppress_with_money(user_id: int, bot=None) -> tuple[bool, str]:
    """پول‌پاشی: هر پرداخت بخشی از شدت انقلاب را کم می‌کند."""
    country = await get_country(user_id)
    rev = await active_revolution(user_id)
    if not rev or not country:
        return False, "🕊 انقلاب فعالی وجود ندارد."
    severity = int(rev["severity"])
    cost = max(1, int(severity)) * 1_200_000
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, (f"❌ برای این مرحله {fmt(cost)} پول لازم است (خزانه شما: {fmt(money)}).\n"
                       "می‌توانید مبلغ کمتری جمع کنید یا از سرکوب نظامی استفاده کنید.")
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    await db.execute("UPDATE revolutions SET money_spent=money_spent+? WHERE id=?", (cost, rev["id"]))
    new_sev = await _severity_after(rev, 30)
    await db.execute("UPDATE states SET satisfaction=MIN(100, satisfaction+4) WHERE user_id=?",
                     (user_id,))
    if new_sev <= 0:
        await _close(rev, "suppressed", "پول‌پاشی")
        await log_event("politics", f"{country['name']} انقلاب را با پول‌پاشی سرکوب کرد")
        if bot:
            await announce(bot, f"💸 <b>انقلاب در {country['flag']} {country['name']} سرکوب شد</b>\n"
                                "دولت با بستهٔ مالی گسترده خیابان‌ها را آرام کرد.", section="politics")
        return True, (f"✅ انقلاب با پول‌پاشی کامل سرکوب شد!\n💰 هزینه: {fmt(cost)}\n"
                      "اکنون با «🗳 انتخابات» رئیس‌جمهور جدید را انتخاب کنید.")
    return True, (f"💸 {fmt(cost)} پول پاشی شد — شدت انقلاب به <b>{new_sev}٪</b> رسید.\n"
                  f"⏳ {fmt_hm(hours_left(rev['ends_at']))} فرصت باقی است.")


async def suppress_with_force(user_id: int, bot=None) -> tuple[bool, str]:
    """سرکوب نظامی: شانس‌دار، تلفات سرباز و ریسک بالا بردن شدت."""
    from core.economy import army_power
    country = await get_country(user_id)
    rev = await active_revolution(user_id)
    if not rev or not country:
        return False, "🕊 انقلاب فعالی وجود ندارد."
    if rev.get("force_block_until") and rev["force_block_until"] > iso():
        return False, f"⏳ نیروها در حال بازآرایی هستند — {fmt_hm(hours_left(rev['force_block_until']))} دیگر تلاش کنید."
    atk, dfn, _ = await army_power(user_id)
    force = atk * 0.6 + dfn * 0.4
    severity = int(rev["severity"])
    chance = clamp(force / (force + severity * 4000), 0.10, 0.95)
    success = random.random() < chance
    soldiers = await db.fetchall(
        "SELECT a.item_id, a.quantity FROM player_assets a WHERE a.user_id=? AND a.item_type='soldier'",
        (user_id,))
    loss_ratio = 0.05 if success else 0.10
    from core import combat as combat_mod
    rows = [{"id": r["item_id"], "quantity": r["quantity"],
             "name": "سرباز", "emoji": "🪖"} for r in soldiers]
    lost_text, lost_units = await combat_mod.apply_losses(user_id, rows, loss_ratio, "soldier")
    await db.execute("UPDATE revolutions SET troops_lost=troops_lost+? WHERE id=?",
                     (lost_units, rev["id"]))
    if success:
        new_sev = await _severity_after(rev, 45)
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-3) WHERE user_id=?",
                         (user_id,))
        if new_sev <= 0:
            await _close(rev, "suppressed", "سرکوب نظامی")
            await set_leader(country["id"], await _new_leader_name(), "کفیل")
            await log_event("politics", f"{country['name']} انقلاب را با زور سرکوب کرد")
            if bot:
                await announce(bot, f"🎖 <b>سرکوب نظامی در {country['flag']} {country['name']}</b>\n"
                                    "ارتش ناآرامی‌ها را در هم شکست؛ یک کفیل موقت ادارهٔ کشور را گرفت.",
                               section="politics")
        return True, (f"🎖 سرکوب نظامی موفق بود! شدت انقلاب به <b>{new_sev}٪</b> رسید.\n"
                      + (f"💥 تلفات: {' ، '.join(lost_text[:3])}\n" if lost_text else "")
                      + ("" if new_sev > 0 else "✅ انقلاب سرکوب شد — برای تعیین رئیس‌جمهور «🗳 انتخابات» را بزنید."))
    await _severity_after(rev, -10)
    await db.execute("UPDATE revolutions SET force_block_until=? WHERE id=?",
                     (add_hours(0.05), rev["id"]))  # ۳ دقیقه
    return True, (f"❌ سرکوب نظامی شکست خورد (شانس {round(chance * 100)}٪) — "
                  "شدت انقلاب بالا رفت.\n"
                  + (f"💥 تلفات: {' ، '.join(lost_text[:3])}" if lost_text else ""))


# ─── ترور ───


async def assassination_cooldown_ok(attacker_id: int, defender_id: int) -> bool:
    hours = float(await get_setting("assassination_cooldown_hours", "6"))
    last = await db.fetchone(
        "SELECT created_at FROM cyber_ops WHERE attacker_id=? AND defender_id=? AND kind='assass' "
        "ORDER BY id DESC LIMIT 1", (attacker_id, defender_id))
    if last and hours_ago(last["created_at"]) < hours:
        return False
    return True


async def assassinate(attacker_id: int, defender_id: int, bot=None) -> tuple[bool, str]:
    """عملیات ترور رئیس‌جمهور کشور هدف؛ در صورت موفقیت انقلاب آغاز می‌شود."""
    from core.economy import army_power
    from gamebot.handlers.war import cyber_chance
    t_country = await get_country(defender_id)
    a_country = await get_country(attacker_id)
    if not t_country or not a_country:
        return False, "❌ کشور هدف یافت نشد."
    if not await assassination_cooldown_ok(attacker_id, defender_id):
        return False, "⏳ هر ۶ ساعت یک عملیات ترور روی هر کشور ممکن است."
    leader = await country_leader(t_country)
    _a, _d, my_cyber = await army_power(attacker_id)
    _a2, _d2, their_cyber = await army_power(defender_id)
    chance = cyber_chance(my_cyber, their_cyber) * 0.8  # ترور سخت‌تر از هک است
    success = random.random() * 100 < chance
    await db.execute(
        "INSERT INTO cyber_ops(attacker_id, defender_id, kind, success, amount) VALUES(?,?,?,?,?)",
        (attacker_id, defender_id, "assass", 1 if success else 0, 0))
    if not success:
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-3) WHERE user_id=?",
                         (attacker_id,))
        if bot:
            await announce(bot,
                           f"🕶 <b>ترور ناکام</b>\n\nتیم عملیات {a_country['flag']} <b>{a_country['name']}</b> "
                           f"در ترور {leader['title']} {t_country['flag']} {t_country['name']} شناسایی و منهدم شد.",
                           section="cyber")
        return False, (f"❌ ترور {leader['title']} {t_country['flag']} {t_country['name']} ناموفق بود "
                       f"(شانس {round(chance)}٪).\n−۳٪ رضایت ملی شما.")
    # ترور موفق: رهبر کشته شد و انقلاب آغاز می‌شود
    await set_leader(t_country["id"], "— (ترور شد)", "نامعلوم")
    await db.execute("UPDATE states SET leader_block_until=?, satisfaction=MAX(0, satisfaction-10) "
                     "WHERE user_id=?", (add_hours(1), defender_id))
    info = await start_revolution(defender_id, "assassination", bot, by_user=attacker_id)
    if bot:
        await announce(
            bot,
            f"🕶 <b>ترور موفق رئیس‌جمهور {t_country['flag']} {t_country['name']}!</b>\n\n"
            f"💀 {leader['title']} <b>{leader['name']}</b> در یک عملیات نفوذی از پای درآمد.\n"
            f"🔥 کشور در وضعیت انقلاب است (شدت {info.get('severity', 0)}٪) — "
            f"مهلت مهار {info.get('minutes', 30)} دقیقه.",
            section="cyber")
    return True, (f"✅ <b>ترور موفق!</b>\n\n💀 {leader['title']} <b>{leader['name']}</b> از پای درآمد و "
                  f"{t_country['flag']} {t_country['name']} وارد انقلاب شد "
                  f"(شدت {info.get('severity', 0)}٪، مهلت {info.get('minutes', 30)} دقیقه).\n"
                  "🕶 ردپای شما پاک شد — سازمان ملل مدرکی ندارد.")


# ─── تیک زمان‌بند ───


async def revolution_tick(bot=None) -> int:
    """بستن انقلاب‌هایی که مهلتشان تمام شده (پیروزی انقلاب)."""
    active = await db.fetchall("SELECT * FROM revolutions WHERE status='active'")
    closed = 0
    for rev in active:
        if not rev.get("ends_at") or rev["ends_at"] > iso():
            continue
        user_id = rev["user_id"]
        country = await get_country(user_id)
        sat_drop = int(float(await get_setting("revolution_success_satisfaction", "20")))
        money_pct = float(await get_setting("revolution_success_money_pct", "0.15"))
        user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
        stolen = int(((user or {}).get("money") or 0) * money_pct)
        if stolen > 0:
            await db.execute("UPDATE users SET money=MAX(0, money-?) WHERE id=?", (stolen, user_id))
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-?) WHERE user_id=?",
                         (sat_drop, user_id))
        await _close(rev, "succeeded", "پیروزی انقلاب — شورای انقلابی")
        if country:
            await set_leader(country["id"], "شورای انقلابی موقت", "شورا")
            await log_event("politics", f"انقلاب در {country['name']} پیروز شد")
        if bot and country:
            await announce(
                bot,
                f"🔥 <b>انقلاب پیروز شد!</b>\n\n"
                f"دولت {country['flag']} <b>{country['name']}</b> سقوط کرد و «شورای انقلابی» قدرت را گرفت.\n"
                f"📉 رضایت: −{sat_drop} | 💸 غارت خزانه: {fmt(stolen)}",
                section="revolution")
            try:
                from gamebot.common import dm
                await dm(bot, user_id,
                         f"🔥 انقلاب پیروز شد و دولت شما سقوط کرد!\n"
                         f"💰 {fmt(stolen)} از خزانه غارت شد و شورای انقلابی قدرت را گرفت.\n"
                         "از «🏛 رهبری و انقلاب» می‌توانید رئیس‌جمهور جدید انتخاب کنید.")
            except Exception:
                pass
        closed += 1
    return closed

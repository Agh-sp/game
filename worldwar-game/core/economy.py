"""منطق مشترک بازی: رضایت، درآمد، قدرت نظامی، پیش‌رفت روزانه و اعلان‌ها."""
from core.db import db, get_setting
from core.utils import iso, now, day_str, jloads, clamp

POP_UNIT = 10_000  # مصرف هر بخش = جمعیت ÷ ۱۰هزار «واحد»

# ─── وضعیت کشور ───


async def get_user(user_id: int) -> dict | None:
    return await db.fetchone("SELECT * FROM users WHERE id=?", (user_id,))


async def get_state(user_id: int) -> dict:
    row = await db.fetchone("SELECT * FROM states WHERE user_id=?", (user_id,))
    if row:
        return row
    await db.execute("INSERT OR IGNORE INTO states(user_id) VALUES(?)", (user_id,))
    return await db.fetchone("SELECT * FROM states WHERE user_id=?", (user_id,))


async def get_country(user_id: int) -> dict | None:
    return await db.fetchone(
        "SELECT c.* FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (user_id,),
    )


async def my_gov_religion(user_id: int) -> tuple[dict | None, dict | None]:
    state = await get_state(user_id)
    gov = await db.fetchone("SELECT * FROM governments WHERE id=?", (state["government_id"],)) if state["government_id"] else None
    rel = await db.fetchone("SELECT * FROM religions WHERE id=?", (state["religion_id"],)) if state["religion_id"] else None
    return gov, rel


def gov_effect(gov: dict | None, key: str, default=0.0) -> float:
    if not gov:
        return default
    return float(jloads(gov.get("effects"), {}).get(key, default))


def rel_effect(rel: dict | None, key: str, default=0.0) -> float:
    if not rel:
        return default
    return float(jloads(rel.get("effects"), {}).get(key, default))


# ─── دارایی‌ها ───


async def asset_qty(user_id: int, item_type: str, item_id: int) -> int:
    row = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
        (user_id, item_type, item_id),
    )
    return row["quantity"] if row else 0


async def add_asset(user_id: int, item_type: str, item_id: int, qty: int) -> None:
    await db.execute(
        "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
        (user_id, item_type, item_id, qty, qty),
    )


async def sub_asset(user_id: int, item_type: str, item_id: int, qty: int) -> bool:
    row = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
        (user_id, item_type, item_id),
    )
    if not row or row["quantity"] < qty:
        return False
    new = row["quantity"] - qty
    if new <= 0:
        await db.execute("DELETE FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
                         (user_id, item_type, item_id))
    else:
        await db.execute("UPDATE player_assets SET quantity=? WHERE user_id=? AND item_type=? AND item_id=?",
                         (new, user_id, item_type, item_id))
    return True


async def assets_of(user_id: int, item_type: str) -> list[dict]:
    return await db.fetchall(
        "SELECT a.*, b.sector, b.name, b.emoji, b.satisfaction AS b_sat, b.capacity, "
        "e.name AS eq_name, e.emoji AS eq_emoji, e.attack_power, e.defense_power, "
        "e.cyber_power AS eq_cyber, e.speed, st.name AS soldier_name, st.emoji AS soldier_emoji, "
        "st.power, st.cyber_power AS soldier_cyber "
        "FROM player_assets a "
        "LEFT JOIN buildings b ON a.item_type='building' AND b.id=a.item_id "
        "LEFT JOIN equipment e ON a.item_type='equipment' AND e.id=a.item_id "
        "LEFT JOIN soldier_types st ON a.item_type='soldier' AND st.id=a.item_id "
        "WHERE a.user_id=? AND a.item_type=? ORDER BY a.item_id",
        (user_id, item_type),
    )


async def project_done(user_id: int, building_id: int) -> bool:
    row = await db.fetchone(
        "SELECT id FROM player_projects WHERE user_id=? AND building_id=? AND status='done'",
        (user_id, building_id),
    )
    return row is not None


async def has_project_named(user_id: int, keyword: str) -> bool:
    row = await db.fetchone(
        "SELECT p.id FROM player_projects p JOIN buildings b ON b.id=p.building_id "
        "WHERE p.user_id=? AND p.status='done' AND b.name LIKE ?",
        (user_id, f"%{keyword}%"),
    )
    return row is not None


# ─── رضایت و زیرساخت ───


def consumption(population: int, blackout_hours: int = 0) -> int:
    """مصرف واحدها با احتساب قطعی (۳۵٪ کاهش مصرف به ازای قطعی کامل)."""
    base = population // POP_UNIT
    if blackout_hours:
        base = int(base * (1 - min(24, blackout_hours) / 24 * 0.35))
    return base


async def sector_capacity(user_id: int, sector: str) -> int:
    rows = await db.fetchall(
        "SELECT a.quantity, b.capacity FROM player_assets a "
        "JOIN buildings b ON b.id=a.item_id "
        "WHERE a.user_id=? AND a.item_type='building' AND b.sector=?",
        (user_id, sector),
    )
    return sum(r["quantity"] * (r["capacity"] or 0) for r in rows)


async def satisfaction_recompute(user_id: int) -> float:
    """محاسبه و ذخیره رضایت مردم بر اساس همه عوامل."""
    state = await get_state(user_id)
    country = await get_country(user_id)
    if not country:
        return state["satisfaction"]
    gov, rel = await my_gov_religion(user_id)
    sat = 50.0

    # ساختمان‌ها
    for r in await assets_of(user_id, "building"):
        sat += (r["b_sat"] or 0) * min(r["quantity"], 10)

    # کمبود زیرساخت (حداکثر ۱۵ واحد رضایت به ازای هر بخش)
    pop = country["population"] or 1
    for sector, cut_key in (("power", "blackout_power"), ("water", "blackout_water"), ("gas", "blackout_gas")):
        cap = await sector_capacity(user_id, sector)
        cons = consumption(pop, state.get(cut_key) or 0)
        if cons > 0 and cap < cons:
            sat -= min(15.0, (cons - cap) / cons * 15)

    # قطعی‌ها
    sat -= (state.get("blackout_power") or 0) * 0.4
    sat -= (state.get("blackout_water") or 0) * 0.6
    sat -= (state.get("blackout_gas") or 0) * 0.5

    # یارانه و مالیات
    subsidy = state.get("subsidy_daily") or 0
    threshold = max(1, int(pop * 0.0004))
    if subsidy > 0:
        sat += min(10.0, subsidy / threshold * 6)
    sat -= (state.get("tax_rate") or 0) * 25

    # قوانین + اثر دین/حکومت
    chosen = jloads(state.get("chosen_laws"), {})
    if chosen:
        law_rows = await db.fetchall("SELECT * FROM laws WHERE id IN (" + ",".join("?" * len(chosen)) + ")",
                                     tuple(int(k) for k in chosen.keys())) if chosen else []
        for law in law_rows:
            opts = jloads(law["options"], [])
            idx = int(chosen.get(str(law["id"]), -1))
            if 0 <= idx < len(opts):
                label, base_eff = opts[idx]["label"], opts[idx].get("satisfaction", 0)
                sat += base_eff
                if rel:
                    for le, delta in jloads(law["religion_effects"], {}).get(rel["name"], {}).items():
                        if le == label:
                            sat += delta + rel_effect(rel, "laws", 0) * 0.5
                if gov:
                    for ge, delta in jloads(law["government_effects"], {}).get(gov["name"], {}).items():
                        if ge == label:
                            sat += delta

    # دین و حکومت
    sat += rel_effect(rel, "satisfaction") + gov_effect(gov, "satisfaction")

    sat = clamp(sat, 0, 100)
    await db.execute("UPDATE states SET satisfaction=? WHERE user_id=?", (round(sat, 1), user_id))
    return sat


# ─── درآمد و ارز ───


async def income_amount(user_id: int) -> int:
    user = await get_user(user_id)
    country = await get_country(user_id)
    state = await get_state(user_id)
    if not user or not country:
        return 0
    base = float(await get_setting("income_base", "100"))
    sat = state["satisfaction"] or 50
    tax = state.get("tax_rate") or 0
    return int(country["population"] / 1000 * base * (0.5 + sat / 100) * (1 + tax * 0.5))


# ─── قدرت نظامی ───


async def army_power(user_id: int) -> tuple[float, float, float]:
    """(حمله، دفاع، سایبری) با احتساب حکومت و پروژه‌ها."""
    gov, _rel = await my_gov_religion(user_id)
    atk = dfn = cyb = 0.0
    for r in await assets_of(user_id, "equipment"):
        qty = r["quantity"]
        atk += qty * (r["attack_power"] or 0)
        dfn += qty * (r["defense_power"] or 0)
        cyb += qty * (r["eq_cyber"] or 0)
    for r in await assets_of(user_id, "soldier"):
        qty = r["quantity"]
        atk += qty * (r["power"] or 0)
        cyb += qty * (r["soldier_cyber"] or 0)
    cyb += 10_000  # پایه

    atk *= 1 + gov_effect(gov, "attack") / 100
    dfn *= 1 + gov_effect(gov, "defense") / 100
    if await has_project_named(user_id, "هوش مصنوعی"):
        atk *= 1.10
    return round(atk), round(dfn), round(cyb)


async def power_score(user_id: int) -> float:
    user = await get_user(user_id)
    if not user:
        return 0
    state = await get_state(user_id)
    atk, dfn, _ = await army_power(user_id)
    return atk + dfn + user["money"] / 10 + (state["satisfaction"] or 0) * 10_000


async def veto_users() -> list[int]:
    """۳ کشور قدرتمند — رایشان در سازمان ملل ۲ برابر است."""
    rows = await db.fetchall(
        "SELECT u.id FROM users u WHERE u.country_id IS NOT NULL AND u.banned=0"
    )
    scores = []
    for r in rows:
        scores.append((await power_score(r["id"]), r["id"]))
    scores.sort(reverse=True)
    return [uid for _s, uid in scores[:3]]


# ─── مسدودی‌ها ───


async def is_leader_blocked(user_id: int) -> bool:
    state = await get_state(user_id)
    return bool(state.get("leader_block_until") and state["leader_block_until"] > iso())


async def is_jammed(user_id: int) -> bool:
    state = await get_state(user_id)
    return bool(state.get("server_jam_until") and state["server_jam_until"] > iso())


async def is_disarmed(user_id: int) -> bool:
    state = await get_state(user_id)
    return bool(state.get("disarmed_until") and state["disarmed_until"] > iso())


async def at_war(user_id: int, other_id: int) -> bool:
    """آیا دو کشور در جنگ فعال هستند؟"""
    if not user_id or not other_id or user_id == other_id:
        return False
    row = await db.fetchone(
        "SELECT id FROM wars WHERE status='active' AND "
        "((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?))",
        (user_id, other_id, other_id, user_id))
    return row is not None


# ─── پیشرفت روزانه ───


async def bump_progress(user_id: int, field: str, amount: int = 1) -> None:
    day = day_str()
    await db.execute(
        "INSERT INTO daily_progress(user_id, day, login) VALUES(?,?,1) ON CONFLICT(user_id, day) DO NOTHING",
        (user_id, day),
    )
    await db.execute(
        f"UPDATE daily_progress SET {field} = {field} + ? WHERE user_id=? AND day=?",
        (amount, user_id, day),
    )


async def get_progress(user_id: int) -> dict:
    row = await db.fetchone(
        "SELECT * FROM daily_progress WHERE user_id=? AND day=?",
        (user_id, day_str()),
    )
    return row or {"login": 0, "built": 0, "trained": 0, "bought": 0, "statements": 0, "voted": 0, "war": 0}


# ─── اعلان کانال ───


async def announce(bot, text: str) -> None:
    """ارسال اعلان به کانال تنظیم‌شده (اگر تنظیم شده باشد)."""
    channel = await get_setting("announcement_channel", "")
    if not channel:
        return
    try:
        await bot.send_message(channel, text)
    except Exception:
        pass


# ─── تکمیل پروژه‌های تمام‌شده ───


async def settle_projects(user_id: int, bot=None) -> list[str]:
    """پروژه‌های به‌اتمام‌رسیده را نهایی می‌کند و خبر افتتاح را اعلام می‌کند."""
    rows = await db.fetchall(
        "SELECT p.*, b.name AS bname, b.emoji AS bemoji, b.satisfaction AS bsat "
        "FROM player_projects p JOIN buildings b ON b.id=p.building_id "
        "WHERE p.user_id=? AND p.status='in_progress' AND p.completes_at<=?",
        (user_id, iso()),
    )
    opened = []
    for r in rows:
        await db.execute("UPDATE player_projects SET status='done' WHERE id=?", (r["id"],))
        opened.append(f"{r['bemoji']} {r['bname']}")
        if bot:
            await announce(bot, f"🎉 افتتاح «{r['bname']}» در کشور اعلام شد.")
    if opened:
        await satisfaction_recompute(user_id)
    return opened


async def settle_trainings(user_id: int) -> int:
    """سربازان آموزش‌دیده را به دارایی اضافه می‌کند؛ تعداد را برمی‌گرداند."""
    rows = await db.fetchall(
        "SELECT * FROM soldier_trainings WHERE user_id=? AND completes_at<=?",
        (user_id, iso()),
    )
    for r in rows:
        await add_asset(user_id, "soldier", r["type_id"], r["count"])
        await db.execute("DELETE FROM soldier_trainings WHERE id=?", (r["id"],))
    return len(rows)

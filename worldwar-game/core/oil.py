"""نفت — دکل، ارتقای تجهیزات استخراج، فروش خودکار ۱۰ دقیقه‌ای (درآمد میلیونی)، اکتشاف و فروش دستی.

هر کشور یک «پایهٔ درآمد نفتی» دارد (`countries.oil_income_base`، بین ۱ تا ۲۰ میلیون)
که در هر فروش خودکار به خزانه واریز می‌شود: آمریکا/چین/روسیه بالای ۱۰ میلیون،
کشورهای کوچک از ۱ میلیون شروع می‌کنند. با ارتقای تجهیزات استخراج، هم بشکهٔ
بیشتری استخراج می‌شود و هم درصدی به درآمد فروش اضافه می‌گردد؛ هزینهٔ هر ارتقا
مرحله‌به‌مرحله گران‌تر می‌شود (ضریب ۱.۶).
"""
from core.db import db, get_setting
from core.economy import asset_qty, get_country, get_state
from core.events import log_event
from core.utils import fmt, fmt_money, hours_ago, iso


async def rig_count(user_id: int) -> int:
    row = await db.fetchone("SELECT id FROM buildings WHERE name='دکل نفتی'")
    return await asset_qty(user_id, "building", row["id"]) if row else 0


async def oil_menu_data(user_id: int) -> dict:
    state = await get_state(user_id)
    country = await get_country(user_id)
    per_rig = await per_rig_barrels(user_id)
    rigs = await rig_count(user_id)
    return {
        "reserve": (country or {}).get("oil_reserve") or 0,
        "richness": (country or {}).get("oil_richness") or 0,
        "stock": state.get("oil_stock") or 0,
        "rigs": rigs,
        "per_rig": per_rig,
        "per_tick": rigs * per_rig,
    }


async def extraction_tick(user_id: int) -> int:
    """استخراج خودکار: هر دکل در هر تیک بشکه‌ای از مخزن زیرزمینی به انبار می‌برد."""
    country = await get_country(user_id)
    if not country:
        return 0
    per_rig = await per_rig_barrels(user_id)
    rigs = await rig_count(user_id)
    if rigs <= 0 or per_rig <= 0:
        return 0
    reserve = country.get("oil_reserve") or 0
    if reserve <= 0:
        return 0
    take = min(rigs * per_rig, reserve)
    await db.execute("UPDATE countries SET oil_reserve=oil_reserve-? WHERE id=?",
                     (take, country["id"]))
    await db.execute("UPDATE states SET oil_stock=oil_stock+? WHERE user_id=?",
                     (take, user_id))
    return take


async def explore(user_id: int) -> tuple[bool, str]:
    """اکتشاف نفتی: پرداخت هزینه + شانس بر اساس نفت‌خیزی کشور."""
    country = await get_country(user_id)
    if not country:
        return False, "کشوری ندارید."
    cost = int(await get_setting("oil_exploration_cost", "50000000"))
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    if (user or {}).get("money", 0) < cost:
        return False, f"❌ بودجه کافی نیست — هزینه اکتشاف: {fmt(cost)}"
    richness = float(country.get("oil_richness") or 0)
    add = int(await get_setting("oil_exploration_add", "2000000000"))
    import random
    success = random.random() * 100 < richness
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    if success:
        await db.execute("UPDATE countries SET oil_reserve=oil_reserve+? WHERE id=?",
                         (add, country["id"]))
        await log_event("oil", f"{country['name']} با اکتشاف نفتی {fmt(add)} بشکه ذخیره جدید یافت")
        return True, (f"🛢 <b>اکتشاف موفق!</b> {fmt(add)} بشکه به مخزن زیرزمینی شما اضافه شد.\n"
                      f"💰 هزینه: {fmt(cost)}")
    return False, (f"⛏ اکتشاف <b>ناموفق</b> بود — نفت جدیدی پیدا نشد (شانس شما: {round(richness)}٪).\n"
                   f"💰 هزینه: {fmt(cost)}")


async def create_offer(seller_id: int, barrels: int, price_money: int, price_coins: int) -> int:
    oid = await db.execute(
        "INSERT INTO oil_offers(seller_id, barrels, price_money, price_coins) VALUES(?,?,?,?)",
        (seller_id, barrels, price_money, price_coins))
    c = await get_country(seller_id)
    await log_event("oil", f"{c['name'] if c else seller_id} عرضه {fmt(barrels)} بشکه نفت ثبت کرد")
    return oid


async def offers_text(user_id: int) -> tuple[str, list[list[tuple[str, str]]]]:
    offers = await db.fetchall(
        "SELECT o.*, c.name, c.flag FROM oil_offers o JOIN countries c ON c.owner_id=o.seller_id "
        "WHERE o.status='open' ORDER BY o.id DESC LIMIT 15")
    lines = ["🛒 <b>بازار نفت — عرضه‌های باز</b>\n"]
    buttons = []
    if not offers:
        lines.append("— عرضه‌ای نیست —")
    for o in offers:
        if o["price_coins"]:
            price = f"🪙 {fmt(o['price_coins'])} سکه شاهی"
        else:
            price = f"💰 {fmt(o['price_money'])}"
        lines.append(f"• {o['flag']} {o['name']}: {fmt(o['barrels'])} بشکه ← {price}")
        if o["seller_id"] != user_id:
            buttons.append([(f"🛒 {o['name']} — {fmt(o['barrels'])} بشکه", f"g|oilbuy|{o['id']}")])
        else:
            buttons.append([(f"❌ لغو عرضه #{o['id']}", f"g|oilcan|{o['id']}")])
    return "\n".join(lines), buttons


# ─── کسب‌وکار نفت: سطح تجهیزات + فروش خودکار ───


async def ensure_business(user_id: int) -> dict:
    """ردیف کسب‌وکار نفتی بازیکن را می‌سازد/برمی‌گرداند."""
    row = await db.fetchone("SELECT * FROM oil_business WHERE user_id=?", (user_id,))
    if row:
        return row
    await db.execute("INSERT OR IGNORE INTO oil_business(user_id, level, auto_sell) VALUES(?,?,0)",
                     (user_id, 1))
    return await db.fetchone("SELECT * FROM oil_business WHERE user_id=?", (user_id,)) or {}


async def level_max() -> int:
    return int(float(await get_setting("oil_level_max", "12")))


async def upgrade_cost(level: int) -> int:
    """هزینهٔ ارتقا از سطح فعلی به سطح بعد — هر مرحله گران‌تر."""
    base = float(await get_setting("oil_level_base_cost", "30000000"))
    factor = float(await get_setting("oil_level_cost_factor", "1.6"))
    return int(base * (factor ** max(0, level - 1)))


async def level_barrel_mult(level: int) -> float:
    bonus = float(await get_setting("oil_level_barrel_bonus", "0.15"))
    return 1 + bonus * max(0, level - 1)


async def level_income_mult(level: int) -> float:
    bonus = float(await get_setting("oil_level_income_bonus", "0.12"))
    return 1 + bonus * max(0, level - 1)


async def per_rig_barrels(user_id: int) -> int:
    """بشکه استخراج هر دکل در هر تیک ۳۰ دقیقه‌ای (با احتساب سطح ارتقا)."""
    base = int(await get_setting("oil_rig_barrels_per_tick", "500"))
    biz = await ensure_business(user_id)
    return int(base * await level_barrel_mult(int(biz.get("level") or 1)))


async def sale_amount(user_id: int, barrels: int) -> dict:
    """مبلغ فروش برای `barrels` بشکه — **بدون سقف**: هر بشکه بیشتر، پول بیشتر.

    فرمول: پایهٔ نفتی کشور × سطح تجهیزات × (۰٫۳۵ + ۰٫۶۵ × بشکه/مرجع)
    یعنی ۵٬۰۰۰ بشکه = ۱ برابر پایه، ۵۰٬۰۰۰ بشکه = حدود ۷ برابر پایه.
    همیشه دست‌کم ۱ میلیون (درآمد فروش خودکار هرگز ریز نمی‌شود).
    """
    country = await get_country(user_id) or {}
    biz = await ensure_business(user_id)
    level = int(biz.get("level") or 1)
    base_m = int(country.get("oil_income_base") or 2)
    mult = await level_income_mult(level)
    need = max(1, int(float(await get_setting("oil_sale_need_barrels", "5000"))))
    ratio = max(0.0, barrels / need)
    amount = int(base_m * 1_000_000 * mult * (0.35 + 0.65 * ratio))
    if barrels > 0:
        amount = max(1_000_000, amount)
    return {"amount": amount, "base_millions": base_m, "level": level,
            "level_mult": round(mult, 2), "need": need, "ratio": round(ratio, 2)}


async def income_estimate(user_id: int) -> dict:
    """برآورد درآمد فروش خودکار بعدی (همهٔ بشکه‌های انبار فروخته می‌شود)."""
    state = await get_state(user_id)
    stock = int(state.get("oil_stock") or 0)
    calc = await sale_amount(user_id, stock)
    return {**calc, "income": calc["amount"],
            "income_millions": round(calc["amount"] / 1_000_000, 2),
            "stock": stock}


async def upgrade_business(user_id: int) -> tuple[bool, str]:
    """ارتقای تجهیزات استخراج (گران‌تر در هر مرحله)."""
    biz = await ensure_business(user_id)
    level = int(biz.get("level") or 1)
    cap = await level_max()
    if level >= cap:
        return False, f"🏆 تجهیزات استخراج شما در بالاترین سطح ({cap}) است."
    # ارتقا همیشه ممکن است (حتی قبل از ساخت اولین دکل) — سطح بالاتر یعنی
    # استخراج بیشتر از هر دکل و درآمد فروش بالاتر.
    cost = await upgrade_cost(level)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost:
        return False, (f"❌ هزینهٔ ارتقا به سطح {level + 1}: {fmt_money(cost)}\n"
                       f"خزانه شما: {fmt_money(money)}")
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost, user_id))
    await db.execute("UPDATE oil_business SET level=? WHERE user_id=?", (level + 1, user_id))
    country = await get_country(user_id)
    await log_event("oil", f"{country['name'] if country else user_id} تجهیزات استخراج نفت را به سطح "
                           f"{level + 1} ارتقا داد")
    nxt = await upgrade_cost(level + 1) if level + 1 < cap else 0
    per_rig = await per_rig_barrels(user_id)
    return True, (f"🛠 <b>ارتقای تجهیزات استخراج انجام شد!</b>\n\n"
                  f"📈 سطح جدید: <b>{level + 1}</b>/{cap}\n"
                  f"🛢 استخراج هر دکل: <b>{fmt(per_rig)}</b> بشکه در هر دوره\n"
                  f"💰 هزینه: {fmt_money(cost)}\n"
                  + (f"➡️ هزینهٔ ارتقای بعدی: <b>{fmt_money(nxt)}</b>" if nxt else "🏆 حداکثر سطح"))


async def toggle_auto_sell(user_id: int) -> tuple[bool, str]:
    """روشن/خاموش‌کردن تجارت خودکار نفت (درآمد هر ۱۰ دقیقه)."""
    biz = await ensure_business(user_id)
    if await rig_count(user_id) <= 0:
        return False, "❌ ابتدا یک دکل نفتی بسازید تا استخراج نفت شروع شود."
    new_state = 0 if int(biz.get("auto_sell") or 0) else 1
    await db.execute("UPDATE oil_business SET auto_sell=? WHERE user_id=?", (new_state, user_id))
    minutes = int(float(await get_setting("oil_auto_sell_minutes", "10")))
    if new_state:
        return True, (f"✅ <b>تجارت خودکار نفت روشن شد.</b>\n"
                      f"هر {minutes} دقیقه نفت انبار شده فروش می‌رود و درآمد آن (میلیونی) "
                      "به طور خودکار به خزانه واریز می‌شود.")
    return True, "⏸ تجارت خودکار نفت خاموش شد."


async def auto_sell_tick(bot=None) -> int:
    """فروش خودکار نفت هر کاربری که موعدش رسیده (پیش‌فرض هر ۱۰ دقیقه)."""
    minutes = max(1, int(float(await get_setting("oil_auto_sell_minutes", "10"))))
    rows = await db.fetchall(
        "SELECT ob.*, u.money, u.id AS uid FROM oil_business ob JOIN users u ON u.id=ob.user_id "
        "WHERE ob.auto_sell=1 AND u.banned=0")
    paid_total = 0
    for r in rows:
        if r["last_sale_at"] and hours_ago(r["last_sale_at"]) < minutes / 60:
            continue
        uid = int(r["uid"])
        if await rig_count(uid) <= 0:
            continue
        state = await get_state(uid)
        stock = int(state.get("oil_stock") or 0)
        if stock < 100:
            continue
        # 💰 همهٔ نفت انبار فروخته می‌شود (قبلاً فقط ۵٬۰۰۰ بشکه فروش می‌رفت)
        sold = stock
        calc = await sale_amount(uid, sold)
        amount = max(1_000_000, int(calc["amount"]))
        if amount <= 0:
            continue
        await db.execute("UPDATE states SET oil_stock=MAX(0, oil_stock-?) WHERE user_id=?",
                         (sold, uid))
        await db.execute("UPDATE users SET money=money+? WHERE id=?", (amount, uid))
        await db.execute(
            "UPDATE oil_business SET last_sale_at=?, last_income=?, total_income=total_income+?, "
            "sales=sales+1, barrels_sold=barrels_sold+? WHERE user_id=?",
            (iso(), amount, amount, sold, uid))
        paid_total += amount
        country = await get_country(uid)
        await log_event("oil", f"فروش خودکار نفت {country['name'] if country else uid}: "
                               f"{fmt(sold)} بشکه → {fmt_money(amount)}")
        if bot:
            try:
                from gamebot.common import dm
                await dm(bot, uid,
                         f"🛢 <b>درآمد فروش خودکار نفت</b>\n\n"
                         f"⛽ {fmt(sold)} بشکه نفت فروش رفت "
                         f"(سطح تجهیزات {calc['level']} — ×{calc['level_mult']}).\n"
                         f"💰 واریز به خزانه: <b>{fmt_money(amount)}</b> "
                         f"({round(amount / 1_000_000, 2)} میلیون)\n"
                         f"🛠 سطح تجهیزات: {calc['level']} | 📊 مجموع درآمد نفت: "
                         f"{fmt_money(int(r['total_income'] or 0) + amount)}")
            except Exception:
                pass
    return paid_total

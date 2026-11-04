"""نفت — دکل، استخراج خودکار در هر تیک، اکتشاف و فروش."""
from core.db import db, get_setting
from core.economy import asset_qty, get_country, get_state
from core.events import log_event
from core.utils import fmt


async def rig_count(user_id: int) -> int:
    row = await db.fetchone("SELECT id FROM buildings WHERE name='دکل نفتی'")
    return await asset_qty(user_id, "building", row["id"]) if row else 0


async def oil_menu_data(user_id: int) -> dict:
    state = await get_state(user_id)
    country = await get_country(user_id)
    per_rig = int(await get_setting("oil_rig_barrels_per_tick", "500"))
    return {
        "reserve": (country or {}).get("oil_reserve") or 0,
        "richness": (country or {}).get("oil_richness") or 0,
        "stock": state.get("oil_stock") or 0,
        "rigs": await rig_count(user_id),
        "per_rig": per_rig,
        "per_tick": await rig_count(user_id) * per_rig,
    }


async def extraction_tick(user_id: int) -> int:
    """استخراج خودکار: هر دکل در هر تیک بشکه‌ای از مخزن زیرزمینی به انبار می‌برد."""
    country = await get_country(user_id)
    if not country:
        return 0
    per_rig = int(await get_setting("oil_rig_barrels_per_tick", "500"))
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

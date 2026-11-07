"""🛒 بازار تسلیحات بین کشورها — خرید و فروش تجهیزات نظامی.

در واقعیت کشورها سلاح می‌فروشند و می‌خرنند (مثل قراردادهای صادرات تسلیحات).
این ماژول یک بازار واقعی بین بازیکن‌ها می‌سازد:

- **آگهی فروش** (`list_item`): بازیکن تعدادی از تجهیزاتش را با قیمت دلخواه
  برای فروش می‌گذارد. تجهیزات بلافاصله از انبار او خارج و در «بازار» بلوکه می‌شود.
- **خرید** (`buy`): بازیکن دیگر با پرداخت پول، تجهیزات را به انبار خودش می‌برد.
  کارمزد بازار (`arms_commission_percent`) از فروشنده کسر می‌شود.
- **لغو آگهی** (`cancel`): تجهیزات به فروشنده برمی‌گردد.
- **آگهی‌های من** و **بازار** با فیلتر دسته‌بندی.

جدول: `arms_deals` (هر ردیف یک آگهی/معامله).
"""
from __future__ import annotations

import logging

from core.db import db, get_setting
from core.utils import add_hours, fmt, fmt_money, iso

log = logging.getLogger(__name__)


async def _num(key: str, default: float) -> float:
    try:
        raw = await get_setting(key, "")
    except Exception:
        return default
    try:
        return float(str(raw).strip()) if str(raw).strip() else default
    except (TypeError, ValueError):
        return default


async def my_stock(user_id: int) -> list[dict]:
    """تجهیزات قابل فروش بازیکن."""
    return await db.fetchall(
        "SELECT e.id AS id, e.name, e.emoji, e.attack_power, e.defense_power, "
        "e.price_money, a.quantity, COALESCE(c.title, 'سایر') AS cat "
        "FROM player_assets a JOIN equipment e ON e.id=a.item_id "
        "LEFT JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND a.quantity>0 "
        "ORDER BY e.attack_power DESC", (user_id,))


async def list_item(user_id: int, equip_id: int, quantity: int,
                    unit_price: int) -> tuple[bool, str]:
    """📤 گذاشتن تجهیزات برای فروش در بازار."""
    max_q = int(await _num("arms_max_quantity", 5000))
    if quantity <= 0:
        return False, "❌ تعداد باید مثبت باشد."
    if quantity > max_q:
        return False, f"❌ حداکثر {fmt(max_q)} واحد در هر آگهی مجاز است."
    if unit_price <= 0:
        return False, "❌ قیمت هر واحد باید مثبت باشد."
    row = await db.fetchone(
        "SELECT a.quantity, e.name, e.emoji FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND a.item_id=?",
        (user_id, equip_id))
    if not row or int(row["quantity"]) < quantity:
        have = int((row or {}).get("quantity") or 0)
        return False, f"❌ موجودی کافی نیست (شما {fmt(have)} واحد دارید)."
    # تجهیزات از انبار فروشنده خارج و در بازار بلوکه می‌شود
    await db.execute(
        "UPDATE player_assets SET quantity=quantity-? "
        "WHERE user_id=? AND item_type='equipment' AND item_id=?",
        (quantity, user_id, equip_id))
    await db.execute("DELETE FROM player_assets WHERE quantity<=0")
    await db.execute(
        "INSERT INTO arms_deals(seller_id, item_type, item_id, quantity, unit_price, status) "
        "VALUES(?, 'equipment', ?, ?, ?, 'pending')",
        (user_id, equip_id, quantity, unit_price))
    total = quantity * unit_price
    return True, (f"✅ <b>آگهی ثبت شد</b>\n\n"
                  f"{row['emoji']} {row['name']} × {fmt(quantity)}\n"
                  f"💰 قیمت هر واحد: {fmt_money(unit_price)}\n"
                  f"💵 ارزش کل: <b>{fmt_money(total)}</b>\n\n"
                  "📦 تجهیزات تا زمان فروش در بازار بلوکه شده‌اند.")


async def market(category: str = "") -> list[dict]:
    """📋 همهٔ آگهی‌های فعال بازار (به‌جز آگهی‌های منفی/باطل)."""
    return await db.fetchall(
        "SELECT d.*, e.name, e.emoji, e.attack_power, e.defense_power, "
        "COALESCE(c.title, 'سایر') AS cat, "
        "COALESCE(co.flag, '') AS s_flag, COALESCE(co.name, '?') AS s_name "
        "FROM arms_deals d "
        "JOIN equipment e ON e.id=d.item_id "
        "LEFT JOIN equipment_categories c ON c.id=e.category_id "
        "LEFT JOIN users u ON u.id=d.seller_id "
        "LEFT JOIN countries co ON co.id=u.country_id "
        "WHERE d.status='pending' AND d.item_type='equipment' "
        "ORDER BY d.unit_price ASC LIMIT 40")


async def my_listings(user_id: int) -> list[dict]:
    return await db.fetchall(
        "SELECT d.*, e.name, e.emoji FROM arms_deals d "
        "JOIN equipment e ON e.id=d.item_id "
        "WHERE d.seller_id=? AND d.status='pending' ORDER BY d.id DESC", (user_id,))


async def buy(buyer_id: int, deal_id: int) -> tuple[bool, str]:
    """🛍 خرید یک آگهی تسلیحات."""
    d = await db.fetchone("SELECT * FROM arms_deals WHERE id=?", (deal_id,))
    if not d or d["status"] != "pending":
        return False, "❌ این آگهی موجود نیست."
    if int(d["seller_id"]) == int(buyer_id):
        return False, "❌ آگهی خودتان را نمی‌توانید بخرید (لغو کنید)."
    qty = int(d["quantity"] or 0)
    unit = int(d["unit_price"] or 0)
    total = qty * unit
    buyer = await db.fetchone("SELECT money FROM users WHERE id=?", (buyer_id,))
    money = int((buyer or {}).get("money") or 0)
    if money < total:
        return False, (f"❌ بودجهٔ کافی ندارید.\n💰 نیاز: {fmt_money(total)}\n"
                       f"💰 خزانه: {fmt_money(money)}")

    commission = int(total * await _num("arms_commission_percent", 5) / 100)
    seller_gets = total - commission

    await db.execute("UPDATE users SET money=money-? WHERE id=?", (total, buyer_id))
    await db.execute("UPDATE users SET money=money+? WHERE id=?",
                     (seller_gets, int(d["seller_id"])))
    await db.execute("UPDATE arms_deals SET status='sold', buyer_id=? WHERE id=?",
                     (buyer_id, deal_id))
    # انتقال تجهیزات به انبار خریدار
    exist = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type='equipment' "
        "AND item_id=?", (buyer_id, int(d["item_id"])))
    if exist:
        await db.execute(
            "UPDATE player_assets SET quantity=quantity+? WHERE user_id=? "
            "AND item_type='equipment' AND item_id=?",
            (qty, buyer_id, int(d["item_id"])))
    else:
        await db.execute(
            "INSERT INTO player_assets(user_id, item_type, item_id, quantity) "
            "VALUES(?, 'equipment', ?, ?)", (buyer_id, int(d["item_id"]), qty))

    item = await db.fetchone("SELECT name, emoji FROM equipment WHERE id=?",
                             (int(d["item_id"]),))
    label = f"{item['emoji']} {item['name']}" if item else f"#{d['item_id']}"
    # اطلاع به فروشنده
    try:
        from core.economy import announce
        await announce(
            f"🛒 <b>معاملهٔ تسلیحات</b>\n\n{label} × {fmt(qty)} فروخته شد "
            f"به قیمت {fmt_money(total)} (کارمزد بازار {fmt_money(commission)}).",
            section="trade")
    except Exception:
        pass
    return True, (f"✅ <b>خرید انجام شد</b>\n\n"
                  f"{label} × {fmt(qty)}\n"
                  f"💵 پرداختی: <b>{fmt_money(total)}</b>\n"
                  f"🏦 کارمزد بازار: {fmt_money(commission)}")


async def cancel(user_id: int, deal_id: int) -> tuple[bool, str]:
    """↩️ لغو آگهی و برگشت تجهیزات به انبار فروشنده."""
    d = await db.fetchone("SELECT * FROM arms_deals WHERE id=?", (deal_id,))
    if not d or d["status"] != "pending":
        return False, "❌ این آگهی موجود نیست."
    if int(d["seller_id"]) != int(user_id):
        return False, "❌ فقط صاحب آگهی می‌تواند آن را لغو کند."
    await db.execute("UPDATE arms_deals SET status='cancelled' WHERE id=?", (deal_id,))
    qty = int(d["quantity"] or 0)
    exist = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type='equipment' "
        "AND item_id=?", (user_id, int(d["item_id"])))
    if exist:
        await db.execute(
            "UPDATE player_assets SET quantity=quantity+? WHERE user_id=? "
            "AND item_type='equipment' AND item_id=?",
            (qty, user_id, int(d["item_id"])))
    else:
        await db.execute(
            "INSERT INTO player_assets(user_id, item_type, item_id, quantity) "
            "VALUES(?, 'equipment', ?, ?)", (user_id, int(d["item_id"]), qty))
    return True, f"↩️ آگهی لغو شد و {fmt(qty)} واحد تجهیزات به انبار شما برگشت."


async def market_text(user_id: int) -> str:
    """متن صفحهٔ بازار تسلیحات."""
    rows = await market()
    lines = ["🛒 <b>بازار تسلیحات بین‌المللی</b>\n",
             f"🏦 کارمزد بازار: <b>{fmt(await _num('arms_commission_percent', 5))}٪</b>",
             "💡 کشورها تجهیزات مازاد خود را می‌فروشند؛ شما می‌توانید بخرید.\n"]
    if not rows:
        lines.append("— بازار خالی است. اولین فروشنده باشید! —")
        return "\n".join(lines)
    for d in rows[:12]:
        total = int(d["quantity"]) * int(d["unit_price"])
        lines.append(
            f"{d['emoji']} <b>{d['name']}</b> × {fmt(d['quantity'])}\n"
            f"     💰 هر واحد {fmt_money(d['unit_price'])} — کل "
            f"<b>{fmt_money(total)}</b> | فروشنده: {d['s_flag']} {d['s_name']}")
    mine = await my_listings(user_id)
    if mine:
        lines.append(f"\n📤 آگهی‌های فعال شما: <b>{len(mine)}</b>")
    return "\n".join(lines)

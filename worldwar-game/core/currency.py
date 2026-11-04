"""مدل ارز جدید — ارز اصلی بازی نام مشخصی ندارد؛ قوی‌ترین ارز «پول اصلی» می‌شود.

امتیاز هر کشور = اقتصاد (حجم تجارت ۲۴ ساعت اخیر + خزانه) + نظامی + رضایت مردمی.
کشورهایی که ارز مشترک دارند (مثل یورو): مجموع امتیاز ÷ تعداد کشورها.
هر ۳۰ دقیقه بازمحاسبه می‌شود و اگر صدرنشین عوض شود، در کانال با عکس اعلام می‌شود.
"""
from core.db import db, get_setting, set_setting
from core.economy import army_power, get_country, get_state
from core.events import log_event
from core.images import announce_img
from core.utils import fmt, iso


async def trade_value_24h(user_id: int) -> int:
    """ارزش پولی تجارت‌های مستقیم ۲۴ ساعت اخیر کاربر (هر دو طرف) + ارزش نفت فروخته‌شده."""
    from core.utils import now, timedelta
    since = iso(now() - timedelta(hours=24))
    rows = await db.fetchall(
        "SELECT value_estimate FROM direct_trades WHERE status='accepted' AND "
        "(from_id=? OR to_id=?) AND created_at>=?",
        (user_id, user_id, since))
    oil = await db.fetchall(
        "SELECT barrels FROM oil_offers WHERE status='done' AND seller_id=? AND created_at>=?",
        (user_id, since))
    oil_price = int(await get_setting("oil_price_per_barrel", "8000"))
    oil_val = sum(r["barrels"] for r in oil) * oil_price
    return sum(r["value_estimate"] or 0 for r in rows) + oil_val


async def currency_score(user_id: int) -> int:
    """امتیاز ارز کشور: اقتصاد (۰-۳۰۰) + نظامی (۰-۳۰۰) + رضایت (۰-۱۰۰)."""
    state = await get_state(user_id)
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    atk, dfn, _ = await army_power(user_id)
    money = (user or {}).get("money", 0)
    trade = await trade_value_24h(user_id)
    economy = min(300.0, trade / 1_000_000 + money / 200_000_000)
    military = min(300.0, (atk + dfn) / 100_000)
    sat = state.get("satisfaction") or 0
    return int(round(economy + military + sat))


async def currency_groups() -> list[dict]:
    """گروه‌بندی ارزها: [{'name', 'score', 'members': [user_id], 'countries': [names]}]"""
    rows = await db.fetchall(
        "SELECT u.id, s.currency_name FROM users u JOIN states s ON s.user_id=u.id "
        "WHERE u.country_id IS NOT NULL AND u.banned=0")
    groups: dict[str, dict] = {}
    for r in rows:
        name = (r["currency_name"] or "").strip() or "بی‌نام"
        g = groups.setdefault(name, {"name": name, "scores": [], "members": []})
        score = await currency_score(r["id"])
        g["scores"].append(score)
        g["members"].append(r["id"])
    out = []
    for name, g in groups.items():
        countries = []
        for uid in g["members"]:
            c = await get_country(uid)
            if c:
                countries.append(f"{c['flag']} {c['name']}")
        out.append({
            "name": name,
            "score": int(round(sum(g["scores"]) / max(1, len(g["scores"])))),
            "members": g["members"],
            "countries": countries,
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


async def main_currency_recompute(bot=None) -> dict | None:
    """بازمحاسبه ارز اصلی؛ اگر تغییر کرد در کانال با عکس اعلام می‌کند. گروه جدید را برمی‌گرداند."""
    groups = await currency_groups()
    if not groups:
        return None
    top = groups[0]
    current = await get_setting("main_currency", "")
    if top["name"] != current:
        await set_setting("main_currency", top["name"])
        await set_setting("main_currency_owner", "، ".join(top["countries"]))
        await set_setting("main_currency_score", str(top["score"]))
        prev = current or "—"
        text = ("💵 <b>ارز اصلی بازی تغییر کرد!</b>\n\n"
                f"ارز <b>«{top['name']}»</b> با امتیاز <b>{fmt(top['score'])}</b> اکنون پول اصلی بازی است.\n"
                f"مالکان این ارز: {'، '.join(top['countries'])}\n"
                f"ارز قبلی: {prev}")
        await log_event("currency", f"ارز اصلی شد: {top['name']} ({top['score']})")
        if bot:
            await announce_img(bot, text, "currency")
        for uid in top["members"]:
            try:
                if bot:
                    await bot.send_message(
                        uid, f"🎉 ارز کشور شما «{top['name']}» حالا <b>پول اصلی بازی</b> است!")
            except Exception:
                pass
    return top


async def my_currency_info(user_id: int) -> dict:
    state = await get_state(user_id)
    groups = await currency_groups()
    my_name = (state.get("currency_name") or "").strip()
    my_group = next((g for g in groups if g["name"] == my_name), None)
    rank = next((i + 1 for i, g in enumerate(groups) if g["name"] == my_name), 0)
    return {
        "name": my_name,
        "score": my_group["score"] if my_group else 0,
        "rank": rank,
        "total": len(groups),
        "groups": groups,
        "main": await get_setting("main_currency", ""),
        "main_owner": await get_setting("main_currency_owner", ""),
    }

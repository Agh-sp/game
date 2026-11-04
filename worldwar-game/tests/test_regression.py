"""Regression tests for the earlier round of fixes (vote, attacks, negotiation, shop, receipts)."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import *  # noqa


async def run():
    from core.db import db, get_setting, set_setting
    UA, UB = 1001, 1002
    rows = await make_world([(UA, "A", 0), (UB, "B", 1)])
    dp, bot = await new_game_dp()

    print("\n== 30-minute UN war vote ==")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, f"g|wdec|{UB}"))
    await dp.feed_update(bot, cb_update(UA, f"g|wperm|{UB}"))
    await dp.feed_update(bot, msg_update(UA, "دلیل جنگ"))
    await dp.feed_update(bot, cb_update(UA, "g|wnoev"))
    war = await db.fetchone("SELECT * FROM wars ORDER BY id DESC LIMIT 1")
    vote = await db.fetchone("SELECT * FROM un_votes ORDER BY id DESC LIMIT 1")
    from core.utils import hours_left
    left = hours_left(vote["ends_at"]) * 60
    print(f"    vote ends in {left:.1f} minutes (status={war['status']})")
    check(28 <= left <= 30.5, f"vote duration ≈ 30 min ({left:.1f})")
    check(war["status"] == "voting", "war waits for the vote")
    from gamebot.handlers.war import settle_votes
    await db.execute("UPDATE un_votes SET ends_at=datetime('now','-1 minute') WHERE id=?", (vote["id"],))
    await settle_votes(bot)
    war2 = await db.fetchone("SELECT * FROM wars WHERE id=?", (war["id"],))
    check(war2["status"] == "active", f"war auto-approved after vote (status={war2['status']})")

    print("\n== missile shop & missile attack ==")
    cats = await db.fetchall("SELECT * FROM equipment_categories")
    check(any(c["key"] == "missile" for c in cats), f"missile category exists ({len(cats)} cats)")
    missiles = await db.fetchall(
        "SELECT e.* FROM equipment e JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE c.key='missile'")
    check(len(missiles) >= 5, f"{len(missiles)} missiles in shop")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, "g|eqshop"))
    await dp.feed_update(bot, cb_update(UA, "g|eqcat|6"))
    texts, _ = shot("missile shop")
    check(any("موشک" in t for t in texts), "missile shop renders")
    m = missiles[0]
    await db.execute("UPDATE users SET money=1000000000, royal_coins=5000 WHERE id=?", (UA,))
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, f"g|eqbuy|{m['id']}"))
    texts, _ = shot("buy missile (qty prompt)")
    await dp.feed_update(bot, msg_update(UA, "2"))
    texts, _ = shot("buy missile (confirm)")
    asset = await db.fetchone(
        "SELECT * FROM player_assets WHERE user_id=? AND item_type='equipment' AND item_id=?", (UA, m["id"]))
    check(asset and asset["quantity"] >= 1, f"missile bought (qty={asset['quantity'] if asset else 0})")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, f"g|wtype|{war['id']}|missile"))
    texts, _ = shot("missile picker")
    check(any("انتخاب نیروی حمله" in t for t in texts), "missile attack picker opens")
    await dp.feed_update(bot, cb_update(UA, f"g|weq|{m['id']}"))
    await dp.feed_update(bot, msg_update(UA, "2"))
    texts, _ = shot("missile forces selected")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, "g|wgo"))
    texts, _ = shot("missile attack")
    joined = "\n".join(texts)
    check("گزارش نبرد" in joined, "missile attack executed")

    print("\n== negotiation room ==")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, f"g|negr|{UB}"))
    neg = await db.fetchone("SELECT * FROM negotiations ORDER BY id DESC LIMIT 1")
    await dp.feed_update(bot, cb_update(UB, f"g|nega|{neg['id']}"))
    await dp.feed_update(bot, cb_update(UA, f"g|negroom|{neg['id']}"))
    SENT.clear()
    await dp.feed_update(bot, msg_update(UA, "سلام، پیشنهاد پیمان نظامی دارم"))
    msgs = await db.fetchall("SELECT * FROM negotiation_msgs WHERE neg_id=?", (neg["id"],))
    check(len(msgs) >= 1, f"negotiation message delivered ({len(msgs)} msgs)")

    print("\n== admin receipt approval ==")
    adp, abot = await new_admin_dp()
    await db.execute("INSERT OR IGNORE INTO admins(id,name,is_super,perms) VALUES(999,'s',1,'[]')")
    await db.execute("INSERT INTO receipts(user_id, kind, country_id, coins, toman) VALUES(?,?,?,?,?)",
                     (UA, "coins", 0, 3, 30000))
    r = await db.fetchone("SELECT * FROM receipts ORDER BY id DESC LIMIT 1")
    coins_before = (await db.fetchone("SELECT royal_coins FROM users WHERE id=?", (UA,)))["royal_coins"]
    SENT.clear()
    await adp.feed_update(abot, msg_update(999, "/start"))
    await adp.feed_update(abot, cb_update(999, "a|rcp|pending|0"))
    texts, _ = shot("pending receipts")
    check(any("فیش" in t for t in texts), "receipt list renders")
    await adp.feed_update(abot, cb_update(999, f"a|rcpo|{r['id']}"))
    texts, _ = shot("open receipt")
    await adp.feed_update(abot, cb_update(999, f"a|rcpok|{r['id']}"))
    texts, _ = shot("approve receipt")
    re_row = await db.fetchone("SELECT status FROM receipts WHERE id=?", (r["id"],))
    coins_after = (await db.fetchone("SELECT royal_coins FROM users WHERE id=?", (UA,)))["royal_coins"]
    check(re_row["status"] == "approved", f"receipt approved (status={re_row['status']})")
    check(coins_after > coins_before, f"coins added {coins_before} → {coins_after}")

    await db.close()
    print("\n=== TOTAL ERRORS:", len(ERRORS))
    for e in ERRORS:
        print("  -", e)


asyncio.run(run())

"""Tests for the new round of fixes: flags, admin images, cyber, targets, tax in millions."""
import asyncio, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import *  # noqa


async def run():
    from core.db import init_db, db, sync_country_owners, get_initial_money, get_setting, set_setting
    UA, UB, UC = 1001, 1002, 1003
    rows = await make_world([(UA, "A", 0), (UB, "B", 1), (UC, "C", 2)])
    await sync_country_owners()

    print("\n== TEST 1: sync_country_owners ==")
    chk = await db.fetchone("SELECT owner_id FROM countries WHERE id=?", (rows[0]["id"],))
    check(chk["owner_id"] == UA, f"owner_id filled from users.country_id ({chk['owner_id']})")
    # duplicate claim: UC claims the same country as UA
    await db.execute("UPDATE users SET country_id=? WHERE id=?", (rows[0]["id"], UC))
    await db.execute("UPDATE users SET country_taken_at=datetime('now','+1 hour') WHERE id=?", (UC,))
    await sync_country_owners()
    ua = await db.fetchone("SELECT country_id FROM users WHERE id=?", (UA,))
    uc = await db.fetchone("SELECT country_id FROM users WHERE id=?", (UC,))
    check(bool(uc["country_id"]) != bool(ua["country_id"]),
          f"exactly one owner kept (A={ua['country_id']}, C={uc['country_id']})")
    # admin assignment: country owned by a user that has no country_id
    await db.execute("UPDATE users SET country_id=NULL WHERE id=?", (UB,))
    await db.execute("UPDATE countries SET owner_id=? WHERE id=?", (UB, rows[1]["id"]))
    await sync_country_owners()
    ub = await db.fetchone("SELECT country_id FROM users WHERE id=?", (UB,))
    check(ub["country_id"] == rows[1]["id"], f"owner without claim gets country back ({ub['country_id']})")
    # restore a clean world: A on row0, B on row1, C without country
    await db.execute("UPDATE users SET country_id=NULL WHERE id=?", (UC,))
    await db.execute("UPDATE users SET country_id=? WHERE id=?", (rows[0]["id"], UA))
    await db.execute("UPDATE users SET country_id=? WHERE id=?", (rows[1]["id"], UB))
    await sync_country_owners()

    print("\n== TEST 2: initial money = 200 million ==")
    await set_setting("initial_money", "200000000")
    check(await get_initial_money() == 200_000_000, f"get_initial_money = {await get_initial_money()}")
    dp, bot = await new_game_dp()
    SENT.clear()
    await dp.feed_update(bot, msg_update(5555, "/start"))
    u = await db.fetchone("SELECT money FROM users WHERE id=5555")
    check(u and u["money"] == 200_000_000, f"new player money = {u['money'] if u else None}")
    # migration of old value
    await set_setting("initial_money", "200")
    await init_db()
    check(await get_initial_money() == 200_000_000,
          f"old value 200 auto-migrated to {await get_initial_money()}")

    print("\n== TEST 3: flag survives seed ==")
    await db.execute("UPDATE countries SET flag_url='AgACAgQAAx-TESTFLAG' WHERE id=?", (rows[0]["id"],))
    from core import seed as seed_mod
    await seed_mod.run(db)
    c = await db.fetchone("SELECT flag_url FROM countries WHERE id=?", (rows[0]["id"],))
    check(c["flag_url"] == "AgACAgQAAx-TESTFLAG", f"custom flag kept after seed ({c['flag_url']})")

    print("\n== TEST 4: admin image attached to announcement ==")
    with open("/home/user/game/worldwar-game/core/images.py") as f:
        src = f.read()
    check('"war_declare"' in src and '"war_attack"' in src and '"cyber"' in src and '"un"' in src,
          "new image sections registered")
    await db.execute("INSERT OR REPLACE INTO images(name, section, file_id) VALUES('unv','un','PHOTO_UN')")
    await db.execute("INSERT OR REPLACE INTO images(name, section, file_id) VALUES('gen','general','PHOTO_GEN')")
    from core.economy import announce
    SENT.clear()
    await set_setting("announcement_channel", "@testchannel")
    await announce(bot, "پیام سازمان ملل", section="un")
    shot("announce(un)")
    ph = [p for (_n, _c, _t, p) in SENT if p]
    check(ph and ph[0] == "PHOTO_UN", f"section image used ({ph[:1]})")
    SENT.clear()
    await announce(bot, "پیام بی‌بخش")
    ph = [p for (_n, _c, _t, p) in SENT if p]
    check(ph and ph[0] == "PHOTO_GEN", f"general fallback image used ({ph[:1]})")

    print("\n== TEST 5: enemy lists include countries with NULL owner_id ==")
    await db.execute("UPDATE countries SET owner_id=NULL WHERE id=?", (rows[1]["id"],))
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, "g|wdec"))
    texts, _ = shot("g|wdec")
    joined = "\n".join(texts)
    from gamebot.handlers.war import enemy_countries
    enemies = await enemy_countries(UA)
    check(any(e["owner_uid"] == UB for e in enemies), f"enemy_countries contains B ({[(e['name'], e['owner_uid']) for e in enemies]})")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, "g|wcyb"))
    texts, _ = shot("g|wcyb")
    check(len(texts) > 0, "cyber list rendered")

    print("\n== TEST 6: cyber chance & operation ==")
    from gamebot.handlers.war import cyber_chance
    check(abs(cyber_chance(10000, 10000) - 50) < 0.01, f"equal power chance = {cyber_chance(10000, 10000)}")
    check(abs(cyber_chance(20000, 10000) - 95) < 0.01, f"double power chance = {cyber_chance(20000, 10000)}")
    check(abs(cyber_chance(5000, 10000) - 25) < 0.01, f"half power chance = {cyber_chance(5000, 10000)}")
    random.seed(1)
    real_random = random.random
    random.random = lambda: 0.0  # force success
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, f"g|cy|assass|{UB}"))
    random.random = real_random
    texts, _ = shot("g|cy|assass")
    st = await db.fetchone("SELECT leader_block_until FROM states WHERE user_id=?", (UB,))
    check(st and st["leader_block_until"], f"leader blocked until {st['leader_block_until'] if st else None}")

    print("\n== TEST 7: tax scales with population & satisfaction, shown in millions ==")
    from core.economy import income_breakdown
    await db.execute("UPDATE countries SET population=100000000 WHERE id=?", (rows[0]["id"],))
    await db.execute("UPDATE states SET satisfaction=80, tax_rate=0.20 WHERE user_id=?", (UA,))
    i1 = await income_breakdown(UA)
    await db.execute("UPDATE states SET satisfaction=95 WHERE user_id=?", (UA,))
    i2 = await income_breakdown(UA)
    await db.execute("UPDATE states SET tax_rate=0.40 WHERE user_id=?", (UA,))
    i3 = await income_breakdown(UA)
    await db.execute("UPDATE countries SET population=200000000 WHERE id=?", (rows[0]["id"],))
    i4 = await income_breakdown(UA)
    print(f"    sat80/daily={i1['daily']:,}  sat95={i2['daily']:,}  tax40={i3['daily']:,}  pop200M={i4['daily']:,}")
    check(i2["daily"] > i1["daily"], "more satisfaction → more income")
    check(i3["daily"] > i2["daily"], "higher tax → more income")
    check(i4["daily"] > i3["daily"], "bigger population → more income")
    from core.utils import fmt_money
    check(fmt_money(i4["daily"]).endswith("میلیون"), f"fmt_money → {fmt_money(i4['daily'])}")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, "g|inc"))
    texts, _ = shot("g|inc")
    check("میلیون" in "\n".join(texts), "income screen shows millions")
    await dp.feed_update(bot, cb_update(UA, "g|tax"))
    texts, _ = shot("g|tax")
    check("میلیون" in "\n".join(texts), "tax screen shows millions")
    await dp.feed_update(bot, msg_update(UA, "25"))
    texts, _ = shot("tax input 25")
    check(any("میلیون" in t for t in texts), "tax confirmation shows millions")
    await db.execute("UPDATE states SET satisfaction=80 WHERE user_id=?", (UA,))

    print("\n== TEST 8: choose admin flag changes the flag for real ==")
    await db.execute("INSERT OR REPLACE INTO images(name, section, file_id) VALUES('پرچم تست','flag','PHOTO_FLAG')")
    img = await db.fetchone("SELECT * FROM images WHERE name='پرچم تست'")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, f"g|flag_set|{img['id']}"))
    texts, photos = shot("g|flag_set")
    c = await db.fetchone("SELECT flag_url FROM countries WHERE id=?", (rows[0]["id"],))
    check(c["flag_url"] == "PHOTO_FLAG", f"country flag_url = {c['flag_url']}")
    check("PHOTO_FLAG" in [p for (_n, _x, _t, p) in SENT], "new flag photo sent to player")
    await dp.feed_update(bot, cb_update(UA, "g|myflag"))
    texts, photos = shot("g|myflag")
    check(any(p == "PHOTO_FLAG" for (_n, _x, _t, p) in SENT), "my flag screen shows chosen flag")
    from core.images import get_country_flag_photo
    country = await db.fetchone("SELECT * FROM countries WHERE id=?", (rows[0]["id"],))
    check(await get_country_flag_photo(country) == "PHOTO_FLAG", "flag photo resolver uses chosen flag")

    print("\n== TEST 9: declare war on Japan-like target and attack ==")
    # give B some defence and A soldiers
    await db.execute("INSERT OR REPLACE INTO player_assets(user_id, item_type, item_id, quantity) "
                     "VALUES(?, 'soldier', 1, 5000)", (UA,))
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, f"g|wnoperm|{UB}"))
    await dp.feed_update(bot, cb_update(UA, f"g|wnpgo|{UB}"))
    shot("declare war")
    war = await db.fetchone("SELECT * FROM wars ORDER BY id DESC LIMIT 1")
    check(war and war["defender_id"] == UB and war["status"] == "active",
          f"war created: {dict(war) if war else None}")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UB, f"g|wnoperm|{UA}"))
    await dp.feed_update(bot, cb_update(UB, f"g|wnpgo|{UA}"))
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, "g|watk"))
    texts, _ = shot("attack list")
    check("گزارش" not in "\n".join(texts), "attack list rendered")
    await dp.feed_update(bot, cb_update(UA, f"g|watkc|{war['id']}"))
    texts, _ = shot("attack types")
    joined = "\n".join(texts)
    check("زمینی" in joined, "attack types list shows land option")
    await dp.feed_update(bot, cb_update(UA, f"g|wtype|{war['id']}|land"))
    texts, _ = shot("pick force")
    check(any("انتخاب نیروی حمله" in t for t in texts), "force picker rendered")
    money_before = (await db.fetchone("SELECT money FROM users WHERE id=?", (UB,)))["money"]
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, "g|wgo"))
    texts, _ = shot("confirm land attack")
    check(any("تأیید حمله" in t for t in texts), "attack confirmation rendered")
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, "g|wgogo"))
    texts, _ = shot("execute land attack")
    joined = "\n".join(texts)
    check("گزارش نبرد" in joined, "battle report produced")
    battle = await db.fetchone("SELECT * FROM battles ORDER BY id DESC LIMIT 1")
    check(battle is not None, f"battle row stored: {dict(battle) if battle else None}")
    money_after = (await db.fetchone("SELECT money FROM users WHERE id=?", (UB,)))["money"]
    print(f"    defender money {money_before:,} → {money_after:,}")
    # سایبری هم بعد از نبرد قابل اجرا باشد
    SENT.clear()
    await dp.feed_update(bot, cb_update(UA, f"g|wcyb|{UB}"))
    texts, _ = shot("cyber target menu")
    check(any("عملیات سایبری" in t for t in texts), "cyber ops menu rendered")

    print("\n== TEST 10: admin settings show the keys ==")
    adp, abot = await new_admin_dp()
    await db.execute("INSERT OR IGNORE INTO admins(id,name,is_super,perms) VALUES(999,'s',1,'[]')")
    SENT.clear()
    await adp.feed_update(abot, msg_update(999, "/start"))
    await adp.feed_update(abot, cb_update(999, "a|set"))
    texts, _ = shot("admin settings")
    joined = "\n".join(texts)
    check("بودجه اولیه" in joined, "initial_money listed")
    check("مجوز جنگ" in joined, "war_vote_minutes listed")

    await db.close()
    print("\n=== TOTAL ERRORS:", len(ERRORS))
    for e in ERRORS:
        print("  -", e)


asyncio.run(run())

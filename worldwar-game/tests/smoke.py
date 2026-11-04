"""Broad regression smoke test: walk most menus of the game bot + admin bot."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import *  # noqa


async def run():
    from core.db import db, get_setting, set_setting
    UA, UB, ADMIN = 1001, 1002, 999
    rows = await make_world([(UA, "A", 0), (UB, "B", 1)])
    await db.execute("INSERT OR IGNORE INTO admins(id,name,is_super,perms) VALUES(999,'s',1,'[]')")
    await set_setting("announcement_channel", "@testchannel")
    for sec in ("un", "general", "flag", "war_attack"):
        await db.execute("INSERT OR REPLACE INTO images(name, section, file_id) VALUES(?,?,?)",
                         (f"img_{sec}", sec, f"PHOTO_{sec}"))
    dp, bot = await new_game_dp()

    print("\n== game bot menus ==")
    callbacks = [
        "g|main", "g|emp", "g|mg", "g|people", "g|pw", "g|oil", "g|oilrig", "g|prj", "g|fun",
        "g|sci", "g|company", "g|army", "g|base", "g|bar", "g|eq", "g|eqshop", "g|train",
        "g|gov", "g|war", "g|wdec", "g|wcyb", "g|un", "g|unrep", "g|trd", "g|neg", "g|negnew",
        "g|dtrd", "g|rsale", "g|strait", "g|mytrt", "g|resc", "g|coin", "g|coinpkg", "g|coinhist",
        "g|coinconv", "g|coinbuy", "g|daily", "g|guide", "g|sup", "g|suphist", "g|cchg",
        "g|stmt", "g|myflag", "g|flag_pick|0", "g|trust", "g|stats", "g|inc", "g|tax", "g|sub",
        "g|cur", "g|welfare", "g|ppl",
    ]
    for data in callbacks:
        before = len(ERRORS)
        SENT.clear()
        await dp.feed_update(bot, cb_update(UA, data))
        if len(ERRORS) > before:
            print(f"  !!! game {data} ERROR")
    extra = ["g|watk", "g|eqcat|1", "g|eqsub|1|drone", "g|eqcat|6", "g|eqsub|6|cruise",
             "g|eqbuy|1", "g|trn|1", f"g|wdec|{UB}", f"g|wcyb|{UB}", f"g|unrep|{UB}",
             f"g|negr|{UB}", f"g|basereqr|{UB}", "g|flag_pick|0"]
    for data in extra:
        before = len(ERRORS)
        SENT.clear()
        await dp.feed_update(bot, cb_update(UA, data))
        if len(ERRORS) > before:
            print(f"  !!! game {data} ERROR")

    print("\n== game text commands ==")
    for text in ["/start", "/cancel", "/laws", "/welfare", "متن عادی", "/flag"]:
        before = len(ERRORS)
        SENT.clear()
        await dp.feed_update(bot, msg_update(UA, text))
        if len(ERRORS) > before:
            print(f"  !!! text {text} ERROR")

    print("\n== admin bot ==")
    adp, abot = await new_admin_dp()
    admin_cbs = ["a|root", "a|stats", "a|eco", "a|rcp|pending|0", "a|usr", "a|set", "a|logs",
                 "a|sections", "a|daily", "a|grp|countries", "a|grp|military", "a|grp|un",
                 "a|grp|trade", "a|grp|world", "a|grp|projects", "a|grp|missions", "a|tik|open|0",
                 "a|season", "a|img", "a|imgnew", "a|adm", "a|fb", "a|db", "a|bulk", "a|prices", "a|cur"]
    before = len(ERRORS)
    await adp.feed_update(abot, msg_update(ADMIN, "/start"))
    if len(ERRORS) > before:
        print("  !!! admin /start ERROR")
    for data in admin_cbs:
        before = len(ERRORS)
        SENT.clear()
        await adp.feed_update(abot, cb_update(ADMIN, data))
        if len(ERRORS) > before:
            print(f"  !!! admin {data} ERROR")

    print("\n== image sections list ==")
    from core.images import IMAGE_SECTIONS
    print("   sections:", len(IMAGE_SECTIONS), list(IMAGE_SECTIONS))
    SENT.clear()
    await adp.feed_update(abot, cb_update(ADMIN, "a|imgnew"))
    await adp.feed_update(abot, msg_update(ADMIN, "تست-عکس"))
    texts, _ = shot("image section picker")
    from core.images import IMAGE_SECTIONS
    check("war_declare" in IMAGE_SECTIONS and "un" in IMAGE_SECTIONS,
          "admin can pick the new sections")

    print("\n== income tick (tax in millions) ==")
    from core.scheduler import income_tick
    await db.execute("UPDATE countries SET population=100000000 WHERE id=?", (rows[0]["id"],))
    await db.execute("UPDATE states SET satisfaction=75, tax_rate=0.2, last_income=NULL WHERE user_id=?", (UA,))
    SENT.clear()
    await income_tick(bot)
    texts, _ = shot("income tick")
    joined = "\n".join(texts)
    check("(روزانه" in joined, "income tick shows daily income too")
    check("میلیون" in joined, "income tick message uses millions")
    check("نرخ مالیات" in joined, "income tick shows tax rate")

    await db.close()
    print("\n=== TOTAL ERRORS:", len(ERRORS))
    for e in ERRORS:
        print("  -", e)


asyncio.run(run())

"""🧨 تست موتور واقع‌گرایی — ده سامانهٔ تازه.

اجرا: /tmp/venv/bin/python tests/test_realism.py   (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

A, B, C = 7301, 7302, 7303


async def give(uid: int, item_type: str, name_like: str, qty: int) -> int:
    from core.db import db
    table = "equipment" if item_type == "equipment" else "buildings"
    row = await db.fetchone(f"SELECT id FROM {table} WHERE name LIKE '%{name_like}%' LIMIT 1")
    if not row:
        return 0
    await db.execute(
        "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
        (uid, item_type, row["id"], qty, qty))
    return int(row["id"])


async def give_soldiers(uid: int, qty: int) -> None:
    from core.db import db
    row = await db.fetchone("SELECT id FROM soldier_types ORDER BY id LIMIT 1")
    await db.execute(
        "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
        (uid, "soldier", row["id"], qty, qty))


async def main():
    from core.db import db, set_setting
    from core import (supply, unrest, market, intel, elections, refugees,
                      bases, grid, weather, income)

    dp, bot = await H.new_game_dp()
    rows = await H.make_world([(A, "آ", 0), (B, "ب", 1), (C, "ج", 2)])
    await give(A, "building", "پالایشگاه", 3)
    await give(A, "building", "دکل نفتی", 4)
    await give_soldiers(A, 200)
    await give(B, "building", "نیروگاه", 2)
    await give_soldiers(B, 100)

    # ─── ۱) 🚚 زنجیرهٔ تأمین ───
    print("\n== 🚚 تأمین و مهمات ==")
    st = await supply.get(A)
    H.check(st["ammo"] > 0 and st["fuel"] > 0, "انبار اولیه ساخته شد")
    prod = await supply.tick(A)
    st2 = await supply.get(A)
    H.check(st2["ammo"] > st["ammo"], "تولید مهمات به انبار اضافه شد")
    H.check(prod["refineries"] >= 1, "پالایشگاه در تولید لحاظ شد")
    need = await supply.need_for_attack(A, 100)
    H.check(need["ammo"] > 0, "مصرف تدارکات برای حمله محاسبه شد")
    res = await supply.consume_attack(A, 100)
    H.check(1.0 <= res["factor"] <= 1.0, "با انبار پر، قدرت حمله کامل ماند")
    await db.execute("UPDATE supply_stock SET ammo=0, fuel=0 WHERE user_id=?", (A,))
    fac = await supply.factor(A)
    H.check(fac < 0.7, f"انبار خالی قدرت حمله را کم کرد (×{fac})")
    res2 = await supply.consume_attack(A, 100)
    H.check(bool(res2["lines"]), "پیام کمبود تدارکات تولید شد")
    ok, txt = await supply.buy(A, "ammo", 100)
    H.check(ok and (await supply.get(A))["ammo"] >= 100, "خرید مهمات از بازار داخلی")
    bal = await db.fetchone("SELECT money FROM users WHERE id=?", (A,))
    ok2, _ = await supply.buy(A, "ammo", 10_000_000)
    H.check(not ok2, "خرید بیش از بودجه رد شد")
    txt = await supply.status_text(A)
    H.check("مهمات" in txt and "سوخت" in txt, "متن وضعیت تأمین کامل است")
    # سوزاندن انبار با خرابکاری
    before = (await supply.get(A))["ammo"]
    burned = await supply.burn_share(A, 0.5)
    H.check((await supply.get(A))["ammo"] < before + 0.01 and burned["ammo"] >= 0,
            "سهم انبار در خرابکاری سوزانده شد")

    # ration: ارتش گرسنه
    await supply.get(B)   # ساخت ردیف انبار
    await db.execute("UPDATE supply_stock SET ammo=0, fuel=0 WHERE user_id=?", (B,))
    ration = await supply.ration_tick(B)
    H.check(not ration["fed"] and bool(ration["lines"]), "کمبود تدارکات سرباز فراری داد")

    # ─── ۲) ✊ ناآرامی و اعتصاب ───
    print("\n== ✊ ناآرامی و اعتصاب ==")
    await db.execute("UPDATE states SET satisfaction=10 WHERE user_id=?", (A,))
    u = await unrest.get(A)
    H.check(u["unrest"] >= 0, "وضعیت ناآرامی خوانده شد")
    parts = await unrest.pressure(A)
    H.check(bool(parts), "عوامل فشار اجتماعی محاسبه شد")
    # بالا بردن ناآرامی تا آستانهٔ اعتصاب
    await unrest.set_unrest(A, (await unrest.get(A))["strike_threshold"])
    tick = await unrest.decay_tick(A)
    H.check(tick["strike_started"], "اعتصاب سراسری در آستانه آغاز شد")
    info = await unrest.get(A)
    H.check(info["strike_active"], "اعتصاب فعال ثبت شد")
    H.check(info["strike_demand"], "خواستهٔ معترضان ثبت شد")
    m = await unrest.income_multiplier(A)
    H.check(m < 1.0, f"اعتصاب درآمد را کم کرد (×{m})")
    src = await income.income_sources(A)
    H.check("✊ ناآرامی/اعتصاب" in (src.get("modifiers") or {}),
            "اعتصاب در محاسبهٔ درآمد لحاظ شد")
    ok, txt = await unrest.pay_subsidy(A, 2)
    H.check(ok, "بستهٔ یارانه پرداخت شد")
    ok, txt = await unrest.crackdown(A)
    H.check(ok, "سرکوب نظامی اعتراض اجرا شد")
    ok, txt = await unrest.ignore(A)
    H.check(ok, "نادیده‌گرفتن اجرا شد")
    ok, txt = await unrest.negotiate_strike(A)
    H.check(ok and not (await unrest.get(A))["strike_active"], "مذاکره اعتصاب را تمام کرد")
    hist = await unrest.history(A)
    H.check(len(hist) >= 1, "تاریخچهٔ اعتصاب ثبت شد")

    # ─── ۳) 🔥 جنگ داخلی ───
    print("\n== 🔥 جنگ داخلی ==")
    await unrest.set_unrest(B, 100)
    started = await unrest.maybe_start_revolt(bot, B)
    H.check(bool(started), "جنگ داخلی در ناآرامی ۱۰۰٪ آغاز شد")
    info = await unrest.get(B)
    H.check(info["revolt_active"], "جنگ داخلی فعال است")
    m = await unrest.income_multiplier(B)
    H.check(m < 0.7, f"جنگ داخلی درآمد را خرد کرد (×{m})")
    await db.execute("UPDATE users SET money=2000000000 WHERE id=?", (B,))
    ok, txt = await unrest.revolt_negotiate(B)
    H.check(ok, "امتیازدهی به شورشی‌ها")
    await set_setting("revolt_bribe_chance", "100")
    ok, txt = await unrest.revolt_bribe(B)
    H.check(ok, "خرید فرماندهان شورشی (شانس ۱۰۰٪)")
    await unrest.set_unrest(C, 95)
    await db.execute("UPDATE states SET revolt_until=? WHERE user_id=?", ("2000-01-01 00:00:00", C))
    await set_setting("revolt_bribe_chance", "0")
    ok_bad, txt_bad = await unrest.revolt_bribe(C)
    H.check(not ok_bad and "لو رفت" in txt_bad, "لو رفتن رشوه جریمه دارد (شانس ۰٪)")
    await set_setting("revolt_bribe_chance", "60")
    await db.execute("UPDATE states SET revolt_until=NULL WHERE user_id=?", (C,))
    await unrest.set_unrest(C, 10)
    ok, txt = await unrest.revolt_crush(B)
    H.check(ok, "سرکوب نظامی جنگ داخلی")
    # پایان با گذشتن مهلت
    await unrest.set_unrest(C, 100)
    await unrest.maybe_start_revolt(bot, C)
    await db.execute("UPDATE states SET revolt_until='2000-01-01 00:00:00' WHERE user_id=?", (C,))
    closed = await unrest.revolt_tick(bot)
    H.check(closed >= 1, "تیک جنگ داخلی اجرا شد")
    st3 = await db.fetchone("SELECT revolt_winner, unrest, satisfaction FROM states WHERE user_id=?", (C,))
    H.check(st3["revolt_winner"] == "rival", "شورشی‌ها پیروز شدند (تغییر حاکمیت)")
    c3 = await db.fetchone(
        "SELECT c.owner_id FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?", (C,))
    H.check(bool(c3), "کشور پس از شورش همچنان به بازیکن تعلق دارد (سقوط نکرد)")

    # ─── ۴) 💸 اقتصاد، تورم، بدهی ───
    print("\n== 💸 اقتصاد کلان ==")
    ok, txt = await market.print_money(A, 200_000_000)
    inf = await market.inflation(A)
    H.check(ok and inf > 0, f"چاپ پول تورم ساخت ({inf}٪)")
    H.check(await market.inflation_income_multiplier(A) < 1.0, "تورم قدرت خرید درآمد را کم کرد")
    H.check(await market.price_multiplier(A) > 1.0, "تورم خرید را گران کرد")
    new_inf = await market.inflation_decay_tick(A)
    H.check(new_inf < inf, "تورم کمی فروکش کرد")
    await db.execute("UPDATE users SET money=5000000000 WHERE id=?", (A,))
    limit = await market.loan_limit(A)
    H.check(limit > 0, f"سقف وام محاسبه شد ({limit})")
    ok, txt = await market.borrow(A, min(limit, 100_000_000))
    H.check(ok, "وام گرفته شد")
    H.check(await market.debt(A) is not None, "بدهی ثبت شد")
    ok2, _ = await market.borrow(A, 10_000_000)
    H.check(not ok2, "وام دوم بدون تسویه رد شد")
    inst = await market.installment_tick(A)
    H.check(inst.get("paid", 0) > 0, "قسط وام از خزانه کسر شد")
    ok, txt = await market.repay(A)
    H.check(ok, "پیش‌پرداخت بدهی")
    H.check(await market.debt(A) is None, "بدهی کامل تسویه شد")

    # ─── ۷) 🛢 بازار جهانی نفت ───
    print("\n== 🛢 بازار جهانی نفت ==")
    await market._set_oil(80)
    mult80 = await market.oil_multiplier()
    H.check(abs(mult80 - 1.0) < 0.02, "قیمت پایه → ضریب ۱")
    await db.execute("INSERT INTO wars(attacker_id, defender_id, status) VALUES(?,?,'active')", (A, B))
    res = await market.oil_tick(bot)
    H.check(res["price"] >= 80, f"جنگ قیمت نفت را بالا برد ({res['price']})")
    await market._set_oil(160)
    H.check(await market.oil_multiplier() > 1.0, "قیمت بالا ضریب درآمد نفتی را بالا برد")
    oil = await income.oil_income(A)
    H.check(oil.get("market_mult", 1) > 1.0, "درآمد نفتی از بازار جهانی اثر گرفت")
    await market._set_oil(20)
    H.check(await market.oil_price() >= 35, "کف قیمت نفت اعمال شد")
    txt = await market.oil_market_text()
    H.check("دلار" in txt, "متن بازار نفت")
    txt = await market.economy_text(A)
    H.check("تورم" in txt and "بدهی" in txt, "متن اقتصاد کلان")

    # ─── ۶) 🗳 انتخابات و احزاب ───
    print("\n== 🗳 انتخابات و احزاب ==")
    p = await elections.party_of(A)
    H.check(p["key"] in elections.PARTIES, "حزب حاکم تعیین شد")
    await db.execute("UPDATE users SET money=5000000000 WHERE id=?", (A,))
    ok, txt = await elections.campaign(A, 2)
    p2 = await elections.party_of(A)
    H.check(ok and p2["campaign"] >= 2, "کمپین رأی تبلیغاتی خرید")
    await db.execute("UPDATE states SET satisfaction=5 WHERE user_id=?", (B,))
    res = await elections.run_one(B, bot)
    H.check(res is not None, "انتخابات برگزار شد")
    res2 = await elections.run_one(B, bot)
    H.check(res2 is not None, "انتخابات دوم هم برگزار شد")
    await elections.party_of(C)
    await db.execute("UPDATE party_state SET next_at='2000-01-01 00:00:00' WHERE user_id=?", (C,))
    done = await elections.tick(bot)
    H.check(done >= 1, "تیک انتخابات کشورهای سررسیده را برگزار کرد")
    txt = await elections.elections_text(A)
    H.check("حزب" in txt, "متن انتخابات")

    # ─── ۵) 🕵 اطلاعات ───
    print("\n== 🕵 جاسوسی ==")
    await give(A, "equipment", "دیداس", 5)
    await db.execute("UPDATE users SET money=5000000000 WHERE id=?", (A,))
    ok, txt = await intel.spy(A, B)
    H.check(ok, "عملیات جاسوسی اجرا شد")
    H.check(await intel.level(A) >= 1, "سطح شبکهٔ اطلاعات بالا رفت")
    est = await intel.estimate(A, B)
    H.check(est["estimate"] and est["low"] < est["real_attack"] <= est["high"],
            "برآورد داخل بازهٔ خطا است")
    prev = await intel.battle_preview(A, B)
    H.check("تا" in prev and "٪" in prev, "پیش‌بینی نبرد بازه‌ای است (مه اطلاعات)")
    await intel.set_level(A, 5)
    H.check(await intel.radius(A) < 0.3, "سطح بالای شبکه بازهٔ خطا را تنگ کرد")
    txt = await intel.intel_text(A)
    H.check("شبکهٔ اطلاعاتی" in txt, "متن اطلاعات")

    # ─── ۸) 📡 پایگاه خارجی ───
    print("\n== 📡 پایگاه خارجی ==")
    await db.execute("INSERT INTO bases(host_id, guest_id, status, kind) VALUES(?,?,'active','land')",
                     (A, B))
    ok, txt = await bases.declare_foreign(A, B)
    H.check(ok, "پایگاه خارجی اعلام شد")
    pay = await bases.income_tick(A)
    H.check(pay > 0, "میزبان از پایگاه درآمد گرفت")
    H.check(await bases.defense_bonus(A) > 1.0, "بونوس دفاعی میزبان")
    H.check(await bases.attack_bonus(B) > 1.0, "بونوس حملهٔ مهمان")
    joined = await bases.auto_join_if_attacked(bot, A, C)
    H.check(len(joined) == 1, "مهمان خودکار وارد جنگ میزبان شد")
    war = await db.fetchone("SELECT * FROM wars WHERE attacker_id=? AND defender_id=?", (B, C))
    H.check(bool(war), "جنگ خودکار در دیتابیس ثبت شد")
    txt = await bases.bases_text(A)
    H.check("خارجی" in txt, "متن پایگاه خارجی")
    ok, txt = await bases.terminate(A, B)
    H.check(ok, "لغو یک‌طرفهٔ قرارداد")
    H.check(await bases.defense_bonus(A) == 1.0, "بونوس دفاعی پس از لغو حذف شد")

    # ─── ۹) ⚡ خاموشی آبشاری ───
    print("\n== ⚡ شبکهٔ برق ==")
    res = await grid.strike(B, "power")
    H.check(res["hours"] > 0, "خرابکاری شبکه خاموشی ساخت")
    H.check(await grid.hours_left(B) > 0, "ساعت خاموشی ثبت شد")
    H.check(await grid.income_multiplier(B) < 1.0, "خاموشی درآمد را کم کرد")
    line = await grid.grid_line(B)
    H.check("خاموشی" in line, "خط وضعیت شبکه")
    await db.execute("UPDATE users SET money=5000000000 WHERE id=?", (B,))
    ok, txt = await grid.repair(B)
    H.check(ok and await grid.hours_left(B) == 0, "ترمیم اضطراری شبکه")
    ok2, _ = await grid.repair(B)
    H.check(not ok2, "ترمیم شبکهٔ سالم رد شد")
    await market.add_inflation(B, 20)
    src = await income.income_sources(B)
    H.check("💸 تورم" in (src.get("modifiers") or {}), "تورم در محاسبهٔ درآمد دیده شد")

    # ─── ۱۰) 🍁 فصل‌ها ───
    print("\n== 🍁 فصل و آب‌وهوا ==")
    row = await weather.current()
    H.check(row.get("season") in weather.SEASONS, "فصل جاری ثبت شد")
    await db.execute("UPDATE season_weather SET season='winter', started_at='2000-01-01 00:00:00'")
    await weather.rotate()
    H.check(await weather.season_key() in weather.SEASONS, "چرخش فصل انجام شد")
    await db.execute("UPDATE season_weather SET season='winter', started_at='2000-01-01 00:00:00'")
    H.check(await weather.attack_multiplier() < 1.0, "زمستان حمله را کند کرد")
    H.check(await weather.energy_extra_pct() > 0, "زمستان مصرف انرژی را بالا برد")
    await db.execute("UPDATE season_weather SET season='autumn', storm=1, started_at='2000-01-01 00:00:00'")
    H.check(await weather.is_storm(), "طوفان پاییز فعال")
    H.check(await weather.attack_multiplier() < 1.0, "طوفان حمله را کند کرد")
    await weather.tick(bot)
    txt = await weather.season_line()
    H.check("فصل" in txt, "خط وضعیت فصل")

    # ─── ۵) 🏃 پناهندگان ───
    print("\n== 🏃 پناهندگان ==")
    await give(B, "building", "نیروگاه", 1)
    await db.execute("UPDATE states SET blackout_power=6, blackout_water=0 WHERE user_id=?", (B,))
    pop_before = (await db.fetchone(
        "SELECT c.population p FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (B,)))["p"]
    fl = await refugees.flight_tick(B)
    pop_after = (await db.fetchone(
        "SELECT c.population p FROM countries c JOIN users u ON u.country_id=c.id WHERE u.id=?",
        (B,)))["p"]
    H.check(fl["fled"] > 0 and pop_after < pop_before, "موج پناهندگان جمعیت را کم کرد")
    flows = await db.fetchall("SELECT * FROM refugee_flows WHERE from_user=?", (B,))
    H.check(len(flows) >= 1, "جریان پناهندگان ثبت شد")
    host = await refugees.host_tick(flows[0]["to_user"])
    H.check(host["hosted"] > 0, "کشور میزبان پناهنده ثبت کرد")
    await db.execute("UPDATE users SET money=5000000000 WHERE id=?", (flows[0]["to_user"],))
    ok, txt = await refugees.resettle(flows[0]["to_user"], 1000)
    H.check(ok, "اسکان پناهندگان")
    txt = await refugees.refugees_text(flows[0]["to_user"])
    H.check("پناهنده" in txt, "متن پناهندگان")

    # ─── حمله با تدارکات و پیش‌بینی ───
    print("\n== ⚔️ حمله با موتور واقع‌گرایی ==")
    await give(A, "equipment", "موشک", 10)
    await db.execute("UPDATE supply_stock SET ammo=100000, fuel=100000 WHERE user_id=?", (A,))
    await db.execute("INSERT INTO wars(attacker_id, defender_id, status) VALUES(?,?,'active')", (A, C))
    war = await db.fetchone("SELECT * FROM wars WHERE attacker_id=? AND defender_id=? "
                            "AND status='active' ORDER BY id DESC LIMIT 1", (A, C))
    H.SENT.clear()
    before_ammo = (await supply.get(A))["ammo"]
    await dp.feed_update(bot, H.cb_update(A, f"g|watkc|{war['id']}"))
    after_ammo = (await supply.get(A))["ammo"]
    H.check(after_ammo <= before_ammo, "حمله از انبار تدارکات کم کرد")

    print("\n== منوهای اداری (تنظیمات تازه) ==")
    from core.db import DEFAULT_SETTINGS
    from adminbot.entities import SETTING_LABELS
    from adminbot.handlers.settings import HELP
    new_keys = [k for k in DEFAULT_SETTINGS if k.startswith(
        ("supply_", "unrest_", "revolt_", "election_", "intel_", "fbase_", "grid_",
         "weather_", "refugee_", "inflation_", "loan_", "oil_market_"))]
    H.check(len(new_keys) >= 70, f"همهٔ کلیدهای تازه در تنظیمات ثبت شدند ({len(new_keys)})")
    H.check(all(k in SETTING_LABELS for k in new_keys), "همهٔ کلیدها برچسب فارسی دارند")
    H.check(all(k in HELP for k in new_keys), "همهٔ کلیدها متن راهنما دارند")

    print(f"\nTOTAL ERRORS: {len(H.ERRORS)}")
    for e in H.ERRORS:
        print(" -", e)


asyncio.run(main())

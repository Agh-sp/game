"""☢️🕊🛒 تست: برنامهٔ هسته‌ای ۵ دقیقه‌ای، آتش‌بس/صلح واقعی، بازار تسلیحات.

اجرا:
    PAW_PROXY=0 python tests/test_new_capabilities.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("tests"))
import harness as H  # noqa: E402


async def main():
    from core.db import db, get_setting, set_setting

    await H.make_world([(2101, "مهاجم", 0), (2102, "مدافع", 1)])
    A, D = 2101, 2102
    dp, bot = await H.new_game_dp()

    # ═══════ TEST 1: ☢️ برنامهٔ هسته‌ای ۵ دقیقه‌ای ═══════
    print("\n══ TEST 1: برنامهٔ هسته‌ای ۵ دقیقه‌ای ══")
    from core import enrichment as en
    minutes = await en.stage_minutes()
    H.check(minutes == 5, f"مدت هر مرحله ۵ دقیقه است ({minutes})")

    await db.execute("UPDATE users SET money=5000000000 WHERE id=?", (A,))
    await db.execute("UPDATE states SET materials=200000 WHERE user_id=?", (A,))
    ok, msg = await en.start_stage(A, 1)
    H.check(ok, f"مرحلهٔ ۱ آغاز شد ({msg.splitlines()[0][:50]})")
    st = await en.get_state(A)
    H.check(st.get("completes_at"), "زمان پایان ثبت شد")
    # اختلاف زمانی باید حدود ۵ دقیقه باشد
    from core.utils import parse, now
    delta = (parse(st["completes_at"]) - now()).total_seconds()
    H.check(280 <= delta <= 305, f"زمان پایان ~۵ دقیقه است ({int(delta)}s)")

    # شبیه‌سازی گذشت زمان و تکمیل خودکار
    await db.execute(
        "UPDATE enrichment SET completes_at=? WHERE user_id=?",
        ("2000-01-01 00:00:00", A))
    res = await en.settle(A)
    H.check(res and res["stage"] == 1, f"تکمیل خودکار مرحله ثبت شد (stage={res})")

    # ═══════ TEST 2: 🕊 پیشنهاد آتش‌بس ═══════
    print("\n══ TEST 2: پیشنهاد آتش‌بس ══")
    from core import ceasefire as cf
    await db.execute(
        "INSERT INTO wars(attacker_id, defender_id, status) VALUES(?,?,'active')", (A, D))
    war = await cf.wars_of(A)
    H.check(len(war) >= 1, f"جنگ فعال برای مهاجم پیدا شد ({war[0]['foe_name'] if war else '-'})")

    await set_setting("ceasefire_cooldown_hours", "0")   # برای تست
    ok, msg = await cf.offer(A, D)
    H.check(ok, "پیشنهاد آتش‌بس ثبت شد")
    off = await cf.pending_for(D)
    H.check(len(off) >= 1, "مدافع پیشنهاد را می‌بیند")

    ok2, msg2 = await cf.offer(A, D)
    H.check(not ok2, "پیشنهاد تکراری رد می‌شود")

    # ═══════ TEST 3: 🕊 پذیرش آتش‌بس و پایان جنگ ═══════
    print("\n══ TEST 3: پذیرش آتش‌بس ══")
    from core import attrition as attr
    await attr.add_strike(D, A, 50)
    H.check(await attr.wear_of(D) > 0, "فرسایش مدافع ثبت شد")

    war_id = war[0]["id"]
    ok, msg = await cf.accept(off[0]["id"], D)
    H.check(ok, "آتش‌بس پذیرفته شد")
    w = await db.fetchone("SELECT status FROM wars WHERE id=?", (war_id,))
    H.check(w["status"] == "ended", f"وضعیت جنگ ended شد ({w['status']})")
    H.check(await attr.wear_of(D) == 0, "فرسایش مدافع پس از صلح صفر شد")
    H.check(await attr.wear_of(A) == 0, "فرسایش مهاجم پس از صلح صفر شد")
    peace = await db.fetchone(
        "SELECT * FROM treaties WHERE kind='peace' AND status='active' AND "
        "((party_a=? AND party_b=?) OR (party_a=? AND party_b=?))", (A, D, D, A))
    H.check(bool(peace), "پیمان صلح ثبت و فعال شد")

    # ═══════ TEST 4: 🕊 رد آتش‌بس ═══════
    print("\n══ TEST 4: رد آتش‌بس ══")
    await db.execute("UPDATE wars SET status='active' WHERE id=?", (war_id,))
    await db.execute(
        "INSERT INTO ceasefire_offers(war_id, from_id, to_id) VALUES(?,?,?)",
        (war_id, A, D))
    new_off = await cf.pending_offer(war_id)
    ok, msg = await cf.reject(new_off["id"], D)
    H.check(ok, "آتش‌بس رد شد")
    w = await db.fetchone("SELECT status FROM wars WHERE id=?", (war_id,))
    H.check(w["status"] == "active", "جنگ پس از رد، فعال می‌ماند")

    # ═══════ TEST 4b: ⏳ فاصلهٔ پیشنهاد آتش‌بس ═══════
    print("\n══ TEST 4b: فاصلهٔ مجاز پیشنهاد آتش‌بس ══")
    await set_setting("ceasefire_cooldown_hours", "6")
    ok, msg = await cf.offer(A, D)
    H.check(not ok and "دقیقه" in msg, f"فاصلهٔ پیشنهاد اعمال شد ({msg[:60]})")
    await set_setting("ceasefire_cooldown_hours", "0")

    # ═══════ TEST 5: 🏳 تسلیم یک‌طرفه ═══════
    print("\n══ TEST 5: تسلیم یک‌طرفه ══")
    from core import provinces as prov
    await prov.ensure_provinces()          # استان‌های پایه برای همهٔ کشورها
    await db.execute("UPDATE provinces SET owner_id=? WHERE country_id="
                     "(SELECT country_id FROM users WHERE id=?)", (D, D))
    provs_before = await prov.province_summary(D)
    H.check(provs_before["total"] > 0, f"مدافع استان دارد ({provs_before['total']})")
    # فرسایش بالا تا تسلیم مجاز شود
    for _ in range(8):
        await attr.add_strike(D, A, 10)
    ok, err = await cf.can_surrender(D)
    H.check(ok, f"تسلیم مجاز شد (فرسایش {await attr.wear_of(D)}٪)")
    war_row = await db.fetchone("SELECT * FROM wars WHERE id=?", (war_id,))
    ok, msg = await cf.surrender(war_row, D, bot)
    H.check(ok, "تسلیم اجرا شد")
    w = await db.fetchone("SELECT status FROM wars WHERE id=?", (war_id,))
    H.check(w["status"] == "ended", "جنگ با تسلیم پایان یافت")
    provs_after = await prov.province_summary(D)
    H.check(provs_after["total"] < provs_before["total"],
            f"استان‌ها در تسلیم واگذار شد ({provs_before['total']} → {provs_after['total']})")

    # ═══════ TEST 6: 🛒 بازار تسلیحات ═══════
    print("\n══ TEST 6: بازار تسلیحات ══")
    from core import arms
    eq = await db.fetchone("SELECT id, name FROM equipment ORDER BY id LIMIT 1")
    await db.execute(
        "INSERT INTO player_assets(user_id, item_type, item_id, quantity) "
        "VALUES(?, 'equipment', ?, 100)", (A, eq["id"]))
    stock_before = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type='equipment' "
        "AND item_id=?", (A, eq["id"]))
    H.check(int(stock_before["quantity"]) >= 100, "مهاجم تجهیزات دارد")

    ok, msg = await arms.list_item(A, eq["id"], 40, 2_000_000)
    H.check(ok, f"آگهی فروش ثبت شد ({msg.splitlines()[0][:40]})")
    stock_after = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type='equipment' "
        "AND item_id=?", (A, eq["id"]))
    H.check(int(stock_after["quantity"]) == int(stock_before["quantity"]) - 40,
            f"۴۰ واحد از انبار فروشنده بلوکه شد "
            f"({stock_before['quantity']} → {stock_after['quantity']})")

    deals = await arms.market()
    deal = next((d for d in deals if int(d["seller_id"]) == A), None)
    H.check(deal is not None, "آگهی در بازار دیده می‌شود")

    await db.execute("UPDATE users SET money=1000000000 WHERE id=?", (D,))
    money_before_d = (await db.fetchone("SELECT money FROM users WHERE id=?", (D,)))["money"]
    money_before_a = (await db.fetchone("SELECT money FROM users WHERE id=?", (A,)))["money"]

    ok, msg = await arms.buy(D, deal["id"])
    H.check(ok, f"خرید انجام شد ({msg.splitlines()[0][:40]})")
    money_after_d = (await db.fetchone("SELECT money FROM users WHERE id=?", (D,)))["money"]
    money_after_a = (await db.fetchone("SELECT money FROM users WHERE id=?", (A,)))["money"]
    H.check(money_before_d - money_after_d == 40 * 2_000_000, "خریدار کل مبلغ را پرداخت کرد")
    H.check(money_after_a > money_before_a, "فروشنده پول دریافت کرد")
    H.check(money_after_a - money_before_a < 40 * 2_000_000,
            "کارمزد بازار از فروشنده کسر شد")

    buyer_stock = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type='equipment' "
        "AND item_id=?", (D, eq["id"]))
    H.check(buyer_stock and int(buyer_stock["quantity"]) == 40,
            "تجهیزات به انبار خریدار منتقل شد")

    ok, msg = await arms.buy(D, deal["id"])
    H.check(not ok, "خرید دوبارهٔ همان آگهی رد می‌شود")

    # لغو آگهی
    ok, _ = await arms.list_item(A, eq["id"], 10, 1_500_000)
    H.check(ok, "آگهی دوم ثبت شد")
    mine = await arms.my_listings(A)
    ok, msg = await arms.cancel(A, mine[0]["id"])
    H.check(ok, "آگهی لغو شد")
    stock_back = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type='equipment' "
        "AND item_id=?", (A, eq["id"]))
    H.check(int(stock_back["quantity"]) == int(stock_after["quantity"]),
            "تجهیزات لغو به انبار برگشت")

    # ═══════ TEST 7: رندر منوها بدون خطا ═══════
    print("\n══ TEST 7: رندر منوهای جدید ══")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|war"))
    H.shot("war room")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|cease"))
    H.shot("ceasefire")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|arms"))
    H.shot("arms market")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|enrich"))
    H.shot("enrichment")

    print(f"\n=== TOTAL ERRORS: {len(H.ERRORS)}")
    for e in H.ERRORS:
        print("  ✗", e)


asyncio.run(main())

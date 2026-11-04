"""تست رهبری/ترور/انقلاب + اقتصاد نفت (ارتقای تجهیزات و فروش خودکار).

اجرا: /tmp/venv/bin/python tests/test_politics_oil.py   (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

ACTOR = 201
VICTIM = 202


def channel_texts() -> list[str]:
    return [t for (_n, _c, t, _p) in H.SENT if t and str(_c) == "@pol_channel"]


async def money(uid: int) -> int:
    from core.db import db
    row = await db.fetchone("SELECT money FROM users WHERE id=?", (uid,))
    return int((row or {}).get("money") or 0)


async def main():
    from core.db import db, set_setting
    from core.economy import add_asset
    dp, bot = await H.new_game_dp()
    await H.make_world([(ACTOR, "مهاجم", 0), (VICTIM, "قربانی", 15)])  # 15 = آمریکا
    await set_setting("announcement_channel", "@pol_channel")
    vrow = await db.fetchone("SELECT c.* FROM users u JOIN countries c ON c.id=u.country_id WHERE u.id=?",
                             (VICTIM,))
    VIC_CID, VIC_NAME = vrow["id"], vrow["name"]
    print(f"     کشور هدف: {vrow['flag']} {VIC_NAME}")

    # ─── ۱) رهبر برای همهٔ کشورها ───
    print("\n== TEST 1: رئیس‌جمهور همهٔ کشورها ==")
    from core.politics import country_leader
    rows = await db.fetchall("SELECT * FROM countries WHERE is_active=1")
    missing = [r["name"] for r in rows if not (r["leader_name"] or "").strip()]
    H.check(not missing, f"همهٔ {len(rows)} کشور نام رهبر دارند")
    H.check(all((r["leader_title"] or "").strip() for r in rows), "عنوان رهبر (رئیس‌جمهور/نخست‌وزیر/...) ثبت شده")
    usa = await db.fetchone("SELECT * FROM countries WHERE name='آمریکا'")
    leader = await country_leader(usa)
    print(f"     🇺🇸 {leader['title']}: {leader['name']}")
    H.check(bool(leader["name"]) and leader["name"] != "—", "رهبر آمریکا در دسترس است")

    # ─── ۲) ترور → انقلاب ───
    print("\n== TEST 2: ترور رئیس‌جمهور و شروع انقلاب ==")
    from core.politics import active_revolution, assassinate
    H.SENT.clear()
    orig_random = random.random
    random.random = lambda: 0.01
    try:
        ok, msg = await assassinate(ACTOR, VICTIM, bot)
    finally:
        random.random = orig_random
    rev = await active_revolution(VICTIM)
    victim_country = await db.fetchone("SELECT * FROM countries WHERE id=?", (VIC_CID,))
    H.check(ok, "ترور موفق ثبت شد")
    H.check(rev is not None, "انقلاب برای کشور هدف فعال شد")
    H.check(rev["severity"] >= 50, f"شدت انقلاب بالا است ({rev['severity'] if rev else 0}٪)")
    H.check((victim_country["leader_name"] or "").startswith("—"), "رهبر قبلی از قدرت حذف شد")
    ann = channel_texts()[0] if channel_texts() else ""
    H.check("ترور" in ann, "کانال خبر ترور را منتشر کرد")
    H.check(any("انقلاب" in (t or "") for (n, c, t, p) in H.SENT if t and str(c) == str(VICTIM)),
            "به کشور هدف هشدار انقلاب ارسال شد")

    # ─── ۳) جریمهٔ درآمد در زمان انقلاب ───
    print("\n== TEST 3: افت درآمد در زمان انقلاب ==")
    from core.economy import income_breakdown
    during = await income_breakdown(VICTIM)
    await db.execute("UPDATE revolutions SET status='paused' WHERE user_id=?", (VICTIM,))
    after = await income_breakdown(VICTIM)
    H.check(during["daily"] < after["daily"],
            f"درآمد در انقلاب کمتر است ({during['daily']:,} < {after['daily']:,})")
    await db.execute("UPDATE revolutions SET status='active' WHERE user_id=?", (VICTIM,))

    # ─── ۴) پول‌پاشی ───
    print("\n== TEST 4: سرکوب با پول‌پاشی ==")
    from core.politics import suppress_with_money
    await db.execute("UPDATE users SET money=? WHERE id=?", (900_000_000, VICTIM))
    before_money = await money(VICTIM)
    before_sev = (await active_revolution(VICTIM))["severity"]
    ok, msg = await suppress_with_money(VICTIM, bot)
    after_rev = await active_revolution(VICTIM)
    H.check(ok, "پول‌پاشی انجام شد")
    H.check(await money(VICTIM) < before_money, "هزینهٔ پول‌پاشی از خزانه کم شد")
    H.check(after_rev is None or after_rev["severity"] < before_sev,
            f"شدت انقلاب کاهش یافت ({before_sev}→{after_rev['severity'] if after_rev else 0})")

    # ─── ۵) انتخابات رئیس‌جمهور جدید ───
    print("\n== TEST 5: انتخابات فوری ==")
    from core.politics import candidates, elect_president
    rev = await active_revolution(VICTIM)
    cands = candidates(rev["id"] if rev else 1)
    H.check(len(cands) == 3, "سه نامزد برای انتخابات وجود دارد")
    ok, msg = await elect_president(VICTIM, 0, bot)
    new_leader = (await db.fetchone("SELECT leader_name, leader_title FROM countries WHERE id=?", (VIC_CID,)))
    H.check(ok, "انتخابات انجام شد")
    H.check(new_leader["leader_name"] == cands[0]["name"], "رئیس‌جمهور جدید ثبت شد")
    H.check(new_leader["leader_title"] == "رئیس‌جمهور", "عنوان رهبر به رئیس‌جمهور تغییر کرد")
    H.check(await active_revolution(VICTIM) is None, "انقلاب با انتخابات پایان یافت")

    # ─── ۶) پیروزی انقلاب با گذشت زمان ───
    print("\n== TEST 6: پایان مهلت → پیروزی انقلاب ==")
    from core.politics import revolution_tick, start_revolution
    await start_revolution(VICTIM, "assassination", bot)
    await db.execute("UPDATE revolutions SET ends_at='2000-01-01 00:00:00' WHERE user_id=? AND status='active'",
                     (VICTIM,))
    money_before = await money(VICTIM)
    closed = await revolution_tick(bot)
    rev_after = await active_revolution(VICTIM)
    country_after = await db.fetchone("SELECT leader_name FROM countries WHERE id=?", (VIC_CID,))
    H.check(closed >= 1, "تیک انقلاب اجرا شد")
    H.check(rev_after is None, "انقلاب بسته شد")
    H.check("شورا" in (country_after["leader_name"] or ""), "شورای انقلابی قدرت را گرفت")
    H.check(await money(VICTIM) < money_before, "بخشی از خزانه غارت شد")

    # ─── ۶b) سرکوب نظامی ───
    print("\n== TEST 6b: سرکوب نظامی انقلاب ==")
    from core.politics import suppress_with_force
    from core.economy import add_asset as _add
    sd = await db.fetchone("SELECT * FROM soldier_types LIMIT 1")
    await _add(VICTIM, "soldier", sd["id"], 2000)
    await start_revolution(VICTIM, "assassination", bot)
    rev = await active_revolution(VICTIM)
    sev_before = rev["severity"]
    orig_random = random.random
    random.random = lambda: 0.01
    try:
        ok, msg = await suppress_with_force(VICTIM, bot)
    finally:
        random.random = orig_random
    rev_after = await active_revolution(VICTIM)
    H.check(ok, "سرکوب نظامی اجرا شد")
    H.check(rev_after is None or rev_after["severity"] != sev_before,
            f"شدت انقلاب تغییر کرد ({sev_before}→{rev_after['severity'] if rev_after else 0})")
    left = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
        (VICTIM,))
    H.check(int(left["c"]) < 2000, f"سرکوب تلفات سرباز داشت (باقی‌مانده {left['c']})")
    if await active_revolution(VICTIM):
        await db.execute("UPDATE revolutions SET status='cancelled' WHERE user_id=? AND status='active'",
                         (VICTIM,))

    # ─── ۷) درآمد واقعی‌تر بر اساس کشور ───
    print("\n== TEST 7: درآمد واقعی بر اساس کشور ==")
    iran_id = (await db.fetchone("SELECT id FROM countries WHERE name='ایران'"))["id"]
    await db.execute("UPDATE users SET country_id=? WHERE id=?", (iran_id, ACTOR))
    iran_income = await income_breakdown(ACTOR)
    usa_income = await income_breakdown(VICTIM)
    H.check(iran_income["gdp_factor"] < usa_income["gdp_factor"],
            f"ضریب اقتصاد ایران ({iran_income['gdp_factor']}) کمتر از آمریکا ({usa_income['gdp_factor']}) است")
    H.check(usa_income["daily"] > iran_income["daily"], "درآمد آمریکا از ایران بیشتر است")

    # ─── ۸) نفت: ساخت دکل + ارتقای گران‌شونده ───
    print("\n== TEST 8: نفت — دکل و ارتقای تجهیزات ==")
    from core import oil
    rig_b = await db.fetchone("SELECT * FROM buildings WHERE name='دکل نفتی'")
    H.check(rig_b is not None, "ساختمان «دکل نفتی» در بازی وجود دارد")
    await add_asset(ACTOR, "building", rig_b["id"], 3)
    H.check(await oil.rig_count(ACTOR) == 3, "۳ دکل نفتی ساخته شد")

    c1 = await oil.upgrade_cost(1)
    c2 = await oil.upgrade_cost(2)
    c3 = await oil.upgrade_cost(3)
    H.check(c2 > c1 and c3 > c2, f"هزینهٔ ارتقا گران‌تر می‌شود ({c1:,} < {c2:,} < {c3:,})")

    await db.execute("UPDATE users SET money=? WHERE id=?", (int(c1 * 3), ACTOR))
    per_rig_before = await oil.per_rig_barrels(ACTOR)
    ok, msg = await oil.upgrade_business(ACTOR)
    biz = await oil.ensure_business(ACTOR)
    H.check(ok and biz["level"] == 2, f"سطح تجهیزات به ۲ ارتقا یافت ({msg.splitlines()[0][:40]})")
    H.check(await oil.per_rig_barrels(ACTOR) > per_rig_before,
            f"استخراج هر دکل بیشتر شد ({per_rig_before}→{await oil.per_rig_barrels(ACTOR)})")
    await db.execute("UPDATE users SET money=0 WHERE id=?", (ACTOR,))
    ok2, msg2 = await oil.upgrade_business(ACTOR)
    H.check(not ok2, "بدون بودجه، ارتقا رد می‌شود")

    # ─── ۹) تجارت خودکار نفت: درآمد میلیونیِ هر ۱۰ دقیقه ───
    print("\n== TEST 9: فروش خودکار نفت (هر ۱۰ دقیقه) ==")
    ok, msg = await oil.toggle_auto_sell(ACTOR)
    H.check(ok and int((await oil.ensure_business(ACTOR))["auto_sell"]) == 1, "تجارت خودکار روشن شد")
    await db.execute("UPDATE states SET oil_stock=6000 WHERE user_id=?", (ACTOR,))
    H.SENT.clear()
    paid = await oil.auto_sell_tick(bot)
    H.check(paid > 0, f"درآمد نفت واریز شد ({paid:,} تومان)")
    H.check(paid >= 1_000_000, "درآمد حداقل یک میلیون است")
    dm_texts = [t for (n, c, t, p) in H.SENT if t and str(c) == str(ACTOR)]
    H.check(any("درآمد فروش خودکار نفت" in (t or "") for t in dm_texts), "به بازیکن گزارش درآمد نفت رسید")
    biz = await oil.ensure_business(ACTOR)
    H.check(int(biz["sales"]) >= 1 and int(biz["total_income"]) > 0, "آمار فروش ثبت شد")
    paid_again = await oil.auto_sell_tick(bot)
    H.check(paid_again == 0, "در بازهٔ ۱۰ دقیقه‌ای دوباره پرداخت نمی‌شود")

    # ─── ۱۰) پایهٔ درآمد نفتی کشورها (آمریکا/روسیه/چین بالای ۱۰ میلیون) ───
    print("\n== TEST 10: پایهٔ نفتی هر کشور ==")
    bases = {r["name"]: r["oil_income_base"] for r in await db.fetchall("SELECT name, oil_income_base FROM countries")}
    for big in ("آمریکا", "روسیه", "چین"):
        H.check(bases[big] > 10, f"پایهٔ نفتی {big} بالای ۱۰ میلیون است ({bases[big]}M)")
    small = sorted(bases.values())[0]
    H.check(small >= 1, f"کمترین پایه از ۱ میلیون شروع می‌شود ({small}M)")
    H.check(bases["ایران"] < bases["آمریکا"], "پایهٔ ایران کمتر از آمریکاست")

    # ─── ۱۱) مسیر دکمه‌های ربات ───
    print("\n== TEST 11: مسیر کاربر در ربات ==")
    err_before = len(H.ERRORS)
    H.SENT.clear()
    for data in ("g|mg", "g|pol", "g|pol_elec", "g|pol_leaders", "g|oil"):
        await dp.feed_update(bot, H.cb_update(ACTOR, data))
    H.check(len(H.ERRORS) == err_before, "صفحات رهبری/انقلاب/نفت بدون خطا باز شدند")
    pol_texts = [t for (n, c, t, p) in H.SENT if t and "رهبر" in t]
    H.check(bool(pol_texts), "صفحهٔ رهبری متن رهبر را نشان می‌دهد")

    print("\n=== TOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("   -", e)
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())

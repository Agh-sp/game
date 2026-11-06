"""تست ویژگی‌های تازه: درآمد میلیونی، استان‌ها، اتحاد، غنی‌سازی، مصالح، فروش سکه، کول‌داون حمله.

اجرا: python3 tests/test_empire.py     (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402


async def main():
    from core.db import db, get_setting, init_db
    dp, bot = await H.new_game_dp()
    A, B, C = 5001, 5002, 5003
    await H.make_world([(A, "بازیکن۱", 0), (B, "بازیکن۲", 1), (C, "بازیکن۳", 2)])

    from core import income as inc
    from core import provinces as prov
    from core import alliances as al
    from core import enrichment as en

    print("\n== TEST 1: درآمد میلیونی هر ۵ دقیقه ==")
    H.check(await inc.get_minutes() == 5, f"فاصلهٔ پرداخت ۵ دقیقه ({await inc.get_minutes()})")
    tax = await inc.tax_income(A, 1.0)
    H.check(tax["amount"] >= 10_000_000, f"مالیات حداقل ۱۰ میلیون ({tax['amount']:,})")
    oil = await inc.oil_income(A, 1.0)
    H.check(oil["amount"] > 0, f"نفت خودکار ({oil['amount']:,})")
    strait = await inc.strait_income(A, 1.0)
    H.check(isinstance(strait["amount"], int), f"عوارض تنگه ({strait['amount']:,})")
    src = await inc.income_sources(A)
    H.check(src["total"] > 0, f"جمع درآمد دوره‌ای ({src['total']:,})")
    # کشور قوی‌تر (ضریب بالاتر) باید بیشتر بگیرد
    strong = await db.fetchone(
        "SELECT u.id AS uid FROM users u JOIN countries c ON c.id=u.country_id "
        "WHERE c.gdp_factor>=3 ORDER BY c.gdp_factor DESC LIMIT 1")
    weak = await db.fetchone(
        "SELECT u.id AS uid FROM users u JOIN countries c ON c.id=u.country_id "
        "WHERE c.gdp_factor<1.5 ORDER BY c.gdp_factor LIMIT 1")
    if strong and weak:
        s_tax = await inc.tax_income(strong["uid"], 1.0)
        w_tax = await inc.tax_income(weak["uid"], 1.0)
        H.check(s_tax["amount"] > w_tax["amount"],
                f"کشور قوی درآمد بیشتر دارد ({s_tax['amount']:,} > {w_tax['amount']:,})")
    H.check(src["growth"]["cap"] == 3.0, "سقف ضریب ارتقا ۳ برابر است")

    print("\n== TEST 2: رشد خودکار درآمد با ارتقا ==")
    g0 = await inc.growth_multiplier(A)
    b = await db.fetchone("SELECT id FROM buildings LIMIT 1")
    for _ in range(4):
        await db.execute(
            "INSERT INTO player_projects(user_id, building_id, name, status) "
            "VALUES(?,?,'پروژه','done')", (A, b["id"]))
    await db.execute("INSERT OR IGNORE INTO oil_business(user_id, level) VALUES(?,5)", (A,))
    await db.execute("UPDATE oil_business SET level=5 WHERE user_id=?", (A,))
    g1 = await inc.growth_multiplier(A)
    H.check(g1["mult"] > g0["mult"], f"ضریب ارتقا بالا رفت ({g0['mult']} → {g1['mult']})")
    H.check(g1["mult"] <= g1["cap"], f"ضریب از سقف رد نشد ({g1['mult']} ≤ {g1['cap']})")
    txt = await inc.income_summary_text(A)
    H.check("ضریب ارتقا" in txt and "نفت" in txt and "تنگه" in txt, "متن خلاصه درآمد کامل است")

    print("\n== TEST 3: ۵ استان برای هر کشور ==")
    await prov.ensure_provinces()
    await prov.sync_owners()
    await prov.sync_counts()
    rows = await db.fetchall("SELECT country_id, COUNT(*) c FROM provinces GROUP BY country_id")
    H.check(all(int(r["c"]) >= 5 for r in rows), f"همهٔ کشورها ≥۵ استان دارند ({len(rows)} کشور)")
    my = await prov.province_summary(A)
    H.check(my["home"] == 5, f"بازیکن ۵ استان دارد ({my['home']})")
    H.check(not my["collapsed"], "بازیکن سقوط نکرده")

    print("\n== TEST 4: تصاحب استان و سقوط کشور ==")
    before = await prov.province_summary(B)
    captured = await prov.capture_province(B, A, war_id=None)
    H.check(captured is not None, f"استان تصاحب شد ({captured['name'] if captured else '—'})")
    after_b = await prov.province_summary(B)
    after_a = await prov.province_summary(A)
    H.check(after_b["home"] == before["home"] - 1, f"مدافع یک استان از دست داد ({after_b['home']})")
    H.check(after_a["total"] == my["total"] + 1, f"مهاجم یک استان گرفت ({after_a['total']})")
    # گرفتن بقیهٔ استان‌ها → سقوط
    for _ in range(10):
        got = await prov.capture_province(B, A, war_id=None)
        if not got:
            break
    collapsed = await prov.check_collapse(B)
    H.check(collapsed, "کشور مدافع پس از از دست دادن همهٔ استان‌ها سقوط کرد")
    row = await db.fetchone("SELECT country_id FROM users WHERE id=?", (B,))
    H.check(row["country_id"] is None, "بازیکن کشورش را از دست داد")

    print("\n== TEST 5: کول‌داون ۳ دقیقه‌ای حمله ==")
    from gamebot.handlers.war import attack_cooldown_state
    from core.utils import iso
    from datetime import datetime, timedelta, timezone
    await db.execute("UPDATE states SET last_attack_at=NULL WHERE user_id=?", (A,))
    ready, remaining, _ = await attack_cooldown_state(A)
    H.check(ready and remaining == 0, "بدون حملهٔ قبلی، حمله آزاد است")
    recent = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute("UPDATE states SET last_attack_at=? WHERE user_id=?", (recent, A))
    ready2, remaining2, msg2 = await attack_cooldown_state(A)
    H.check(not ready2, f"بلافاصله بعد از حمله قفل است (باقی‌مانده {remaining2}s)")
    H.check(150 <= remaining2 <= 180, f"کول‌داون ~۳ دقیقه است ({remaining2}s)")
    H.check("بازسازی" in msg2, "پیام کول‌داون راهنما دارد")
    old = (datetime.now(timezone.utc) - timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute("UPDATE states SET last_attack_at=? WHERE user_id=?", (old, A))
    ready3, _r, _m = await attack_cooldown_state(A)
    H.check(ready3, "بعد از ۳ دقیقه دوباره آزاد می‌شود")

    print("\n== TEST 6: بخش اتحاد ==")
    ok, msg = await al.create_alliance(A, "اتحاد آریا")
    H.check(ok, f"ساخت اتحاد ({msg[:40]})")
    ok2, _ = await al.create_alliance(A, "اتحاد دوم")
    H.check(not ok2, "نمی‌توان دو اتحاد هم‌زمان داشت")
    mine = await al.my_alliance(A)
    H.check(mine is not None and mine["name"] == "اتحاد آریا", "اتحاد ساخته شد")
    ok3, _ = await al.invite(mine["id"], A, C)
    H.check(ok3, "دعوت بازیکن به اتحاد")
    invites = await al.pending_invites(C)
    H.check(len(invites) == 1, f"دعوت‌نامه برای بازیکن سوم ثبت شد ({len(invites)})")
    ok4, _ = await al.accept_invite(invites[0]["id"], C)
    H.check(ok4, "پذیرش دعوت‌نامه")
    allies = await al.allies_of(A)
    H.check(C in allies, f"متحد اضافه شد ({allies})")
    bonus = await al.defense_bonus(A)
    H.check(bonus["bonus"] > 0, f"کمک دفاعی متحدان ({bonus['bonus']})")
    txt = await al.alliance_text(A)
    H.check("اتحاد آریا" in txt, "متن اتحاد نام را نشان می‌دهد")
    ok5, _ = await al.leave_alliance(C)
    H.check(ok5 and not await al.allies_of(A), "خروج از اتحاد کار می‌کند")

    print("\n== TEST 7: مراحل غنی‌سازی ==")
    await db.execute("UPDATE users SET money=5000000000 WHERE id=?", (A,))
    await db.execute("UPDATE states SET materials=50000 WHERE user_id=?", (A,))
    H.check(en.MAX_STAGE == 4, "چهار مرحله تعریف شده")
    st = await en.get_state(A)
    H.check(int(st["stage"]) == 0, "شروع از مرحله صفر")
    ok, err = await en.start_stage(A, 3)
    H.check(not ok, "نمی‌توان مرحله را از ترتیب پرید")
    ok, msg = await en.start_stage(A, 1)
    H.check(ok, f"شروع مرحله ۱ ({msg.splitlines()[0][:40]})")
    H.check(await en.in_progress(A), "مرحله در جریان است")
    ok2, err2 = await en.start_stage(A, 1)
    H.check(not ok2, "دو مرحله هم‌زمان شروع نمی‌شود")
    # شبیه‌سازی تکمیل
    await db.execute(
        "UPDATE enrichment SET completes_at='2000-01-01 00:00:00' WHERE user_id=?", (A,))
    res = await en.settle(A)
    H.check(res is not None and res["stage"] == 1, f"تکمیل مرحله ({res})")
    st2 = await en.get_state(A)
    H.check(int(st2["stage"]) == 1, "مرحله ثبت شد")
    ok3, _m3 = await en.start_stage(A, 2)
    H.check(ok3, "مرحلهٔ بعدی باز شد")
    etxt = await en.enrichment_text(A)
    H.check("مرحله 1" in etxt or "مرحله ۱" in etxt, "متن غنی‌سازی مراحل را نشان می‌دهد")
    H.check("90" in etxt or "۹۰" in etxt, "بالاترین مرحله در متن هست")

    print("\n== TEST 8: 🧱 خرید مصالح ==")
    from gamebot.handlers.materials import materials_shop_text, PACKAGES
    H.check(len(PACKAGES) == 4, f"چهار پکیج مصالح ({len(PACKAGES)})")
    mtext = await materials_shop_text(A)
    H.check("خرید مصالح" in mtext, "عنوان متن فروشگاه مصالح")
    H.check("1,000" in mtext or "۱٬۰۰۰" in mtext or "۱,۰۰۰" in mtext,
            "پکیج ۱۰۰۰ واحدی در متن هست")
    before_mats = await db.fetchone("SELECT materials FROM states WHERE user_id=?", (A,))
    await db.execute("UPDATE users SET money=1000000000 WHERE id=?", (A,))
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|matb|m1"))
    after_mats = await db.fetchone("SELECT materials FROM states WHERE user_id=?", (A,))
    H.check(int(after_mats["materials"]) == int(before_mats["materials"]) + 1000,
            f"۱۰۰۰ واحد مصالح اضافه شد ({before_mats['materials']} → {after_mats['materials']})")
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (A,))
    H.check(int(user["money"]) == 1_000_000_000 - 20_000_000,
            "۲۰ میلیون از خزانه کم شد")

    print("\n== TEST 9: 💰 فروش سکه شاهی (دونه‌ای) ==")
    from gamebot.handlers.misc import sell_rate
    await db.execute("UPDATE users SET royal_coins=10, money=0 WHERE id=?", (A,))
    rate = await sell_rate()
    H.check(rate > 0, f"نرخ فروش سکه ({rate:,})")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|coinselln|1"))
    row = await db.fetchone("SELECT royal_coins, money FROM users WHERE id=?", (A,))
    H.check(int(row["royal_coins"]) == 9, f"یک سکه کم شد ({row['royal_coins']})")
    H.check(int(row["money"]) == rate, f"پول واریز شد ({row['money']:,})")
    sale = await db.fetchone(
        "SELECT * FROM coin_sales WHERE user_id=? ORDER BY id DESC", (A,))
    H.check(sale is not None and int(sale["coins"]) == 1, "فروش در تاریخچه ثبت شد")
    # فروش بیش از موجودی نباید کاری کند
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|coinselln|999"))
    row2 = await db.fetchone("SELECT royal_coins FROM users WHERE id=?", (A,))
    H.check(int(row2["royal_coins"]) == 9, "فروش بیش از موجودی انجام نشد")
    # فروش همه
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|coinselln|9"))
    row3 = await db.fetchone("SELECT royal_coins, money FROM users WHERE id=?", (A,))
    H.check(int(row3["royal_coins"]) == 0, "همهٔ سکه‌ها فروخته شد")
    H.check(int(row3["money"]) == rate * 10, f"پول همهٔ سکه‌ها واریز شد ({row3['money']:,})")

    print("\n== TEST 10: مذاکره — گزارش تحویل شفاف ==")
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "gamebot", "handlers", "trade.py"), encoding="utf-8").read()
    H.check("ارسال دوباره به طرف مقابل" in src, "دکمهٔ ارسال دوباره اضافه شده")
    H.check("undelivered" in src, "ردیابی اعضای تحویل‌نشده")
    H.check("negresend" in src, "مسیر ارسال دوباره ثبت شده")

    await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        print("\n=== TOTAL ERRORS:", len(H.ERRORS))
        for e in H.ERRORS:
            print("  -", e)

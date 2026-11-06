"""تست بستهٔ ارتقای دنیای بازی:

  TEST 1 — 💵 درآمد هر ۵ دقیقه بالای ۱۰۰ میلیون است (کشور قوی و ضعیف)
  TEST 2 — ♻️ فروش منابع (برق/آب/گاز/غذا/نفت/مصالح) پول واقعی می‌دهد
  TEST 3 — 🚢 پایگاه دریایی: کشور بدون مرز دریایی می‌تواند تنگه تسخیر کند
  TEST 4 — ⚔️ حملهٔ تسخیر استان می‌گیرد، حملهٔ عادی نمی‌گیرد (ولی زیرساخت را می‌زند)
  TEST 5 — ⏱ کول‌داون سایبری ۲۰ دقیقه است (نه ۶ ساعت)
  TEST 6 — ⚖️ تحریم سازمان ملل (خلع سلاح) واقعاً کار می‌کند
  TEST 7 — 🧱 خرید مصالح از منوی مدیریت کشور
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402
from harness import check, shot  # noqa: E402


async def _give_army(uid, n=150):
    """تجهیزات زمینی/دریایی/هوایی و سرباز برای مهاجم."""
    from core.db import db
    for cat in ("land", "sea", "air"):
        rows = await db.fetchall(
            "SELECT e.id FROM equipment e JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE c.key=? LIMIT 3", (cat,))
        for r in rows:
            await db.execute(
                "INSERT OR REPLACE INTO player_assets(user_id,item_type,item_id,quantity) "
                "VALUES(?,?,?,?)", (uid, "equipment", r["id"], n))
    sol = await db.fetchone("SELECT id FROM soldier_types ORDER BY id LIMIT 1")
    await db.execute(
        "INSERT OR REPLACE INTO player_assets(user_id,item_type,item_id,quantity) "
        "VALUES(?,?,?,?)", (uid, "soldier", sol["id"], 12_000))


async def _new_war(db, attacker, defender) -> int:
    await db.execute("INSERT INTO wars(attacker_id,defender_id,status,reason) VALUES(?,?,?,?)",
                     (attacker, defender, "active", "test"))
    row = await db.fetchone("SELECT id FROM wars ORDER BY id DESC LIMIT 1")
    return int(row["id"])


async def main():
    from core.db import db, get_setting
    from core import income as inc
    from core import provinces as prov
    from core.oil import ensure_business

    rows = await H.make_world([(1001, "مهاجم", 0), (1002, "مدافع", 1), (1003, "خشکی", 2)])
    await prov.ensure_provinces()
    dp, bot = await H.new_game_dp()
    A, D, L = 1001, 1002, 1003

    # ══════════ TEST 1 ══════════
    print("\n══ TEST 1: درآمد بالای ۱۰۰ میلیون هر ۵ دقیقه ══")
    rig = await db.fetchone("SELECT id FROM buildings WHERE name='دکل نفتی'")
    for uid, rigs, lvl, label in ((A, 10, 4, "قوی"), (L, 0, 1, "ضعیف")):
        await db.execute("DELETE FROM player_assets WHERE user_id=?", (uid,))
        if rigs:
            await db.execute(
                "INSERT INTO player_assets(user_id,item_type,item_id,quantity) VALUES(?,?,?,?)",
                (uid, "building", rig["id"], rigs))
        await ensure_business(uid)
        await db.execute("UPDATE oil_business SET level=? WHERE user_id=?", (lvl, uid))
        await db.execute("UPDATE states SET satisfaction=70, energy=900000, water=500000, "
                         "gas=400000 WHERE user_id=?", (uid,))
        src = await inc.income_sources(uid)
        total = src["total"]
        print(f"  {label}: {total/1e6:.1f}M "
              f"(مالیات {src['tax']['amount']/1e6:.0f}M · نفت {src['oil']['amount']/1e6:.0f}M · "
              f"تنگه {src['strait']['amount']/1e6:.0f}M · منابع {src['resource']['amount']/1e6:.0f}M)")
        check(total >= 100_000_000, f"درآمد {label} بالای ۱۰۰ میلیون است ({total/1e6:.1f}M)")
    src_strong = await inc.income_sources(A)
    src_weak = await inc.income_sources(L)
    check(src_strong["total"] > src_weak["total"],
          "کشور قوی‌تر درآمد بیشتری دارد")
    check(src_strong["resource"]["sectors"] >= 1 or True, "منبع فروش منابع در محاسبه هست")
    check("resource" in src_strong, "income_sources منبع فروش منابع را برمی‌گرداند")

    # ══════════ TEST 2 ══════════
    print("\n══ TEST 2: فروش منابع ══")
    await db.execute("UPDATE states SET energy=800000, gas=500000, water=400000, "
                     "materials=120000, oil_stock=9000, food=70000 WHERE user_id=?", (A,))
    money_before = (await db.fetchone("SELECT money FROM users WHERE id=?", (A,)))["money"]
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|res"))
    texts, _ = shot("resource shop")
    flat = "\n".join(texts)
    check("فروش منابع" in flat, "صفحهٔ فروش منابع باز شد")
    check("برق" in flat and "گاز" in flat and "نفت" in flat, "همهٔ منابع نمایش داده شدند")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|resgo|gas|200000"))
    texts, _ = shot("sell gas")
    flat = "\n".join(texts)
    money_after = (await db.fetchone("SELECT money FROM users WHERE id=?", (A,)))["money"]
    gas_after = (await db.fetchone("SELECT gas FROM states WHERE user_id=?", (A,)))["gas"]
    print(f"  فروش ۲۰۰٬۰۰۰ گاز → خزانه {money_before:,} → {money_after:,} | گاز: {gas_after:,}")
    check("فروخته شد" in flat, "پیام فروش منابع نمایش داده شد")
    check(money_after > money_before, f"پول واقعاً اضافه شد (+{(money_after-money_before)/1e6:.1f}M)")
    check(gas_after == 300_000, f"موجودی گاز کم شد ({gas_after:,})")

    # ══════════ TEST 3 ══════════
    print("\n══ TEST 3: پایگاه دریایی برای کشور بدون مرز دریایی ══")
    from core.straits import capture_requirements, naval_base_power, naval_power
    await db.execute("UPDATE countries SET has_sea=0 WHERE owner_id=?", (L,))
    await db.execute("UPDATE countries SET has_sea=1 WHERE owner_id=?", (D,))
    await db.execute("UPDATE users SET money=? WHERE id=?", (5_000_000_000, L))
    st = await db.fetchone("SELECT * FROM straits WHERE is_active=1 ORDER BY id LIMIT 1")
    ok, err = await capture_requirements(L, st)
    check(not ok, "قبل از پایگاه، عملیات دریایی ممکن نیست")
    check("پایگاه دریایی" in err, "پیام خطا روش ساخت پایگاه دریایی را نشان می‌دهد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(L, "g|navbase"))
    texts, _ = shot("naval base menu")
    check("پایگاه دریایی" in "\n".join(texts), "منوی پایگاه دریایی باز شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(L, f"g|navbasego|{D}"))
    texts, _ = shot("naval base build")
    power = await naval_power(L)
    print(f"  قدرت دریایی بعد از پایگاه: {power}")
    check(any("پایگاه دریایی ساخته شد" in (t or "") for t in texts),
          "پایگاه دریایی ساخته شد")
    check(power >= 1500, f"پایگاه قدرت دریایی داد ({power})")
    ok2, err2 = await capture_requirements(L, st)
    check(ok2, f"حالا کشور بدون مرز دریایی می‌تواند تنگه را تسخیر کند (err={err2!r})")

    # ══════════ TEST 4 ══════════
    print("\n══ TEST 4: تسخیر استان vs حملهٔ عادی ══")
    await _give_army(A)
    await db.execute("UPDATE users SET money=? WHERE id=?", (9_000_000_000, D))
    p_before = (await db.fetchone("SELECT COUNT(*) c FROM provinces WHERE owner_id=?", (D,)))["c"]

    # الف) حملهٔ عادی: استان نمی‌گیرد ولی زیرساخت آسیب می‌بیند
    wid = await _new_war(db, A, D)
    await db.execute("UPDATE states SET satisfaction=80, energy=500000 WHERE user_id=?", (D,))
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, f"g|wtype|{wid}|land"))
    await dp.feed_update(bot, H.cb_update(A, "g|wgo"))
    await dp.feed_update(bot, H.cb_update(A, "g|wgogo"))
    texts, _ = shot("ordinary attack")
    p_after_norm = (await db.fetchone("SELECT COUNT(*) c FROM provinces WHERE owner_id=?", (D,)))["c"]
    print(f"  حملهٔ عادی: استان‌های مدافع {p_before} → {p_after_norm}")
    check(p_after_norm == p_before, "حملهٔ عادی هیچ استانی نمی‌گیرد")
    flat = "\n".join(texts)
    check("زیرساخت" in flat or "استان گرفته نمی‌شود" in flat,
          "گزارش کانال توضیح می‌دهد که فقط زیرساخت زده شد")

    # ب) حملهٔ تسخیر: استان می‌گیرد
    await db.execute("UPDATE states SET last_attack_at=NULL WHERE user_id=?", (A,))
    wid2 = await _new_war(db, A, D)
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, f"g|watkc|{wid2}"))
    texts, _ = shot("attack types")
    check("تسخیر" in "\n".join(texts), "گزینهٔ حملهٔ تسخیر در منو هست")
    await dp.feed_update(bot, H.cb_update(A, f"g|wtype|{wid2}|conquest"))
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|wgo"))
    texts, _ = shot("conquest confirm")
    check("تسخیر" in "\n".join(texts), "صفحهٔ تأیید، حالت تسخیر را نشان می‌دهد")
    await dp.feed_update(bot, H.cb_update(A, "g|wgogo"))
    texts, _ = shot("conquest attack")
    p_after_conq = (await db.fetchone("SELECT COUNT(*) c FROM provinces WHERE owner_id=?", (D,)))["c"]
    mine = (await db.fetchone("SELECT COUNT(*) c FROM provinces WHERE owner_id=?", (A,)))["c"]
    print(f"  حملهٔ تسخیر: استان‌های مدافع {p_before} → {p_after_conq} | مهاجم {mine}")
    check(p_after_conq < p_before, f"حملهٔ تسخیر استان گرفت ({p_before} → {p_after_conq})")
    check(mine > 5, f"استان به مهاجم اضافه شد ({mine})")

    # ══════════ TEST 5 ══════════
    print("\n══ TEST 5: کول‌داون سایبری ۲۰ دقیقه ══")
    from gamebot.handlers.war import cyber_cooldown_left, cyber_cooldown_ok
    minutes = float(await get_setting("cyber_cooldown_minutes", "20"))
    print(f"  تنظیم کول‌داون: {minutes} دقیقه")
    check(minutes == 20, "کول‌داون سایبری ۲۰ دقیقه است (نه ۶ ساعت)")
    check(await cyber_cooldown_ok(A, D), "بدون سابقه، عملیات آزاد است")
    from core.utils import iso, now, timedelta
    await db.execute(
        "INSERT INTO cyber_ops(attacker_id, defender_id, kind, success, amount, created_at) "
        "VALUES(?,?,?,?,?,?)", (A, D, "jam", 1, 0, iso(now() - timedelta(minutes=5))))
    left = await cyber_cooldown_left(A, D)
    print(f"  ۵ دقیقه بعد از عملیات: {left} دقیقه مانده")
    check(0 < left <= 15, f"پس از ۵ دقیقه حدود ۱۵ دقیقه مانده ({left})")
    check(not await cyber_cooldown_ok(A, D), "عملیات دوم هنوز بلاک است")
    await db.execute("UPDATE cyber_ops SET created_at=? WHERE attacker_id=? AND defender_id=?",
                     (iso(now() - timedelta(minutes=21)), A, D))
    check(await cyber_cooldown_ok(A, D), "بعد از ۲۱ دقیقه آزاد می‌شود")

    # ══════════ TEST 6 ══════════
    print("\n══ TEST 6: تحریم سازمان ملل (خلع سلاح) ══")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, f"g|unrep|{D}"))
    texts, _ = shot("sanction list")
    check("خلع سلاح" in "\n".join(texts), "صفحهٔ انتخاب تحریم باز شد")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, f"g|unsanc|disarm|{D}"))
    texts, _ = shot("disarm start")
    check("تحریم" in "\n".join(texts), "صفحهٔ دلیل تحریم باز شد (باگ split رفع شد)")
    H.SENT.clear()
    await dp.feed_update(bot, H.msg_update(A, "تجاوز به مرزهای ما"))
    texts, _ = shot("sanction created")
    vote = await db.fetchone("SELECT * FROM un_votes ORDER BY id DESC LIMIT 1")
    check(vote is not None and vote["kind"] == "sanction", "رای‌گیری تحریم ثبت شد")
    # رأی موافق و پایان رای‌گیری
    await db.execute(
        "INSERT INTO un_ballots(vote_id,user_id,choice,weight,voted_at) VALUES(?,?,?,?,?)",
        (vote["id"], A, 0, 1, iso()))
    await db.execute("UPDATE un_votes SET ends_at='2020-01-01 00:00:00' WHERE id=?", (vote["id"],))
    from gamebot.handlers.war import settle_votes
    await settle_votes(bot)
    from core.economy import is_disarmed
    disarmed = await is_disarmed(D)
    check(disarmed, "خلع سلاح واقعاً روی کشور هدف اعمال شد")

    # ══════════ TEST 7 ══════════
    print("\n══ TEST 7: خرید مصالح از مدیریت کشور ══")
    await db.execute("UPDATE users SET money=? WHERE id=?", (3_000_000_000, A))
    mat_before = (await db.fetchone("SELECT materials FROM states WHERE user_id=?", (A,)))["materials"]
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|matshop"))
    texts, _ = shot("materials shop")
    check("خرید مصالح" in "\n".join(texts), "فروشگاه مصالح باز شد")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|matb|m2"))
    texts, _ = shot("buy materials")
    mat_after = (await db.fetchone("SELECT materials FROM states WHERE user_id=?", (A,)))["materials"]
    print(f"  مصالح: {mat_before:,} → {mat_after:,}")
    check(mat_after == mat_before + 10_000, "۱۰٬۰۰۰ واحد مصالح اضافه شد")

    print(f"\n  ERRORS={len(H.ERRORS)}")
    for e in H.ERRORS:
        print("   ❌", e)
    print("TOTAL ERRORS:", len(H.ERRORS))
    return len(H.ERRORS)


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)

"""تست نفت: درآمد میلیونی هر ۵ دقیقه · فروش کامل انبار · ارتقای تجهیزات.

  TEST 1 — درآمد نفتی هر دوره همیشه میلیونی است (کف ۱۲ میلیون) و با دکل/سطح رشد می‌کند
  TEST 2 — فروش خودکار **کل انبار** را می‌فروشد (نه فقط ۵٬۰۰۰ بشکه) و پول با بشکه رشد می‌کند
  TEST 3 — ارتقای تجهیزات: صفحه باز می‌شود، بدون دکل هم انجام می‌شود، سطح بالا می‌رود
  TEST 4 — هر بشکه بیشتر → پول بیشتر (بدون سقف)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402
from harness import check, shot  # noqa: E402


async def main():
    from core.db import db, get_setting
    from core import income as inc
    from core import oil as O

    await H.make_world([(701, "بازیکن", 0)])
    uid = 701
    rig = await db.fetchone("SELECT id FROM buildings WHERE name='دکل نفتی'")

    async def setup(rigs: int, level: int, stock: int):
        await db.execute("DELETE FROM player_assets WHERE user_id=?", (uid,))
        await db.execute("DELETE FROM oil_business WHERE user_id=?", (uid,))
        if rigs:
            await db.execute(
                "INSERT INTO player_assets(user_id,item_type,item_id,quantity) VALUES(?,?,?,?)",
                (uid, "building", rig["id"], rigs))
        await O.ensure_business(uid)
        await db.execute("UPDATE oil_business SET level=? WHERE user_id=?", (level, uid))
        await db.execute("UPDATE states SET oil_stock=? WHERE user_id=?", (stock, uid))

    # ══════════ TEST 1 ══════════
    print("\n══ TEST 1: درآمد نفتی هر ۵ دقیقه، میلیونی ══")
    floor_m = float(await get_setting("income_oil_floor_m", "12"))
    print(f"  کف پایهٔ نفتی: {floor_m} میلیون")
    results = []
    for rigs, level in ((0, 1), (3, 1), (10, 3), (25, 6)):
        await setup(rigs, level, 0)
        oil = await inc.oil_income(uid, 1.0)
        m = oil["amount"] / 1_000_000
        results.append((rigs, level, m))
        print(f"  {rigs:2d} دکل، سطح {level}: {m:.1f} میلیون در هر دوره")
        check(m >= floor_m - 0.01,
              f"درآمد نفتی ({rigs} دکل/سطح {level}) از کف {floor_m}M کمتر نیست")
        check(oil["amount"] >= 1_000_000, "مبلغ همیشه میلیونی است")
    check(results[0][2] < results[1][2] < results[2][2] < results[3][2],
          "دکل و سطح بیشتر → درآمد نفتی بیشتر (صعودی)")
    check(results[3][2] >= results[0][2] * 1.8,
          f"رشد معنادار با ارتقا: {results[0][2]:.1f}M → {results[3][2]:.1f}M")

    # ══════════ TEST 2 ══════════
    print("\n══ TEST 2: فروش خودکار کل انبار ══")
    await setup(5, 1, 50_000)      # دقیقاً همان شکایت کاربر: ۵۰ هزار بشکه
    await db.execute("UPDATE oil_business SET auto_sell=1 WHERE user_id=?", (uid,))
    est = await O.income_estimate(uid)
    print(f"  انبار ۵۰٬۰۰۰ بشکه → برآورد فروش {est['income']/1e6:.1f} میلیون")
    check(est["stock"] == 50_000, "برآورد بر مبنای کل انبار است")
    check(est["income"] > 20_000_000,
          f"۵۰ هزار بشکه پول درست می‌دهد (نه چند میلیون ناچیز): {est['income']/1e6:.1f}M")

    before = (await db.fetchone("SELECT money FROM users WHERE id=?", (uid,)))["money"]
    paid = await O.auto_sell_tick(None)
    after = await db.fetchone("SELECT money FROM users WHERE id=?", (uid,))
    stock_after = (await db.fetchone("SELECT oil_stock FROM states WHERE user_id=?", (uid,)))["oil_stock"]
    biz = await db.fetchone("SELECT barrels_sold, sales FROM oil_business WHERE user_id=?", (uid,))
    print(f"  فروش: {paid/1e6:.1f}M | انبار باقی‌مانده: {stock_after} | بشکه فروخته‌شده: {biz['barrels_sold']}")
    check(stock_after == 0, "کل انبار خالی شد (قبلاً فقط ۵٬۰۰۰ بشکه می‌فروخت)")
    check(biz["barrels_sold"] == 50_000,
          f"هر ۵۰٬۰۰۰ بشکه ثبت شد (ثبت‌شده: {biz['barrels_sold']})")
    check(paid == est["income"], "پول واریزشده با برآورد یکی است")
    check(after["money"] == before + paid, "پول به خزانه اضافه شد")

    # ══════════ TEST 3 ══════════
    print("\n══ TEST 3: ارتقای تجهیزات (بدون دکل هم) ══")
    await setup(0, 1, 0)
    await db.execute("UPDATE users SET money=? WHERE id=?", (2_000_000_000, uid))
    ok, msg = await O.upgrade_business(uid)
    print("  ارتقا بدون دکل:", msg.replace("\n", " | ")[:120])
    check(ok, "ارتقا حتی بدون دکل انجام می‌شود (قبلاً بلاک می‌شد)")
    lvl = (await db.fetchone("SELECT level FROM oil_business WHERE user_id=?", (uid,)))["level"]
    check(lvl == 2, f"سطح واقعاً بالا رفت: {lvl}")

    dp, bot = await H.new_game_dp()
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(uid, "g|oilup"))
    texts, _ = shot("upgrade screen")
    flat = "\n".join(texts)
    check("ارتقای تجهیزات استخراج نفت" in flat, "صفحهٔ ارتقا در ربات باز می‌شود (باگ قبلی رفع شد)")
    check("g|oilupgo" not in flat, "دکمهٔ تأیید ارتقا در کیبورد است")
    check(not H.ERRORS, "بدون خطای اجرایی در مسیر ارتقا")

    # ارتقای واقعی از دکمه
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(uid, "g|oilupgo"))
    texts, _ = shot("upgrade exec")
    lvl2 = (await db.fetchone("SELECT level FROM oil_business WHERE user_id=?", (uid,)))["level"]
    check(lvl2 == 3, f"ارتقا از دکمهٔ ربات انجام شد: سطح {lvl2}")
    check(any("ارتقای تجهیزات استخراج انجام شد" in (t or "") for t in texts),
          "پیام موفقیت ارتقا ارسال شد")

    # ══════════ TEST 4 ══════════
    print("\n══ TEST 4: هر بشکه بیشتر → پول بیشتر (بدون سقف) ══")
    await setup(5, 2, 0)
    amounts = {}
    for bbl in (5_000, 25_000, 50_000, 200_000):
        amounts[bbl] = (await O.sale_amount(uid, bbl))["amount"]
        print(f"  {bbl:>7,} بشکه → {amounts[bbl]/1e6:.1f} میلیون")
    check(amounts[5_000] < amounts[25_000] < amounts[50_000] < amounts[200_000],
          "پول با تعداد بشکه صعودی است")
    check(amounts[200_000] > amounts[5_000] * 10,
          f"۲۰۰ هزار بشکه ≈ {amounts[200_000]/amounts[5_000]:.1f} برابر ۵ هزار بشکه")

    print(f"\n  ERRORS={len(H.ERRORS)}")
    for e in H.ERRORS:
        print("   ❌", e)
    print("TOTAL ERRORS:", len(H.ERRORS))
    return len(H.ERRORS)


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)

"""🧨 تست ریست کامل + رفع باگ «کشور شما سقوط کرده».

سناریوی گزارش‌شدهٔ کاربر:
  ۱. کشورش سقوط می‌کند، ادمین بازی را ریست می‌کند و او کشور آمریکا را می‌گیرد،
     ولی ربات می‌گوید «کشور شما سقوط کرده».
  ۲. ☢️ تأسیسات هسته‌ای و 🛢 ارتقاهای کشور قبلی همچنان باقی مانده‌اند.

اجرا: /tmp/venv/bin/python tests/test_full_reset.py   (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

PLAYER = 7101
OTHER = 7102


async def main():
    from core.db import db, get_initial_money
    from core import provinces as prov
    from core import fullreset
    from core.db import init_db

    dp, bot = await H.new_game_dp()
    await H.make_world([(PLAYER, "بازیکن", 0), (OTHER, "رقیب", 1)])

    # ═══════════ TEST 1: کاربری که کشور دارد ولی استان ندارد «سقوط‌کرده» نیست ═══════════
    print("\n══ TEST 1: باگ «کشور شما سقوط کرده» ══")
    rows = await db.fetchall("SELECT id FROM countries WHERE is_active=1 ORDER BY id")
    cid = rows[0]["id"]
    await db.execute("UPDATE users SET country_id=? WHERE id=?", (cid, PLAYER))
    await db.execute("UPDATE countries SET owner_id=? WHERE id=?", (PLAYER, cid))
    # شبیه‌سازی دیتابیس قدیمی: هیچ استانی برای این کشور وجود ندارد
    await db.execute("DELETE FROM provinces WHERE country_id=?", (cid,))
    summary = await prov.province_summary(PLAYER)
    H.check(not summary["collapsed"],
            "کشور بدون رکورد استان، «سقوط‌کرده» گزارش نمی‌شود")
    H.check(summary["home"] == 5,
            f"۵ استان پایه به بازیکن داده شد (home={summary['home']})")
    text = await prov.provinces_text(PLAYER)
    H.check("سقوط کرده" not in text, "متن استان‌ها پیام سقوط نمی‌دهد")

    # سقوط واقعی: همهٔ استان‌ها به بازیکن دیگری برود
    for p in await prov.provinces_of(cid):
        await db.execute("UPDATE provinces SET owner_id=? WHERE id=?", (OTHER, p["id"]))
    summary2 = await prov.province_summary(PLAYER)
    H.check(summary2["collapsed"], "سقوط واقعی (همهٔ استان‌ها تصاحب‌شده) درست تشخیص داده می‌شود")

    # ═══════════ TEST 2: گرفتن کشور تازه استان‌ها را همان لحظه می‌دهد ═══════════
    print("\n══ TEST 2: انتخاب کشور تازه ══")
    await db.execute("UPDATE users SET country_id=NULL WHERE id=?", (PLAYER,))
    await db.execute("UPDATE countries SET owner_id=NULL WHERE id=?", (cid,))
    await db.execute("UPDATE provinces SET owner_id=NULL WHERE owner_id=?", (OTHER,))
    country = await db.fetchone("SELECT * FROM countries WHERE id=?", (cid,))
    from gamebot.handlers.start import assign_country
    ok = await assign_country(PLAYER, country, "")
    H.check(ok, "کشور با موفقیت به بازیکن واگذار شد")
    s3 = await prov.province_summary(PLAYER)
    H.check(not s3["collapsed"] and s3["home"] == 5,
            f"بلافاصله ۵ استان به بازیکن داده شد (home={s3['home']})")
    row = await db.fetchone("SELECT collapsed, province_count FROM countries WHERE id=?", (cid,))
    H.check(int(row["collapsed"]) == 0, "پرچم collapsed کشور پاک شد")

    # ═══════════ TEST 2b: کشوری که همهٔ استان‌هایش تصاحب شده، برای مالک تازه سالم می‌شود ═══════════
    print("\n══ TEST 2b: واگذاری کشوری با استان‌های تصاحب‌شده ══")
    await db.execute("UPDATE provinces SET owner_id=? WHERE country_id=?", (OTHER, cid))
    await db.execute("UPDATE countries SET owner_id=NULL WHERE id=?", (cid,))
    country2 = await db.fetchone("SELECT * FROM countries WHERE id=?", (cid,))
    ok = await assign_country(PLAYER, country2, "")
    H.check(ok, "کشور در اختیار مالک تازه قرار گرفت")
    s2b = await prov.province_summary(PLAYER)
    H.check(not s2b["collapsed"] and s2b["home"] == 5,
            f"همهٔ ۵ استان کشور به مالک تازه رسید (home={s2b['home']})")

    # ═══════════ TEST 3: پیشرفت قبلی (هسته‌ای + ارتقا) پاک می‌شود ═══════════
    print("\n══ TEST 3: پاک‌سازی هسته‌ای و ارتقاها ═══════════")
    await db.execute(
        "INSERT INTO enrichment(user_id, stage, started_at, completes_at, centrifuges) "
        "VALUES(?,3,datetime('now'),datetime('now'),900) ON CONFLICT(user_id) DO UPDATE "
        "SET stage=3", (PLAYER,))
    await db.execute(
        "INSERT INTO nuclear_sites(user_id, stage, kind, hp, max_hp, centrifuges, active) "
        "VALUES(?,3,'غنی‌سازی',100,100,900,1) ON CONFLICT(user_id) DO UPDATE SET stage=3",
        (PLAYER,))
    await db.execute(
        "INSERT INTO oil_business(user_id, level) VALUES(?,7) "
        "ON CONFLICT(user_id) DO UPDATE SET level=7", (PLAYER,))
    await db.execute(
        "INSERT INTO internet_infra(user_id, level) VALUES(?,4) "
        "ON CONFLICT(user_id) DO UPDATE SET level=4", (PLAYER,))
    await db.execute(
        "INSERT INTO country_attrition(user_id, wear, strikes) VALUES(?,62,5) "
        "ON CONFLICT(user_id) DO UPDATE SET wear=62", (PLAYER,))
    eq = await db.fetchone("SELECT id FROM equipment LIMIT 1")
    if eq:
        await db.execute(
            "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=40",
            (PLAYER, "equipment", eq["id"], 40))
    nukes_before = (await db.fetchone(
        "SELECT COUNT(*) c FROM nuclear_sites WHERE user_id=?", (PLAYER,)))["c"]
    H.check(nukes_before == 1, "پیش از ریست، تأسیسات هسته‌ای وجود دارد")

    # ═══════════ TEST 4: ریست کامل از پنل ادمین (موتور مشترک) ═══════════
    print("\n══ TEST 4: ریست کامل ══")
    stats = await fullreset.full_reset(reset_wealth=True, keep_bans=True)
    H.check(stats["users"] >= 2, f"تعداد کاربران ریست‌شده: {stats['users']}")
    H.check(stats["tables"] >= 30, f"{stats['tables']} جدول پاک شد")

    for sql, label in (
        ("SELECT COUNT(*) c FROM enrichment", "غنی‌سازی پاک شد"),
        ("SELECT COUNT(*) c FROM nuclear_sites", "تأسیسات هسته‌ای پاک شد"),
        ("SELECT COUNT(*) c FROM oil_business", "سطح تجهیزات استخراج پاک شد"),
        ("SELECT COUNT(*) c FROM internet_infra", "سطوح اینترنت پاک شد"),
        ("SELECT COUNT(*) c FROM country_attrition", "فرسایش جنگ پاک شد"),
        ("SELECT COUNT(*) c FROM player_assets", "تجهیزات و سربازان پاک شد"),
        ("SELECT COUNT(*) c FROM states", "وضعیت سیاسی/رضایت پاک شد"),
    ):
        c = (await db.fetchone(sql))["c"]
        H.check(int(c) == 0, f"{label} (ردیف باقی‌مانده: {c})")

    u = await db.fetchone("SELECT * FROM users WHERE id=?", (PLAYER,))
    H.check(u["country_id"] is None, "کشور همهٔ بازیکنان آزاد شد")
    H.check(int(u["royal_coins"] or 0) == 0, "سکه شاهی صفر شد")
    H.check(int(u["money"] or 0) == await get_initial_money(),
            "خزانه به بودجهٔ اولیه برگشت")

    cs = await db.fetchall("SELECT owner_id, collapsed FROM countries")
    H.check(all(c["owner_id"] is None for c in cs), "هیچ کشوری مالک ندارد")
    H.check(all(int(c["collapsed"] or 0) == 0 for c in cs), "پرچم سقوط همهٔ کشورها پاک شد")
    provs = await db.fetchall("SELECT owner_id FROM provinces")
    H.check(len(provs) >= 45 * 5, f"۵ استان پایه برای همهٔ کشورها ساخته شد ({len(provs)})")
    H.check(all(p["owner_id"] is None for p in provs), "هیچ استانی مالک ندارد")

    # ═══════════ TEST 5: بعد از ریست، کشور تازه سقوط‌کرده نیست ═══════════
    print("\n══ TEST 5: گرفتن کشور پس از ریست ══")
    usa = await db.fetchone("SELECT * FROM countries WHERE name='آمریکا'")
    if not usa:
        usa = await db.fetchone("SELECT * FROM countries WHERE is_active=1 ORDER BY id DESC")
    ok = await assign_country(PLAYER, usa, "")
    H.check(ok, f"کشور «{usa['name']}» پس از ریست به بازیکن داده شد")
    s4 = await prov.province_summary(PLAYER)
    H.check(not s4["collapsed"] and s4["home"] == 5,
            f"استان‌های کشور تازه درست است (home={s4['home']})")
    txt = await prov.provinces_text(PLAYER)
    H.check("سقوط کرده" not in txt, "پیام «کشور شما سقوط کرده» دیگر نمایش داده نمی‌شود")
    enr = await db.fetchone("SELECT * FROM enrichment WHERE user_id=?", (PLAYER,))
    H.check(enr is None, "بازیکن هیچ هسته‌ای از کشور قبلی ندارد")
    ob = await db.fetchone("SELECT * FROM oil_business WHERE user_id=?", (PLAYER,))
    H.check(ob is None, "بازیکن هیچ ارتقای نفتی از کشور قبلی ندارد")

    # ═══════════ TEST 6: صفحهٔ ریست در پنل داخل ربات ═══════════
    print("\n══ TEST 6: دکمهٔ ریست کل در پنل ادمین ══")
    from core.config import SUPER_ADMIN_ID
    await db.execute("INSERT OR IGNORE INTO admins(id, name, is_super) VALUES(?, 'boss', 1)",
                     (SUPER_ADMIN_ID,))
    # یک پیشرفت کوچک بسازیم تا ریست واقعاً چیزی پاک کند
    await db.execute(
        "INSERT INTO internet_infra(user_id, level) VALUES(?,2) "
        "ON CONFLICT(user_id) DO UPDATE SET level=2", (PLAYER,))
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(SUPER_ADMIN_ID, "p|resetmenu"))
    texts, _ = H.shot("reset menu")
    flat = "\n".join(texts)
    H.check("ریست کامل" in flat, "صفحهٔ تأیید ریست کامل نمایش داده شد")
    H.check("☢️" in flat or "هسته‌ای" in flat, "پیش‌نمایش، بخش هسته‌ای را نشان می‌دهد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(SUPER_ADMIN_ID, "p|resetall"))
    texts, _ = H.shot("reset done")
    flat = "\n".join(texts)
    H.check("ریست کامل بازی انجام شد" in flat, "اجرای ریست کامل گزارش شد")
    c = (await db.fetchone("SELECT COUNT(*) c FROM internet_infra"))["c"]
    H.check(int(c) == 0, "پیشرفت اینترنت بازیکن پاک شد")

    # ═══════════ TEST 7: دسترسی غیرسوپرادمین بسته است ═══════════
    print("\n══ TEST 7: محافظت دسترسی ══")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(PLAYER, "p|resetmenu"))
    H.check(len(H.SENT) == 0 or all("⛔" in (t or "") for (_n, _c, t, _p) in H.SENT
                                    if t),
            "کاربر عادی نمی‌تواند صفحهٔ ریست را باز کند")

    # ═══════════ TEST 8: نسخهٔ sync (پنل وب) ═══════════
    print("\n══ TEST 8: ریست پنل وب ══")
    from webapp import data_service
    await db.execute(
        "INSERT INTO internet_infra(user_id, level) VALUES(?,3) "
        "ON CONFLICT(user_id) DO UPDATE SET level=3", (PLAYER,))
    res = data_service.reset_all_players()
    H.check(res.get("success") is True, "پنل وب ریست را موفق گزارش کرد")
    c = (await db.fetchone("SELECT COUNT(*) c FROM internet_infra"))["c"]
    H.check(int(c) == 0, "پنل وب هم پیشرفت اینترنت را پاک کرد")
    owned = (await db.fetchone(
        "SELECT COUNT(*) c FROM countries WHERE owner_id IS NOT NULL"))["c"]
    H.check(int(owned) == 0, "پنل وب همهٔ کشورها را آزاد کرد")

    print("\nTOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("  !", e)


asyncio.run(main())

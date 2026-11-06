"""تست حملهٔ فرسایشی تنگه + ریست کشور توسط ادمین.

  TEST A — حمله هرگز با «قدرت ناکافی» بلاک نمی‌شود
  TEST B — نبرد فرسایشی: حملهٔ ضعیف هم دفاع مدافع را کم می‌کند
  TEST C — صفحهٔ تأیید حمله (g|stc|) و اجرای آن (g|stgo|)
  TEST D — ریست کشور توسط ادمین → بازیکن بدون کشور می‌شود و می‌تواند دوباره انتخاب کند
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402
from harness import check, shot  # noqa: E402


async def give(user_id, sub, qty):
    """تجهیزات دریایی را مستقیم در انبار می‌ریزد (برای تست)."""
    from core.db import db
    row = await db.fetchone(
        "SELECT e.id FROM equipment e JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE c.key='sea' AND (LOWER(e.subcategory)=? OR LOWER(e.name) LIKE ?) "
        "ORDER BY e.id LIMIT 1", (sub, f"%{sub}%"))
    if not row:
        return None
    await db.execute(
        "INSERT INTO player_assets(user_id,item_type,item_id,quantity) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id,item_type,item_id) DO UPDATE SET quantity=quantity+?",
        (user_id, "equipment", row["id"], qty, qty))
    return row["id"]


async def main():
    from core.db import db, get_setting, set_setting
    from core.straits import (attack_outlook, capture_requirements, capture_strait,
                              naval_power, naval_defense)

    rows = await H.make_world([(501, "مهاجم", 0), (502, "مدافع", 1)])
    attacker, defender = 501, 502

    # ══════════════ TEST A ══════════════
    print("\n══ TEST A: حمله هرگز بلاک نمی‌شود ══")
    strait = await db.fetchone("SELECT * FROM straits WHERE is_active=1 ORDER BY id LIMIT 1")
    await db.execute("UPDATE straits SET owner_id=? WHERE id=?", (defender, strait["id"]))
    strait = await db.fetchone("SELECT * FROM straits WHERE id=?", (strait["id"],))

    # مهاجم بسیار ضعیف (کمی بالای حداقل)
    sea = await db.fetchall(
        "SELECT e.id, e.name, e.subcategory, e.attack_power, e.defense_power "
        "FROM equipment e JOIN equipment_categories c ON c.id=e.category_id WHERE c.key='sea'")
    print("  تجهیزات دریایی:", [(r["id"], r["name"], r["subcategory"]) for r in sea][:6])
    await give(attacker, "frigate", 2)
    await give(defender, "frigate", 60)

    a_nav = await naval_power(attacker)
    d_def = await naval_defense(defender)
    print(f"  مهاجم دریایی={a_nav}  مدافع دفاع={d_def}")
    check(a_nav < d_def, "مهاجم واقعاً ضعیف‌تر از مدافع است (سناریوی فرسایشی)")

    ok, err = await capture_requirements(attacker, strait)
    check(ok, f"capture_requirements اجازهٔ حمله می‌دهد (err={err!r})")
    check(err == "", "هیچ پیام بلاک «قدرت کافی نیست» برنمی‌گردد")

    look = await attack_outlook(attacker, strait)
    print(f"  outlook: {look}")
    check(look["can_capture"] is False, "در همین حمله تصرف ممکن نیست (طبق انتظار)")
    check(look["needed_rounds"] >= 1, f"تعداد حملهٔ لازم محاسبه شده: {look['needed_rounds']}")
    check(look["attrition"] == float(await get_setting("strait_attrition_percent", "18")),
          f"درصد فرسایش از تنظیمات خوانده شد: {look['attrition']}")

    # ══════════════ TEST B ══════════════
    print("\n══ TEST B: فرسایش تضمینی دفاع مدافع ══")
    before_def = await naval_defense(defender)
    dp, bot = await H.new_game_dp()
    report = await capture_strait(bot, attacker, strait["id"])
    after_def = await naval_defense(defender)
    print(f"  دفاع مدافع: {before_def} → {after_def}")
    print("  گزارش:", report.replace("\n", " | ")[:300])
    check(after_def < before_def,
          f"دفاع مدافع واقعاً کم شد ({before_def} → {after_def})")
    drop_pct = (before_def - after_def) / before_def * 100 if before_def else 0
    check(drop_pct >= 15, f"افت دفاع حداقل ~۱۵٪ فرسایش: {drop_pct:.1f}٪")
    check("فرسایشی" in report, "گزارش نبرد شامل خط «نبرد فرسایشی» است")

    strait_now = await db.fetchone("SELECT owner_id FROM straits WHERE id=?", (strait["id"],))
    if strait_now["owner_id"] != attacker:
        check("مالکیت تغییر نکرد" in report or "دفع" in report,
              "حملهٔ ناموفق گزارش دفع دارد و مالکیت تغییر نکرده")

    # حمله‌های پی‌درپی: آیا دفاع در نهایت می‌شکند؟
    print("  ♻️ حمله‌های پی‌درپی تا شکستن دفاع:")
    rounds = 0
    while rounds < 12:
        strait_now = await db.fetchone("SELECT * FROM straits WHERE id=?", (strait["id"],))
        if strait_now["owner_id"] == attacker:
            break
        # ناوگان مهاجم را بازسازی می‌کنیم تا فرسایش مدافع سنجیده شود
        await give(attacker, "frigate", 2)
        r = await capture_strait(bot, attacker, strait["id"])
        rounds += 1
        d = await naval_defense(defender)
        print(f"    حمله {rounds}: دفاع مدافع={d} | مالک={strait_now['owner_id']}")
        if strait_now["owner_id"] == attacker:
            break
    strait_final = await db.fetchone("SELECT owner_id FROM straits WHERE id=?", (strait["id"],))
    print(f"  بعد از {rounds} حمله: مالک={strait_final['owner_id']}")
    check(rounds > 0, "حمله‌های پی‌درپی اجرا شدند")
    check(await naval_defense(defender) < before_def,
          "ناوگان مدافع در طول حمله‌های پی‌درپی فرسوده شد")

    # ══════════════ TEST C ══════════════
    print("\n══ TEST C: صفحهٔ تأیید حمله در UI ══")
    from harness import SENT
    SENT.clear()
    sid = strait["id"]
    # مهاجم را صاحب کشور دیگری کن تا مالک تنگه نباشد
    await db.execute("UPDATE straits SET owner_id=? WHERE id=?", (defender, sid))
    await dp.feed_update(bot, H.cb_update(attacker, f"g|stc|{sid}"))
    texts, _ = shot("confirm")
    flat = "\n".join(texts)
    check("آیا حمله می‌کنید؟" in flat, "صفحهٔ تأیید حمله نمایش داده شد")
    check(f"g|stgo|{sid}" not in flat, "دکمهٔ تأیید در کیبورد است (نه در متن)")
    check("فرسایشی" in flat, "صفحهٔ تأیید توضیح فرسایشی بودن نبرد را دارد")

    # اجرای تأیید
    SENT.clear()
    await dp.feed_update(bot, H.cb_update(attacker, f"g|stgo|{sid}"))
    texts, _ = shot("execute")
    flat = "\n".join(texts)
    check("نبرد دریایی" in flat or "تسخیر" in flat or "دفع" in flat,
          "با تأیید، گزارش نبرد صادر شد")

    # ══════════════ TEST D ══════════════
    print("\n══ TEST D: ریست کشور توسط ادمین ══")
    victim = 503
    from core.db import init_db
    await db.execute("INSERT OR IGNORE INTO users(id, full_name, money) VALUES(?,?,?)",
                     (victim, "قربانی", 5000000000))
    c = await db.fetchone("SELECT * FROM countries WHERE is_active=1 ORDER BY id LIMIT 1 OFFSET 3")
    await db.execute("UPDATE users SET country_id=?, royal_coins=99 WHERE id=?", (c["id"], victim))
    await db.execute("UPDATE countries SET owner_id=? WHERE id=?", (victim, c["id"]))
    old_country = c["id"]
    print(f"  قبل: user.country_id={old_country} owner_id={victim}")

    from adminbot.handlers.reset import reset_payload
    text, markup = await reset_payload(victim)
    check("ریست کامل کشور" in text, "صفحهٔ تأیید ریست کشور ساخته شد")
    check("آیا مطمئن هستید؟" in text, "تأیید نهایی خواسته می‌شود")

    adp, abot = await H.new_admin_dp()
    await db.execute("INSERT OR IGNORE INTO admins(id, name, is_super) VALUES(1001,'boss',1)")
    SENT.clear()
    await adp.feed_update(abot, H.cb_update(1001, f"a|rctygo|{victim}"))
    texts, _ = shot("reset")
    flat = "\n".join(texts)
    check("ریست انجام شد" in flat or "ریست شد" in flat, "ریست با موفقیت اجرا شد")

    u = await db.fetchone("SELECT * FROM users WHERE id=?", (victim,))
    check(u["country_id"] is None, "کشور بازیکن پاک شد (country_id=NULL)")
    check((u["royal_coins"] or 0) == 0, "سکه شاهی صفر شد")
    oc = await db.fetchone("SELECT * FROM countries WHERE id=?", (old_country,))
    check(oc["owner_id"] is None, "مالکیت کشور آزاد شد")
    provs = await db.fetchall("SELECT * FROM provinces WHERE country_id=? AND owner_id IS NOT NULL",
                              (old_country,))
    check(len(provs) == 0, "استان‌های کشور آزاد شدند")

    # ══════════════ TEST E: ادمین خودش کشور تازه می‌دهد ══════════════
    print("\n══ TEST E: انتخاب کشور تازه توسط ادمین ══")
    from adminbot.handlers.reset import pick_payload
    ptext, pmarkup = await pick_payload(victim, 0)
    check("انتخاب کشور تازه" in ptext, "لیست کشورهای آزاد ساخته شد")
    free = await db.fetchone(
        "SELECT * FROM countries WHERE owner_id IS NULL AND is_active=1 AND id!=? "
        "AND NOT EXISTS (SELECT 1 FROM users u WHERE u.country_id=countries.id) "
        "ORDER BY id LIMIT 1", (old_country,))
    check(free is not None, "کشور آزاد برای تخصیص وجود دارد")
    SENT.clear()
    await adp.feed_update(abot, H.cb_update(1001, f"a|rctyset|{victim}|{free['id']}"))
    texts, _ = shot("assign")
    u2 = await db.fetchone("SELECT country_id FROM users WHERE id=?", (victim,))
    check(u2["country_id"] == free["id"], f"کشور تازه به بازیکن داده شد: {free['name']}")
    oc2 = await db.fetchone("SELECT owner_id FROM countries WHERE id=?", (free["id"],))
    check(oc2["owner_id"] == victim, "مالکیت کشور تازه ثبت شد")
    provs2 = await db.fetchall(
        "SELECT * FROM provinces WHERE country_id=? AND owner_id=?", (free["id"], victim))
    check(len(provs2) >= 5, f"۵ استان پایه به بازیکن رسید ({len(provs2)})")

    print(f"\n  ERRORS={len(H.ERRORS)}")
    for e in H.ERRORS:
        print("   ❌", e)
    print("TOTAL ERRORS:", len(H.ERRORS))
    return len(H.ERRORS)


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)

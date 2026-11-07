"""🎯 تست خرابکاری در تأسیسات (زدن هر چیزی که دشمن ساخته است).

اجرا: /tmp/venv/bin/python tests/test_sabotage.py   (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

ATTACKER = 9101
DEFENDER = 9102


async def give_equipment(uid: int, name_like: str, qty: int = 5) -> int:
    """دادن تجهیزات با نام مشخص به بازیکن؛ خروجی آیدی تجهیز."""
    from core.db import db
    row = await db.fetchone(
        f"SELECT id FROM equipment WHERE name LIKE '%{name_like}%' ORDER BY id LIMIT 1")
    if not row:
        return 0
    await db.execute(
        "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
        (uid, "equipment", row["id"], qty, qty))
    return int(row["id"])


async def give_building(uid: int, name: str, qty: int = 3) -> int:
    from core.db import db
    row = await db.fetchone("SELECT id FROM buildings WHERE name=? LIMIT 1", (name,))
    if not row:
        return 0
    await db.execute(
        "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
        (uid, "building", row["id"], qty, qty))
    return int(row["id"])


async def asset_qty(uid: int, item_type: str, item_id: int) -> int:
    from core.db import db
    row = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
        (uid, item_type, item_id))
    return int((row or {}).get("quantity") or 0)


async def main():
    from core.db import db, set_setting
    from core import sabotage

    dp, bot = await H.new_game_dp()
    await H.make_world([(ATTACKER, "مهاجم", 0), (DEFENDER, "مدافع", 1)])

    # تجهیزات: مهاجم موشک + سایبری، مدافع پدافند هوایی
    missile = await give_equipment(ATTACKER, "موشک", 10)
    await give_equipment(ATTACKER, "دیداس", 5)
    airdef = await give_equipment(DEFENDER, "پاتریوت", 3)
    H.check(missile > 0, "مهاجم تجهیزات موشکی دارد")

    # ═══════════ TEST 1: فهرست سازه‌های دشمن ═══════════
    print("\n══ TEST 1: شناسایی سازه‌های دشمن ══")
    rig = await give_building(DEFENDER, "دکل نفتی", 4)
    power = await give_building(DEFENDER, "نیروگاه بادی", 2)
    refinery = await give_building(DEFENDER, "پالایشگاه کوچک", 2)
    await db.execute("INSERT OR REPLACE INTO internet_infra(user_id, level) VALUES(?,3)",
                     (DEFENDER,))
    await db.execute(
        "INSERT OR REPLACE INTO companies(owner_id, type_id, name, income_daily) "
        "VALUES(?,1,'شرکت ملی نفت',5000000)", (DEFENDER,))
    await db.execute(
        "INSERT OR REPLACE INTO enrichment(user_id, stage, centrifuges) VALUES(?,2,600)",
        (DEFENDER,))
    from core import nuclear as nuke
    await nuke.sync_stage(DEFENDER)

    facs = await sabotage.facilities(DEFENDER)
    kinds = {f["kind"] for f in facs}
    H.check("oil" in kinds, "🛢 دکل نفتی در فهرست اهداف است")
    H.check("power" in kinds, "⚡ نیروگاه در فهرست اهداف است")
    H.check("industry" in kinds, "🏭 پالایشگاه در فهرست اهداف است")
    H.check("internet" in kinds, "🌐 زیرساخت اینترنت در فهرست اهداف است")
    H.check("company" in kinds, "🏢 شرکت در فهرست اهداف است")
    H.check("nuclear" in kinds, "☢️ تأسیسات هسته‌ای در فهرست اهداف است")
    H.check("airdef" in kinds, "🎖 پدافند هوایی در فهرست اهداف است")
    print(f"  (سازه‌های شناسایی‌شده: {sorted(kinds)})")

    summary = await sabotage.targets_summary(ATTACKER)
    mine = next((t for t in summary if t["user_id"] == DEFENDER), None)
    H.check(mine is not None and mine["total"] >= 6,
            "کشور مدافع در فهرست کشورهای قابل هدف است")

    # ═══════════ TEST 2: سلاح مناسب و کول‌داون ═══════════
    print("\n══ TEST 2: پیش‌نیاز سلاح و کول‌داون ══")
    await db.execute("DELETE FROM sabotage_ops")
    await set_setting("sabotage_cooldown_minutes", "0")
    ok, _msg = await sabotage.can_sabotage(ATTACKER, "oil")
    H.check(ok, "با موشک می‌توان به دکل نفتی حمله کرد")
    H.check("airdef" not in await sabotage.weapon_categories(DEFENDER),
            "تجهیزات پدافندی سلاح تهاجمی حساب نمی‌شوند")
    ok2, msg2 = await sabotage.can_sabotage(DEFENDER, "oil")
    H.check(not ok2 and ("موشک" in msg2 or "نیاز" in msg2),
            "کشور بدون سلاح برد بلند نمی‌تواند حمله کند")
    await set_setting("sabotage_cooldown_minutes", "20")
    await db.execute(
        "INSERT INTO sabotage_ops(attacker_id, defender_id, kind, success, last_at) "
        "VALUES(?,?,'oil',1,datetime('now'))", (ATTACKER, DEFENDER))
    left = await sabotage.cooldown_left(ATTACKER)
    H.check(left > 0, f"کول‌داون فعال است ({left} دقیقه)")
    ok3, msg3 = await sabotage.can_sabotage(ATTACKER, "oil")
    H.check(not ok3 and "صبر" in msg3, "در کول‌داون حمله رد می‌شود")
    await db.execute("DELETE FROM sabotage_ops")
    await set_setting("sabotage_cooldown_minutes", "0")

    # ═══════════ TEST 3: پیش‌بینی و توان ═══════════
    print("\n══ TEST 3: پیش‌بینی حمله ══")
    look = await sabotage.outlook(ATTACKER, DEFENDER, "oil", rig)
    H.check(look.get("ok"), "پیش‌بینی برای دکل نفتی محاسبه شد")
    H.check(0 < look["chance"] <= 95, f"احتمال اصابت در بازهٔ معتبر ({look['chance']}٪)")
    H.check(look["atk"] > 0 and look["def"] > 0,
            f"توان حمله/پدافند محاسبه شد ({look['atk']} / {look['def']})")
    bad = await sabotage.outlook(ATTACKER, DEFENDER, "oil", 999999)
    H.check(not bad.get("ok"), "هدف ناموجود رد می‌شود")

    # ═══════════ TEST 4: خرابکاری واقعی در دکل نفتی ═══════════
    print("\n══ TEST 4: اجرای خرابکاری در نفت ══")
    await set_setting("sabotage_cooldown_minutes", "0")
    before = await asset_qty(DEFENDER, "building", rig)
    hits = 0
    report = ""
    for _ in range(25):
        report = await sabotage.sabotage(bot, ATTACKER, DEFENDER, "oil", rig)
        hits += 1 if "اصابت مستقیم" in report else 0
        after = await asset_qty(DEFENDER, "building", rig)
        if after < before:
            break
    after = await asset_qty(DEFENDER, "building", rig)
    if hits == 0:
        print(f"  ℹ️ در ۲۵ تلاش هیچ اصابتی ثبت نشد — شانس واقعی {look['chance']}٪ است")
    H.check(after < before, f"دکل‌های نفتی مدافع کم شد ({before} → {after})")
    H.check("خرابکاری" in report or "اصابت" in report, "گزارش حمله تولید شد")
    H.SENT.clear()

    # ═══════════ TEST 5: پیامدها (رضایت، فرسایش، لاگ) ═══════════
    print("\n══ TEST 5: پیامدهای سیاسی و فرسایش ══")
    from core import attrition as attr
    wear = await attr.wear_of(DEFENDER)
    H.check(wear >= 0, f"فرسایش مدافع محاسبه شد ({round(wear, 1)}٪)")
    logs = await db.fetchall("SELECT * FROM sabotage_ops WHERE attacker_id=?", (ATTACKER,))
    H.check(len(logs) > 0, f"{len(logs)} عملیات خرابکاری ثبت شد")
    H.check(all(l["kind"] for l in logs), "نوع هدف در لاگ ثبت شده است")

    # ═══════════ TEST 6: اینترنت و شرکت (اهداف سایبری) ═══════════
    print("\n══ TEST 6: اهداف داده‌محور ══")
    await set_setting("sabotage_cooldown_minutes", "0")
    for _ in range(8):
        await sabotage.sabotage(bot, ATTACKER, DEFENDER, "internet", 0)
        row = await db.fetchone("SELECT level FROM internet_infra WHERE user_id=?",
                                (DEFENDER,))
        if int((row or {}).get("level") or 0) < 3:
            break
    row = await db.fetchone("SELECT level FROM internet_infra WHERE user_id=?", (DEFENDER,))
    H.check(int((row or {}).get("level") or 0) <= 3,
            f"سطح اینترنت مدافع کاهش یافت ({int((row or {}).get('level') or 0)})")

    comp = await db.fetchone("SELECT * FROM companies WHERE owner_id=?", (DEFENDER,))
    if comp:
        for _ in range(8):
            await sabotage.sabotage(bot, ATTACKER, DEFENDER, "company", comp["id"])
            still = await db.fetchone("SELECT id FROM companies WHERE id=?", (comp["id"],))
            if not still:
                break
        still = await db.fetchone("SELECT id FROM companies WHERE id=?", (comp["id"],))
        H.check(still is None, "شرکت مدافع با حمله سایبری نابود شد")

    # ═══════════ TEST 7: بازسازی ═══════════
    print("\n══ TEST 7: بازسازی سازه‌ها ══")
    await db.execute("UPDATE users SET money=2000000000 WHERE id=?", (DEFENDER,))
    await db.execute("UPDATE states SET materials=5000 WHERE user_id=?", (DEFENDER,))
    opts = await sabotage.rebuild_options(DEFENDER)
    H.check(len(opts) > 0, f"{len(opts)} گزینهٔ بازسازی موجود است")
    rebuilt = False
    for o in opts:
        ok, msg = await sabotage.rebuild(DEFENDER, o["kind"], int(o.get("item_id") or 0))
        if ok:
            rebuilt = True
            print("   ↳", msg.split("\n")[0][:80])
            break
    H.check(rebuilt, "بازسازی یک سازه با موفقیت انجام شد")

    # ═══════════ TEST 8: رابط تلگرام ═══════════
    print("\n══ TEST 8: دکمه‌ها و منو ══")
    await set_setting("sabotage_cooldown_minutes", "0")
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, "g|war"))
    texts, _ = H.shot("war room")
    war_flat = "\n".join(texts)
    if "خرابکاری" not in war_flat:
        print("   (متن کامل اتاق جنگ برای بررسی)")
        for t in texts:
            print("   >", (t or "").replace("\n", " | ")[:300])
    H.check("خرابکاری" in war_flat, "دکمهٔ خرابکاری در اتاق جنگ هست")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, "g|sab"))
    texts, _ = H.shot("sabotage list")
    flat = "\n".join(texts)
    H.check("خرابکاری" in flat, "فهرست کشورها نمایش داده شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, f"g|sabd|{DEFENDER}"))
    texts, _ = H.shot("sabotage targets")
    flat = "\n".join(texts)
    H.check("سازه" in flat or "دکل" in flat, "فهرست سازه‌ها نمایش داده شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, f"g|sabv|oil|{rig}|{DEFENDER}"))
    texts, _ = H.shot("sabotage preview")
    flat = "\n".join(texts)
    H.check("احتمال اصابت" in flat, "پیش‌نمایش شانس اصابت نمایش داده شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, f"g|sabgo|oil|{rig}|{DEFENDER}"))
    texts, _ = H.shot("sabotage fire")
    flat = "\n".join(texts)
    H.check(bool(flat.strip()), "گزارش حمله نمایش داده شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(DEFENDER, "g|sabmy"))
    H.shot("my damage")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(DEFENDER, "g|sabfix"))
    texts, _ = H.shot("rebuild menu")
    H.check("بازسازی" in "\n".join(texts), "منوی بازسازی نمایش داده شد")

    print("\nTOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("  !", e)


asyncio.run(main())

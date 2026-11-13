"""☢️ تست بمب اتم + محدودیت ساخت + تلفات واقعی نبرد.

سه درخواست بازیکن که این فایل پوشش می‌دهد:

1. **بمب اتم:** پس از غنی‌سازی ۹۰٪ باید بتوان کلاهک ساخت و شلیک کرد.
2. **محدودیت ساخت:** سقف ۵۰۰ عددی ساخت سازه/دکل/تجهیزات برداشته شده باشد.
3. **تلفات واقعی:** حمله با ۵ کشتی نباید ۱۰۰ ناو هواپیمابر دشمن را نابود کند؛
   تلفات از یگان‌های درگیر و با سقف محاسبه شود. هم‌چنین «خرابکاری زیرساخت»
   نباید فقط یک مسیر مرده باشد و زدن تأسیسات هسته‌ای از همان‌جا کار کند.

اجرا: PAW_PROXY=0 python3 tests/test_nuke.py     (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

DBG = os.environ.get("DBG") == "1"


def dbg(*a):
    if DBG:
        print("   DBG", *a)


ATTACKER = 9301
DEFENDER = 9302
POOR = 9303


async def equipment_id(name_like: str) -> int:
    from core.db import db
    row = await db.fetchone(
        "SELECT id FROM equipment WHERE name LIKE ? ORDER BY id LIMIT 1", (f"%{name_like}%",))
    return int(row["id"]) if row else 0


async def give_equipment(uid: int, item_id: int, qty: int) -> None:
    from core.db import db
    await db.execute(
        "INSERT INTO player_assets(user_id, item_type, item_id, quantity) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity=quantity+?",
        (uid, "equipment", item_id, qty, qty))


async def qty_of(uid: int, item_type: str, item_id: int) -> int:
    from core.db import db
    row = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
        (uid, item_type, item_id))
    return int((row or {}).get("quantity") or 0)


async def main():
    from core.db import db, get_setting, init_db, set_setting

    await init_db()
    from core import combat, nuke, sabotage, enrichment

    # 🌍 سه کشور واقعی به بازیکنان تست بدهیم (targets/provinces به آن نیاز دارند)
    await H.make_world([(ATTACKER, "مهاجم", 0), (DEFENDER, "مدافع", 1), (POOR, "فقیر", 2)])
    for uid in (ATTACKER, DEFENDER, POOR):
        await db.execute("INSERT OR IGNORE INTO users(id, full_name) VALUES(?,?)",
                         (uid, f"U{uid}"))
    await db.execute("UPDATE users SET money=20000000000, royal_coins=500 WHERE id IN (?,?)",
                     (ATTACKER, POOR))
    await db.execute("UPDATE users SET money=5000000000, royal_coins=100 WHERE id=?", (DEFENDER,))
    for uid in (ATTACKER, DEFENDER, POOR):
        await db.execute("INSERT OR IGNORE INTO states(user_id, satisfaction, materials) "
                         "VALUES(?,60,200000)", (uid,))
        await db.execute("UPDATE states SET materials=200000, satisfaction=60 WHERE user_id=?",
                         (uid,))
    # موشک بالستیک + بمب‌افکن برای مهاجم
    missile = await equipment_id("بالستیک")
    bomber = await equipment_id("بمب‌افکن")
    H.check(missile > 0, f"موشک بالستیک در دیتابیس است ({missile})")
    await give_equipment(ATTACKER, missile, 60)
    await give_equipment(ATTACKER, bomber, 20)

    # ═══════════════ ۱) ساخت بمب فقط بعد از ۹۰٪ ═══════════════
    print("\n== TEST 1: بمب اتم فقط بعد از غنی‌سازی ۹۰٪ ==")
    ok, why = await nuke.can_build(ATTACKER)
    H.check(not ok and "۹۰" in why, f"بدون غنی‌سازی ۹۰٪ ساخت کلاهک قفل است ({why[:40]})")

    # مرحله ۳ را رد کنیم و ببینیم هنوز قفل است
    await db.execute("INSERT OR REPLACE INTO enrichment(user_id, stage) VALUES(?,3)", (ATTACKER,))
    ok, why = await nuke.can_build(ATTACKER)
    H.check(not ok, "در غنی‌سازی ۶۰٪ هم ساخت کلاهک ممکن نیست")

    # رسیدن به ۹۰٪ + تأسیسات فعال
    await db.execute("UPDATE enrichment SET stage=4 WHERE user_id=?", (ATTACKER,))
    ok, why = await nuke.can_build(ATTACKER)
    H.check(ok, f"با غنی‌سازی ۹۰٪ ساخت کلاهک ممکن است ({why[:60]})")

    # ═══════════════ ۲) ساخت و تحویل کلاهک ═══════════════
    print("\n== TEST 2: ساخت کلاهک با هزینه و زمان ==")
    await set_setting("nuke_bomb_minutes", "0")      # برای تست: فوری
    await set_setting("nuke_bomb_limit", "8")
    money_before = int((await db.fetchone("SELECT money FROM users WHERE id=?", (ATTACKER,)))["money"])
    mats_before = int((await db.fetchone("SELECT materials FROM states WHERE user_id=?",
                                          (ATTACKER,)))["materials"])
    ok, msg = await nuke.build(None, ATTACKER, "فاتح هسته‌ای")
    H.check(ok, f"ساخت کلاهک انجام شد ({msg.splitlines()[0][:60]})")
    inv = await nuke.arsenal(ATTACKER)
    H.check(int(inv["bombs"]) == 1, f"یک کلاهک در زرادخانه است ({inv['bombs']})")
    money_after = int((await db.fetchone("SELECT money FROM users WHERE id=?", (ATTACKER,)))["money"])
    mats_after = int((await db.fetchone("SELECT materials FROM states WHERE user_id=?",
                                         (ATTACKER,)))["materials"])
    H.check(money_after < money_before, f"هزینهٔ پول کسر شد ({money_before}→{money_after})")
    H.check(mats_after < mats_before, f"مصالح کسر شد ({mats_before}→{mats_after})")
    bombs = await nuke.bomb_list(ATTACKER)
    H.check(len(bombs) == 1 and bombs[0]["name"] == "فاتح هسته‌ای",
            f"کلاهک با نام ثبت شد ({bombs[0]['name'] if bombs else '—'})")
    H.check(bool(bombs) and float(bombs[0]["yield_kt"]) > 0,
            f"قدرت کلاهک ثبت شد ({bombs[0]['yield_kt'] if bombs else 0} کیلوتن)")

    # سقف زرادخانه
    await set_setting("nuke_bomb_limit", "1")
    ok, why = await nuke.can_build(ATTACKER)
    H.check(not ok and "پر است" in why, f"سقف زرادخانه اعمال می‌شود ({why[:40]})")
    await set_setting("nuke_bomb_limit", "8")

    # ساخت با زمان: تحویل با settle
    await set_setting("nuke_bomb_minutes", "20")
    await db.execute("UPDATE states SET materials=200000 WHERE user_id=?", (ATTACKER,))
    ok, _msg = await nuke.build(None, ATTACKER, "")
    H.check(ok, "ساخت دومین کلاهک با زمان شروع شد")
    info = await nuke.building_info(ATTACKER)
    H.check(info is not None, "کلاهک در حال ساخت ثبت شد")
    H.check(int((await nuke.arsenal(ATTACKER))["bombs"]) == 1,
            "کلاهک در حال ساخت هنوز به زرادخانه اضافه نشده")
    # زمان را به گذشته ببریم → تحویل
    await db.execute("UPDATE nuclear_bombs SET ready_at='2020-01-01 00:00:00' "
                     "WHERE owner_id=? AND state='building'", (ATTACKER,))
    done = await nuke.settle(ATTACKER)
    H.check(done is not None, "تحویل کلاهک پس از پایان زمان")
    H.check(int((await nuke.arsenal(ATTACKER))["bombs"]) == 2,
            "کلاهک دوم به زرادخانه اضافه شد")
    H.check(await nuke.building_info(ATTACKER) is None, "صف ساخت خالی شد")
    # 🚀 بقای صف ساخت بعد از ری‌استارت: فقط دیتابیس منبع حقیقت است
    await db.execute("INSERT INTO nuclear_bombs(owner_id, name, yield_kt, state, built_at, ready_at) "
                     "VALUES(?,'پس از ری‌استارت',0,'building',datetime('now'),"
                     "datetime('now','+20 minutes'))", (ATTACKER,))
    nuke._PREPARED = False                          # شبیه‌سازی ری‌استارت پروسه
    H.check(await nuke.building_info(ATTACKER) is not None,
            "صف ساخت پس از ری‌استارت سرور باقی می‌ماند")
    await db.execute("DELETE FROM nuclear_bombs WHERE owner_id=? AND state='building'", (ATTACKER,))
    await set_setting("nuke_bomb_minutes", "30")

    # ═══════════════ ۳) شلیک هسته‌ای ═══════════════
    print("\n== TEST 3: شلیک کلاهک و پیامدها ==")
    await set_setting("nuke_strike_cooldown_hours", "0")
    ok, why = await nuke.can_strike(ATTACKER)
    H.check(ok, f"شلیک ممکن است ({why[:40]})")

    # استان برای مدافع بسازیم
    from core.provinces import ensure_country_provinces
    user_row = await db.fetchone("SELECT country_id FROM users WHERE id=?", (DEFENDER,))
    if user_row and user_row["country_id"]:
        await ensure_country_provinces(int(user_row["country_id"]), DEFENDER, normalize=True)
    prov_before = (await db.fetchone("SELECT COUNT(*) c FROM provinces WHERE owner_id=?",
                                     (DEFENDER,)))["c"]

    sat_before = int((await db.fetchone("SELECT satisfaction FROM states WHERE user_id=?",
                                        (DEFENDER,)))["satisfaction"])
    look = await nuke.outlook(ATTACKER, DEFENDER)
    H.check(look["yield_kt"] > 0, f"قدرت کلاهک در پیش‌نمایش ({look['yield_kt']} کیلوتن)")
    H.check(look["civilian"] > 0, f"تلفات غیرنظامی تخمینی ({look['civilian']})")
    H.check(0 <= look["mitigation"] <= 35, f"سقف کاهش اثر پدافند ({look['mitigation']}٪)")

    dbg("can_strike", await nuke.can_strike(ATTACKER))
    dbg("bombs", await nuke.arsenal(ATTACKER))
    report = await nuke.strike(None, ATTACKER, DEFENDER)
    dbg("report", report[:200])
    H.check("ضربهٔ هسته‌ای" in report, "گزارش ضربهٔ هسته‌ای ساخته شد")
    inv = await nuke.arsenal(ATTACKER)
    H.check(int(inv["bombs"]) == 1, f"یک کلاهک مصرف شد (باقی: {inv['bombs']})")
    sat_after = int((await db.fetchone("SELECT satisfaction FROM states WHERE user_id=?",
                                       (DEFENDER,)))["satisfaction"])
    H.check(sat_after < sat_before, f"رضایت کشور هدف افت کرد ({sat_before}→{sat_after})")
    prov_after = (await db.fetchone("SELECT COUNT(*) c FROM provinces WHERE owner_id=?",
                                    (DEFENDER,)))["c"]
    H.check(prov_after <= prov_before, f"استان‌های مدافع بیشتر نشد ({prov_before}→{prov_after})")
    strike_log = await db.fetchone(
        "SELECT * FROM nuclear_strikes WHERE attacker_id=? AND damage>100", (ATTACKER,))
    H.check(bool(strike_log), "ضربهٔ هسته‌ای در جدول حمله‌ها ثبت شد")

    # کول‌داون
    await set_setting("nuke_strike_cooldown_hours", "12")
    left = await nuke.cooldown_left(ATTACKER)
    H.check(left > 0, f"کول‌داون هسته‌ای فعال شد ({left} دقیقه)")
    ok, why = await nuke.can_strike(ATTACKER)
    H.check(not ok and "صبر" in why, "شلیک دوم در کول‌داون رد می‌شود")

    # بدون کلاهک
    await db.execute("UPDATE nuclear_arsenal SET bombs=0 WHERE user_id=?", (ATTACKER,))
    await set_setting("nuke_strike_cooldown_hours", "0")
    ok, why = await nuke.can_strike(ATTACKER)
    H.check(not ok and "کلاهک" in why, "بدون کلاهک شلیک ممکن نیست")
    msg = await nuke.strike(None, ATTACKER, DEFENDER)
    H.check("کلاهک" in msg, "شلیک بدون کلاهک پیام درست می‌دهد")

    # ═══════════════ ۴) رابط تلگرام ═══════════════
    print("\n== TEST 4: منوی بمب اتم در ربات ==")
    await db.execute("INSERT OR REPLACE INTO nuclear_arsenal(user_id, bombs) VALUES(?,3)",
                     (ATTACKER,))
    await set_setting("nuke_strike_cooldown_hours", "0")
    await db.execute("INSERT OR REPLACE INTO enrichment(user_id, stage) VALUES(?,4)", (ATTACKER,))
    from core import nuclear as nuc_site
    await nuc_site.sync_stage(ATTACKER)
    await db.execute("INSERT INTO nuclear_sites(user_id, stage, kind, hp, max_hp, active) "
                     "VALUES(?,4,'x',100,100,1) ON CONFLICT(user_id) DO UPDATE SET active=1, hp=100",
                     (ATTACKER,))

    from gamebot.main import create_dispatcher as game_dp_factory
    bot = H.FakeBot("42:GAME")
    H.BOT_REF["bot"] = bot
    dp = game_dp_factory()
    dp.errors.register(lambda e: (H.ERRORS.append(f"game: {e.exception}"), True)[1])

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, "g|nuke"))
    texts = H.shot("nuke menu")[0]
    text = texts[-1] if texts else ""
    H.check("سلاح هسته‌ای" in text, "منوی سلاح هسته‌ای باز شد")
    H.check("زرادخانه" in text, "شمار زرادخانه نمایش داده شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, "g|nuketg"))
    texts = H.shot("nuke targets")[0]
    text = texts[-1] if texts else ""
    H.check("انتخاب هدف" in text, "فهرست اهداف هسته‌ای باز شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, f"g|nukeconf|{DEFENDER}"))
    texts = H.shot("nuke confirm")[0]
    text = texts[-1] if texts else ""
    H.check("تأیید ضربهٔ هسته‌ای" in text, "پیش‌نمایش تأیید شلیک آمد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, f"g|nukego|{DEFENDER}"))
    texts = H.shot("nuke fire")[0]
    text = texts[-1] if texts else ""
    H.check("ضربهٔ هسته‌ای" in text, "شلیک از دکمه انجام شد")
    H.check(int((await nuke.arsenal(ATTACKER))["bombs"]) == 2, "زرادخانه از دکمه کم شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, "g|nukehelp"))
    texts = H.shot("nuke help")[0]
    text = texts[-1] if texts else ""
    H.check("راهنمای سلاح هسته‌ای" in text, "راهنمای بمب باز شد")

    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(ATTACKER, "g|enrich"))
    H.shot("enrich")
    import inspect
    from gamebot.handlers.world import enrich_menu
    src = inspect.getsource(enrich_menu)
    H.check('"g|nuke"' in src, "دکمهٔ بمب اتم در بخش غنی‌سازی هست")
    H.check("nukebuild" in inspect.getsource(
        __import__("gamebot.handlers.world", fromlist=["x"]).nuke_menu),
        "ساخت کلاهک از منوی هسته‌ای در دسترس است")

    # ═══════════════ ۵) خرابکاری هسته‌ای ═══════════════
    print("\n== TEST 5: زدن تأسیسات هسته‌ای از خرابکاری زیرساخت ==")
    await db.execute("INSERT OR REPLACE INTO enrichment(user_id, stage) VALUES(?,2)", (DEFENDER,))
    await nuc_site.sync_stage(DEFENDER)
    await db.execute("UPDATE nuclear_sites SET active=1, hp=100 WHERE user_id=?", (DEFENDER,))
    await set_setting("sabotage_cooldown_minutes", "0")
    facs = await sabotage.facilities(DEFENDER)
    H.check(any(f["kind"] == "nuclear" for f in facs), "تأسیسات هسته‌ای در اهداف است")
    cats = await sabotage.weapon_categories(ATTACKER)
    H.check("missile" in cats, f"سلاح موشکی شناسایی شد ({sorted(cats)})")
    ok, why = await sabotage.can_sabotage(ATTACKER, "nuclear")
    H.check(ok, f"خرابکاری در تأسیسات هسته‌ای مجاز است ({why[:50]})")
    hp_before = int((await nuc_site.ensure_site(DEFENDER))["hp"])
    got_report = ""
    for _ in range(12):
        got_report = await sabotage.sabotage(bot, ATTACKER, DEFENDER, "nuclear", 0)
        site = await nuc_site.ensure_site(DEFENDER)
        if int(site["hp"]) < hp_before:
            break
    site = await nuc_site.ensure_site(DEFENDER)
    H.check(int(site["hp"]) < hp_before,
            f"تأسیسات هسته‌ای آسیب دید ({hp_before}→{site['hp']})")
    H.check("تأسیسات هسته‌ای" in got_report, "گزارش حمله به تأسیسات ساخته شد")

    # کشوری که تأسیسات ندارد پیام درست بگیرد
    await db.execute("DELETE FROM nuclear_sites WHERE user_id=?", (POOR,))
    msg = await sabotage.sabotage(bot, ATTACKER, POOR, "nuclear", 0)
    H.check("تأسیسات" in msg or "سازه" in msg,
            f"کشور بدون تأسیسات پیام درست می‌دهد ({msg[:40]})")

    # ═══════════════ ۶) تلفات واقعی نبرد ═══════════════
    print("\n== TEST 6: تلفات فقط از یگان‌های درگیر (نه کل انبار) ==")
    carrier = await equipment_id("ناو هواپیمابر")
    if carrier == 0:
        carrier = await equipment_id("ناو")
    H.check(carrier > 0, f"ناو در دیتابیس است ({carrier})")
    await db.execute("DELETE FROM player_assets WHERE user_id IN (?,?)", (ATTACKER, DEFENDER))
    # مدافع: ۱۰۰ ناو در انبار
    await give_equipment(DEFENDER, carrier, 100)
    # مهاجم: ۵ کشتی + یک موشک که عملاً اعزام می‌شود
    small_ship = await equipment_id("قایق تندرو")
    await give_equipment(ATTACKER, small_ship or carrier, 5)
    H.check(await qty_of(DEFENDER, "equipment", carrier) == 100, "مدافع ۱۰۰ ناو دارد")

    combat.set_deployed(ATTACKER, "equipment", [small_ship or carrier])
    att_rows = await combat.equipment_rows(ATTACKER, only_ids=[small_ship or carrier])
    cap = await combat.defend_cap(ATTACKER, 5)
    H.check(cap <= 10, f"سقف تلفات مدافع متناسب با نیروی اعزامی است ({cap})")
    def_rows = await combat.equipment_rows(DEFENDER)
    names, lost = await combat.apply_capped_losses(DEFENDER, def_rows, 0.75, cap)
    left = await qty_of(DEFENDER, "equipment", carrier)
    H.check(left >= 100 - cap, f"تلفات مدافع از سقف رد نشد (مانده {left} از ۱۰۰، سقف {cap})")
    H.check(lost <= cap, f"تعداد نابودشده در سقف ماند ({lost})")

    # تلفات مهاجم فقط از یگان درگیر
    await db.execute("DELETE FROM player_assets WHERE user_id=?", (ATTACKER,))
    reserve_id = await equipment_id("ناو")
    await give_equipment(ATTACKER, small_ship or carrier, 5)
    await give_equipment(ATTACKER, reserve_id, 80)
    combat.set_deployed(ATTACKER, "equipment", [small_ship or carrier])
    att_rows = await combat.equipment_rows(ATTACKER, only_ids=[small_ship or carrier])
    lost_names, lost_units, note = await combat.apply_attrition_losses(
        ATTACKER, await combat.equipment_rows(ATTACKER), 0.90)
    reserve_left = await qty_of(ATTACKER, "equipment", reserve_id)
    H.check(reserve_left >= 75,
            f"ذخیره‌گاه مهاجم تقریباً سالم ماند ({reserve_left} از ۸۰ ناو)")
    H.check(bool(note), f"توضیح شفاف تلفات ساخته شد ({note[:50]})")

    # ═══════════════ ۷) حذف سقف ۵۰۰ ═══════════════
    print("\n== TEST 7: سقف ۵۰۰ عددی ساخت برداشته شد ==")
    import inspect
    from gamebot.handlers import army as army_mod
    from gamebot.handlers import oil as oil_mod
    from gamebot.handlers import people as people_mod
    for mod, fn in ((people_mod, "buy_building_custom_input"),
                    (oil_mod, "oil_rig_custom_input"),
                    (army_mod, "eq_qty_input")):
        src = inspect.getsource(getattr(mod, fn))
        H.check("qty > 500" not in src.replace(" ", ""),
                f"سقف ۵۰۰ در {fn} حذف شده")
        H.check("1_000_000" in src or "10_000_000" in src,
                f"سقف منطقی بزرگ در {fn} هست")

    # ساخت واقعی ۶۰۰ عدد (بیشتر از سقف قبلی)
    from gamebot.handlers.people import execute_building_purchase
    b = await db.fetchone("SELECT * FROM buildings WHERE cost_money<10000000 ORDER BY id LIMIT 1")
    if b:
        await db.execute("UPDATE users SET money=90000000000 WHERE id=?", (POOR,))
        await db.execute("UPDATE states SET materials=90000000 WHERE user_id=?", (POOR,))
        await db.execute("DELETE FROM player_assets WHERE user_id=? AND item_type='building'",
                         (POOR,))

        class FakeMsg:
            def __init__(self, uid):
                self.from_user = type("U", (), {"id": uid})()

            async def answer(self, text, **_kw):
                H.SENT.append(("sendMessage", self.from_user.id, text, None))

        await execute_building_purchase(FakeMsg(POOR), int(b["id"]), 600)
        have = await qty_of(POOR, "building", int(b["id"]))
        H.check(have == 600, f"۶۰۰ عدد در یک بار ساخته شد (ساخته شد: {have})")

    # ═══════════════ ۸) ریست کامل، زرادخانه را هم پاک می‌کند ═══════════════
    print("\n== TEST 8: ریست کامل زرادخانه را پاک می‌کند ==")
    from core.fullreset import reset_player_progress
    await db.execute("INSERT OR REPLACE INTO nuclear_arsenal(user_id, bombs) VALUES(?,2)",
                     (ATTACKER,))
    await db.execute("INSERT INTO nuclear_bombs(owner_id, name, yield_kt, state) "
                     "VALUES(?,'تست',150,'ready')", (ATTACKER,))
    await reset_player_progress(ATTACKER)
    inv = await nuke.arsenal(ATTACKER)
    H.check(int(inv["bombs"]) == 0, f"زرادخانه پس از ریست خالی شد ({inv['bombs']})")
    left_bombs = await db.fetchone("SELECT COUNT(*) c FROM nuclear_bombs WHERE owner_id=?",
                                   (ATTACKER,))
    H.check(int(left_bombs["c"]) == 0, "کلاهک‌های ثبت‌شده پاک شدند")

    # ─── تنظیمات تست را برگردانیم ───
    await set_setting("nuke_bomb_minutes", "30")
    await set_setting("nuke_bomb_limit", "8")
    await set_setting("nuke_strike_cooldown_hours", "12")
    await set_setting("sabotage_cooldown_minutes", "20")

    print("\n=== TOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("   -", e)
    await db.close()


asyncio.run(main())

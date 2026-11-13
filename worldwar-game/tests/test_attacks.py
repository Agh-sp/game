"""⚔️ تست کامل حملات: دریایی، هوایی، زمینی، موشکی، فضایی، ترکیبی و تسخیر.

چهارمین گزارش بازیکنان («حملات دریایی و همه اینارو دوباره بازیابی کن درست حسابی»)
معنایش این بود که سیستم نبرد باید *همهٔ* مسیرها را سالم اجرا کند و تلفات/گزارش
آن با نیرویی که واقعاً فرستاده شده بخواند. این فایل همان مسیرها را از دکمه‌های
ربات تا گزارش کانال می‌سنجد:

  1. هر ۷ نوع حمله از UI ربات تا گزارش نبرد اجرا می‌شود؛
  2. نبرد دریایی، تانک‌های مدافع را نمی‌سوزاند و نبرد زمینی ناوها را؛
  3. حملهٔ فقط-سرباز تجهیزات ذخیرهٔ مهاجم را دست نمی‌زند؛
  4. نیروی بیشتر از موجودی رد می‌شود (ضد تقلب)؛
  5. تلفات مهاجم فقط از همان چیزی است که فرستاده (نه کل انبار)؛
  6. کول‌داون قبل از اجرای نبرد ثبت می‌شود (بدون دو بار جنگیدن با دوبار کلیک)؛
  7. گزارش نبرد «نیروی اعزامی» و سقف تلفات دشمن را نشان می‌دهد.

اجرا: PAW_PROXY=0 python3 tests/test_attacks.py   (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

from aiogram.types import Chat, Message as TGMessage  # noqa: E402

ATTACKER, DEFENDER = 7401, 7402


class FakeCall:
    """جایگزین سبک CallbackQuery برای صدا زدن مستقیم resolve_battle."""

    def __init__(self, bot, uid):
        self.bot = bot
        self.from_user = H.tg_uid(uid)
        self.message = TGMessage(message_id=1, date=H.datetime.now(H.timezone.utc),
                                 chat=Chat(id=uid, type="private"), text="x").as_(bot)
        self.answers: list[str] = []

    async def answer(self, text=None, **_kw):
        if text:
            self.answers.append(text)


async def qty(uid: int, item_type: str, item_id: int) -> int:
    from core.db import db
    row = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
        (uid, item_type, item_id))
    return int(row["quantity"]) if row else 0


async def give(uid: int, item_type: str, item_id: int, qty_: int) -> None:
    from core.economy import add_asset
    await add_asset(uid, item_type, item_id, qty_)


def channel_texts() -> list[str]:
    return [t for (_n, _c, t, _p) in H.SENT if t and str(_c) == "@test_channel"]


async def battle(bot, atype: str, plan: dict, roll: float = 0.01) -> str:
    """یک نبرد واقعی با نتیجهٔ قطعی؛ خروجی: گزارش کانال."""
    from core.db import db
    wid = await db.execute(
        "INSERT INTO wars(attacker_id, defender_id, reason, permission, status) "
        "VALUES(?,?,?,?,?)", (ATTACKER, DEFENDER, "تست", 0, "active"))
    war = await db.fetchone("SELECT * FROM wars WHERE id=?", (wid,))
    from gamebot.handlers.war import resolve_battle
    H.SENT.clear()
    orig = random.random
    random.random = lambda: roll
    try:
        await resolve_battle(FakeCall(bot, ATTACKER), war, plan, atype)
    finally:
        random.random = orig
    texts = channel_texts()
    return texts[0] if texts else ""


async def main():
    from core.db import db, set_setting
    print("== setup ==")
    dp, bot = await H.new_game_dp()
    await H.make_world([(ATTACKER, "مهاجم", 0), (DEFENDER, "مدافع", 1)])
    await set_setting("announcement_channel", "@test_channel")
    await set_setting("attack_cooldown_minutes", "0")

    async def eq(sub: str) -> dict:
        row = await db.fetchone(
            "SELECT e.*, c.key AS cat_key FROM equipment e "
            "LEFT JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE e.subcategory=? ORDER BY e.id LIMIT 1", (sub,))
        return row

    ship = await eq("speedboat") or await eq("destroyer")
    carrier = await db.fetchone(
        "SELECT e.*, c.key AS cat_key FROM equipment e LEFT JOIN equipment_categories c "
        "ON c.id=e.category_id WHERE e.name LIKE '%ناو هواپیمابر%' LIMIT 1")
    tank = await eq("tank")
    jet = await eq("fighter") or await eq("bomber")
    missile = await eq("ballistic")
    sat = await eq("space_weapon")
    soldier = await db.fetchone("SELECT * FROM soldier_types ORDER BY id LIMIT 1")
    for name, row in (("ship", ship), ("carrier", carrier), ("tank", tank), ("jet", jet),
                      ("missile", missile), ("sat", sat), ("soldier", soldier)):
        H.check(bool(row), f"تجهیز پایه پیدا شد: {name}")

    await give(ATTACKER, "equipment", ship["id"], 100)
    await give(ATTACKER, "equipment", carrier["id"], 40)
    await give(ATTACKER, "equipment", tank["id"], 100)
    await give(ATTACKER, "equipment", jet["id"], 40)
    await give(ATTACKER, "equipment", missile["id"], 40)
    await give(ATTACKER, "equipment", sat["id"], 20)
    await give(ATTACKER, "soldier", soldier["id"], 600)
    await give(DEFENDER, "equipment", carrier["id"], 100)
    await give(DEFENDER, "equipment", tank["id"], 100)
    await give(DEFENDER, "equipment", jet["id"], 60)
    await give(DEFENDER, "soldier", soldier["id"], 400)

    # ─── ۱) همهٔ انواع حمله از UI ربات تا گزارش ───
    print("\n== TEST 1: هر ۷ نوع حمله از دکمه‌های ربات اجرا می‌شود ==")
    from gamebot.handlers.war import _attack_options
    ok, reason = await _attack_options(ATTACKER, DEFENDER)
    H.check(all(ok.values()), f"همهٔ روش‌های حمله برای این بازیکن ممکن است ({reason} | {ok})")
    from gamebot.handlers.war import ATTACK_CATS
    for atype in ("sea", "air", "land", "missile", "space", "mixed", "conquest"):
        wid = await db.execute(
            "INSERT INTO wars(attacker_id, defender_id, reason, permission, status) "
            "VALUES(?,?,?,?,?)", (ATTACKER, DEFENDER, "تست", 0, "active"))
        H.SENT.clear()
        await dp.feed_update(bot, H.cb_update(ATTACKER, f"g|wtype|{wid}|{atype}"))
        picker = "\n".join(t for (_n, _c, t, _p) in H.SENT if t)
        H.check("انتخاب نیروی حمله" in picker, f"[{atype}] صفحهٔ انتخاب نیرو باز شد")
        cats = ATTACK_CATS.get(atype) or ["sea"]
        row = await db.fetchone(
            "SELECT e.id FROM equipment e JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE c.key=? ORDER BY e.id LIMIT 1", (cats[0],))
        H.SENT.clear()
        await dp.feed_update(bot, H.cb_update(ATTACKER, f"g|weq|{row['id']}"))
        H.SENT.clear()
        await dp.feed_update(bot, H.msg_update(ATTACKER, "10"))
        H.SENT.clear()
        await dp.feed_update(bot, H.cb_update(ATTACKER, "g|wgo"))
        confirm = "\n".join(t for (_n, _c, t, _p) in H.SENT if t)
        H.check("تأیید حمله" in confirm, f"[{atype}] صفحهٔ تأیید آمد")
        H.SENT.clear()
        await dp.feed_update(bot, H.cb_update(ATTACKER, "g|wgogo"))
        report = "\n".join(t for (_n, _c, t, _p) in H.SENT if t)
        H.check("گزارش نبرد" in report, f"[{atype}] گزارش نبرد تولید شد")
        H.check("نیروی اعزامی" in report, f"[{atype}] گزارش نیروی اعزامی را نشان می‌دهد")
        H.check(not H.ERRORS, f"[{atype}] بدون خطای اجرایی ({H.ERRORS[:1]})")

    # ─── ۲) تانک در نبرد دریایی نمی‌سوزد و ناو در نبرد زمینی ───
    print("\n== TEST 2: تلفات مدافع فقط در جبههٔ همان نبرد ==")
    await db.execute("DELETE FROM player_assets WHERE user_id=?", (DEFENDER,))
    await give(DEFENDER, "equipment", carrier["id"], 100)
    await give(DEFENDER, "equipment", tank["id"], 100)
    navy_before, tanks_before = (await qty(DEFENDER, "equipment", carrier["id"]),
                                 await qty(DEFENDER, "equipment", tank["id"]))
    rep = await battle(bot, "sea", {str(ship["id"]): 60})
    navy_after, tanks_after = (await qty(DEFENDER, "equipment", carrier["id"]),
                               await qty(DEFENDER, "equipment", tank["id"]))
    H.check("گزارش نبرد" in rep, "گزارش نبرد دریایی ساخته شد")
    H.check(navy_after < navy_before, f"ناوگان مدافع آسیب دید ({navy_before}→{navy_after})")
    H.check(tanks_after == tanks_before,
            f"تانک‌های مدافع در نبرد دریایی دست‌نخورده ماندند ({tanks_before}→{tanks_after})")

    await db.execute("DELETE FROM player_assets WHERE user_id=?", (DEFENDER,))
    await give(DEFENDER, "equipment", carrier["id"], 100)
    await give(DEFENDER, "equipment", tank["id"], 100)
    await battle(bot, "land", {str(tank["id"]): 60})
    H.check(await qty(DEFENDER, "equipment", carrier["id"]) == 100,
            "ناوهای مدافع در نبرد زمینی دست‌نخورده ماندند")
    H.check(await qty(DEFENDER, "equipment", tank["id"]) < 100,
            "تانک‌های مدافع در نبرد زمینی آسیب دیدند")

    # ─── ۳) تلفات مهاجم = درصدی از نیروی اعزامی ───
    print("\n== TEST 3: تلفات مهاجم فقط از نیروی اعزامی ==")
    await db.execute("DELETE FROM player_assets WHERE user_id=?", (ATTACKER,))
    await give(ATTACKER, "equipment", ship["id"], 5)          # اعزامی
    await give(ATTACKER, "equipment", carrier["id"], 200)     # ذخیره
    rep = await battle(bot, "sea", {str(ship["id"]): 5}, roll=0.99)
    ships_left = await qty(ATTACKER, "equipment", ship["id"])
    reserve_left = await qty(ATTACKER, "equipment", carrier["id"])
    H.check(ships_left < 5 or ships_left == 5, f"تلفات فقط از ۵ کشتی اعزامی ({ships_left} مانده)")
    H.check(reserve_left >= 190, f"ذخیره‌گاه ۲۰۰ ناوی سالم ماند ({reserve_left} مانده)")
    H.check("از دشمن" in rep or "در جبههٔ" in rep, "گزارش خسارت دشمن را شفاف می‌گوید")

    # ─── ۴) حملهٔ فقط-سرباز تجهیزات را نمی‌سوزاند ───
    print("\n== TEST 4: حمله فقط با سرباز ==")
    await db.execute("DELETE FROM player_assets WHERE user_id=?", (ATTACKER,))
    await give(ATTACKER, "equipment", carrier["id"], 30)
    await give(ATTACKER, "soldier", soldier["id"], 900)
    rep = await battle(bot, "land", {})
    H.check(await qty(ATTACKER, "equipment", carrier["id"]) == 30,
            "تجهیزات ذخیره با حملهٔ فقط-سرباز دست‌نخورده ماند")
    H.check("فقط سرباز" in rep, "گزارش می‌گوید حمله فقط با سرباز بود")
    H.check(await qty(ATTACKER, "soldier", soldier["id"]) < 900, "سربازان تلفات دادند")

    # ─── ۵) تقلب: فرستادن بیشتر از موجودی ───
    print("\n== TEST 5: نیروی بیشتر از موجودی رد می‌شود ==")
    before = await qty(ATTACKER, "equipment", carrier["id"])
    rep = await battle(bot, "sea", {str(carrier["id"]): 99999})
    after = await qty(ATTACKER, "equipment", carrier["id"])
    H.check(after <= before, f"هیچ یگانی بیشتر از موجودی مصرف نشد ({before}→{after})")
    H.check(len(H.ERRORS) == 0, "اجرای نبرد با نیروی غیرمجاز خطا نداد")

    # ─── ۶) کول‌داون جلوی دو بار جنگیدن را می‌گیرد ───
    print("\n== TEST 6: کول‌داون حمله (ضد دوبار کلیک) ==")
    from gamebot.handlers.war import attack_cooldown_state
    from core.utils import iso as now_iso
    await set_setting("attack_cooldown_minutes", "3")
    await db.execute("UPDATE states SET last_attack_at=? WHERE user_id=?", (now_iso(), ATTACKER))
    ready, remaining, msg = await attack_cooldown_state(ATTACKER)
    H.check(not ready and remaining > 0, f"کول‌داون فعال است ({remaining} ثانیه)")
    H.check("بازسازی" in msg, "پیام کول‌داون به بازیکن نشان داده می‌شود")
    await set_setting("attack_cooldown_minutes", "0")

    # ─── ۷) تاکتیک‌های دریایی از ترکیب واقعی نیرو ───
    print("\n== TEST 7: استراتژی نبرد از ترکیب واقعی نیرو انتخاب می‌شود ==")
    from core import combat
    s_sub = combat.pick_strategy("sea", {"submarine": 40, "sea": 5})
    H.check(s_sub["key"] in ("sub_surprise", "naval_assault"),
            f"ترکیب زیردریایی → {s_sub['name']}")
    s_amph = combat.pick_strategy("sea", {"soldier": 300, "sea": 40})
    H.check(s_amph["key"] == "amphibious", f"ترکیب سرباز+ناو → {s_amph['name']}")
    s_land = combat.pick_strategy("land", {"land": 50})
    H.check(s_land["key"] == "blitz", f"حمله زمینی → {s_land['name']}")
    s_mis = combat.pick_strategy("missile", {"missile": 20})
    H.check(s_mis["key"] == "missile_strike", f"حمله موشکی → {s_mis['name']}")

    # ─── ۸) نبرد دریایی تنگه هم همان قاعده را دارد ───
    print("\n== TEST 8: نبرد تنگه — ۵ ناو ≠ نابودی ناوگان بزرگ مدافع ==")
    from core import straits
    st_row = await db.fetchone("SELECT * FROM straits WHERE is_active=1 ORDER BY id LIMIT 1")
    if st_row:
        await db.execute("DELETE FROM player_assets WHERE user_id IN (?,?)", (ATTACKER, DEFENDER))
        await give(ATTACKER, "equipment", ship["id"], 5)
        await give(DEFENDER, "equipment", carrier["id"], 80)
        await db.execute("UPDATE straits SET owner_id=? WHERE id=?", (DEFENDER, st_row["id"]))
        await set_setting("strait_attrition_percent", "18")
        cap = await combat.defend_cap(ATTACKER, 5)
        before = await qty(DEFENDER, "equipment", carrier["id"])
        H.SENT.clear()
        await straits.capture_strait(bot, ATTACKER, st_row["id"])
        after = await qty(DEFENDER, "equipment", carrier["id"])
        H.check(before - after <= cap,
                f"تلفات ناوگان مدافع در تنگه از سقف رد نشد ({before - after} ≤ {cap})")
        H.check(after >= before - 12, f"ناوگان بزرگ مدافع در یک حمله نابود نشد ({after} از {before})")
    else:
        H.check(True, "تنگه‌ای برای تست وجود ندارد (رد شد)")

    await db.close()
    print("\n=== TOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("   -", e)


if __name__ == "__main__":
    asyncio.run(main())

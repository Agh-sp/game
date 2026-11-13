"""تست نبرد واقعی: تسخیر تنگه با نبرد دریایی + تلفات دو طرف + گزارش کانال.

اجرا: /tmp/venv/bin/python tests/test_combat.py   (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402  (DB_PATH و sys.path را تنظیم می‌کند)

from aiogram.types import Chat, Message as TGMessage  # noqa: E402


class FakeCall:
    """جایگزین سبک CallbackQuery برای صدا زدن مستقیم resolve_battle."""

    def __init__(self, bot, uid):
        self.bot = bot
        self.from_user = H.tg_uid(uid)
        self.message = TGMessage(message_id=1, date=H.datetime.now(H.timezone.utc),
                                 chat=Chat(id=uid, type="private"),
                                 text="x").as_(bot)
        self._answers = []

    async def answer(self, text=None, **kw):
        if text:
            self._answers.append(text)


async def equip_id(name_part: str) -> dict:
    from core.db import db
    row = await db.fetchone("SELECT e.*, c.key AS cat_key FROM equipment e "
                            "LEFT JOIN equipment_categories c ON c.id=e.category_id "
                            "WHERE e.name LIKE ? LIMIT 1", (f"%{name_part}%",))
    return row


async def qty(uid: int, item_type: str, item_id: int) -> int:
    from core.db import db
    row = await db.fetchone(
        "SELECT quantity FROM player_assets WHERE user_id=? AND item_type=? AND item_id=?",
        (uid, item_type, item_id))
    return int(row["quantity"]) if row else 0


def channel_texts() -> list[str]:
    return [t for (_n, _c, t, _p) in H.SENT if t and str(_c) == "@test_channel"]


async def main():
    from core.db import db, set_setting
    print("== setup ==")
    dp, bot = await H.new_game_dp()
    await H.make_world([(101, "مهاجم", 0), (102, "مدافع", 1)])
    await set_setting("announcement_channel", "@test_channel")

    from core.economy import add_asset
    from core import combat, straits

    frigate = await equip_id("ناوچه جماران")     # sea / frigate
    sub = await equip_id("زیردریایی سبک")
    missile = await equip_id("شهاب")              # in case of missile test
    soldier = await db.fetchone("SELECT * FROM soldier_types LIMIT 1")

    # ─── تست ۱: نبرد دریایی برای تنگه (پیروزی) ───
    print("\n== TEST 1: نبرد دریایی تنگه — پیروزی با تلفات دو طرف ==")
    await add_asset(101, "equipment", frigate["id"], 30)
    await add_asset(102, "equipment", frigate["id"], 3)
    await add_asset(102, "equipment", sub["id"], 2)
    await add_asset(101, "soldier", soldier["id"], 500)
    await add_asset(102, "soldier", soldier["id"], 200)

    sid = (await db.fetchone("SELECT id FROM straits WHERE is_active=1 ORDER BY id"))["id"]
    await db.execute("UPDATE straits SET owner_id=? WHERE id=?", (102, sid))

    atk_before = await qty(101, "equipment", frigate["id"])
    def_before = await qty(102, "equipment", frigate["id"]) + await qty(102, "equipment", sub["id"])
    orig_random = random.random
    random.random = lambda: 0.01          # تاس همیشه به نفع مهاجم
    H.SENT.clear()
    try:
        msg = await straits.capture_strait(bot, 101, sid)
    finally:
        random.random = orig_random

    atk_after = await qty(101, "equipment", frigate["id"])
    def_after = await qty(102, "equipment", frigate["id"]) + await qty(102, "equipment", sub["id"])
    owner = (await db.fetchone("SELECT owner_id FROM straits WHERE id=?", (sid,)))["owner_id"]

    H.check(owner == 101, "تنگه پس از پیروزی به مهاجم رسید")
    H.check(atk_after < atk_before, f"تلفات مهاجم واقعی اعمال شد ({atk_before}→{atk_after})")
    H.check(def_after < def_before, f"تلفات مدافع واقعی اعمال شد ({def_before}→{def_after})")
    H.check("استراتژی" in msg or "تسخیر" in msg, "پیام بازیکن استراتژی/نتیجه را دارد")

    texts = channel_texts()
    ann = texts[0] if texts else ""
    H.check(bool(texts), "گزارش نبرد در کانال اعلام شد")
    H.check("استراتژی" in ann, "کانال نوع استراتژی حمله را نوشت")
    H.check("خسارات طرفین" in ann, "کانال بخش خسارات طرفین دارد")
    H.check("تلفات مهاجم" in ann and "تلفات مدافع" in ann,
            "کانال تلفات هر دو طرف را جدا نوشت")
    H.check("توان مهاجم" in ann and "توان مدافع" in ann, "کانال توان دو طرف را نوشت")

    # ─── تست ۲: نبرد ناموفق — تنگه دست مدافع می‌ماند ───
    print("\n== TEST 2: نبرد ناموفق — تنگه آزاد نمی‌شود ==")
    await db.execute("UPDATE straits SET owner_id=? WHERE id=?", (102, sid))
    before_a = await qty(101, "equipment", frigate["id"])
    orig_random = random.random
    random.random = lambda: 0.999         # تاس همیشه به نفع مدافع
    H.SENT.clear()
    try:
        msg2 = await straits.capture_strait(bot, 101, sid)
    finally:
        random.random = orig_random
    owner2 = (await db.fetchone("SELECT owner_id FROM straits WHERE id=?", (sid,)))["owner_id"]
    H.check(owner2 == 102, "با شکست، مالکیت تنگه تغییر نکرد")
    H.check("دفع" in msg2 or "ناموفق" in msg2 or "❌" in msg2, "پیام بازیکن شکست را گزارش کرد")
    ann2 = channel_texts()[0] if channel_texts() else ""
    H.check("دفاع موفق" in ann2 or "دفع شد" in ann2, "کانال پیروزی مدافع را نوشت")

    # ─── تست ۳: نبود نیروی کافی ───
    print("\n== TEST 3: نیروی ناکافی → حملهٔ فرسایشی (بدون بلاک) ==")
    await db.execute("UPDATE player_assets SET quantity=1 WHERE user_id=101 AND item_type='equipment' AND item_id=?",
                     (frigate["id"],))
    st_row = await db.fetchone("SELECT * FROM straits WHERE id=?", (sid,))
    ok, err = await straits.capture_requirements(101, st_row)
    H.check(ok and err == "", f"حمله حتی با ناوگان ناکافی مجاز است (err={err!r})")
    look = await straits.attack_outlook(101, st_row)
    H.check(look["can_capture"] is False, "پیش‌بینی: در همین حمله تصرف ممکن نیست")
    H.check(look["needed_rounds"] >= 1, f"تعداد حملهٔ فرسایشی لازم: {look['needed_rounds']}")
    def_before = await straits.naval_defense(102)
    await add_asset(102, "equipment", frigate["id"], 5)   # ناوگان واقعی برای فرسایش
    def_before = await straits.naval_defense(102)
    await straits.capture_strait(bot, 101, sid)
    def_after = await straits.naval_defense(102)
    H.check(def_after < def_before, f"فرسایش تضمینی: دفاع مدافع {def_before} → {def_after}")


    # ─── تست ۴: نبرد کشورها — تلفات سرباز و تجهیزات هر دو طرف ───
    print("\n== TEST 4: نبرد کشورها با استراتژی و تلفات دو طرف ==")
    await add_asset(101, "equipment", frigate["id"], 20)
    await add_asset(101, "equipment", missile["id"], 10)
    await add_asset(102, "equipment", frigate["id"], 5)
    a_sol_before = await qty(101, "soldier", soldier["id"])
    d_sol_before = await qty(102, "soldier", soldier["id"])
    a_eq_before = await qty(101, "equipment", missile["id"])
    d_eq_before = await qty(102, "equipment", frigate["id"])

    war_id = await db.execute(
        "INSERT INTO wars(attacker_id, defender_id, reason, permission, status) VALUES(?,?,?,?,?)",
        (101, 102, "تست", 0, "active"))
    war = await db.fetchone("SELECT * FROM wars WHERE id=?", (war_id,))
    from gamebot.handlers.war import resolve_battle
    call = FakeCall(bot, 101)
    H.SENT.clear()
    orig_random = random.random
    random.random = lambda: 0.01
    try:
        await resolve_battle(call, war, {str(missile["id"]): 6}, "missile")
    finally:
        random.random = orig_random

    a_sol_after = await qty(101, "soldier", soldier["id"])
    d_sol_after = await qty(102, "soldier", soldier["id"])
    a_eq_after = await qty(101, "equipment", missile["id"])
    d_eq_after = await qty(102, "equipment", frigate["id"])
    H.check(a_eq_after < a_eq_before, f"تجهیزات ارسالی مهاجم کم شد ({a_eq_before}→{a_eq_after})")
    H.check(d_eq_after < d_eq_before, f"تجهیزات مدافع کم شد ({d_eq_before}→{d_eq_after})")
    H.check(a_sol_after < a_sol_before, f"سربازان مهاجم تلفات دادند ({a_sol_before}→{a_sol_after})")
    H.check(d_sol_after < d_sol_before, f"سربازان مدافع تلفات دادند ({d_sol_before}→{d_sol_after})")

    ann3 = channel_texts()[0] if channel_texts() else ""
    H.check("استراتژی" in ann3, "گزارش کانال استراتژی حمله را دارد")
    H.check("تلفات مهاجم" in ann3 and "تلفات مدافع" in ann3, "گزارش کانال تلفات دو طرف را دارد")
    H.check("توان مهاجم" in ann3, "گزارش کانال توان مهاجم را دارد")
    print("     >", ann3.replace("\n", " | ")[:400])

    # ─── تست ۵: شانس واقعی بر اساس نسبت نیرو ───
    print("\n== TEST 5: شانس نبرد تابع نسبت نیروها ==")
    c_equal = combat.battle_chance(1000, 1000)
    c_strong = combat.battle_chance(3000, 1000)
    c_weak = combat.battle_chance(300, 1000)
    H.check(0.45 <= c_equal <= 0.55, f"نیروی برابر ≈ ۵۰٪ ({round(c_equal * 100)}%)")
    H.check(c_strong > 0.75, f"برتری ۳ برابری شانس بالا ({round(c_strong * 100)}%)")
    H.check(c_weak < 0.25, f"ضعف ۳ برابری شانس پایین ({round(c_weak * 100)}%)")
    ar, dr = combat.loss_ratios(0.9, combat.strategy("naval_assault"))
    H.check(ar < dr, f"برنده تلفات کمتر از بازنده دارد (مهاجم {round(ar * 100)}% / مدافع {round(dr * 100)}%)")

    # ─── تست ۶: مسیر واقعی کاربر در ربات (دکمهٔ تصاحب تنگه) ───
    print("\n== TEST 6: مسیر کاربر — دکمهٔ «حمله دریایی برای تسخیر» ==")
    await db.execute("UPDATE straits SET owner_id=? WHERE id=?", (102, sid))
    await add_asset(101, "equipment", frigate["id"], 40)
    err_before = len(H.ERRORS)
    H.SENT.clear()
    orig_random = random.random
    random.random = lambda: 0.01
    try:
        # مرحلهٔ ۱: صفحهٔ تأیید حمله
        await dp.feed_update(bot, H.cb_update(101, f"g|stc|{sid}"))
        confirm_txt = "\n".join(t for (_n, _c, t, _p) in H.SENT if t)
        H.check("آیا حمله می‌کنید؟" in confirm_txt, "صفحهٔ تأیید حمله نمایش داده شد")
        # مرحلهٔ ۲: تأیید و اجرای نبرد
        await dp.feed_update(bot, H.cb_update(101, f"g|stgo|{sid}"))
    finally:
        random.random = orig_random
    H.check(len(H.ERRORS) == err_before, "بدون خطای اجرایی در مسیر دکمه‌ها")
    owner_ui = (await db.fetchone("SELECT owner_id FROM straits WHERE id=?", (sid,)))["owner_id"]
    H.check(owner_ui == 101, "تسخیر تنگه از طریق ربات انجام شد")
    ui_texts = channel_texts()
    H.check(bool(ui_texts) and "استراتژی" in ui_texts[0],
            "گزارش کانال از مسیر ربات هم استراتژی دارد")

    # ─── تست ۷: باگ «۵ کشتی ۱۰۰ ناو را نابود کرد» ───
    print("\n== TEST 7: تلفات متناسب با نیروی اعزامی (۵ کشتی ≠ نابودی ۱۰۰ ناو) ==")
    await db.execute("DELETE FROM player_assets WHERE user_id IN (101,102)")
    carrier = await equip_id("ناو هواپیمابر")
    if not carrier:
        carrier = await equip_id("ناو")
    ship = await equip_id("قایق تندرو") or frigate
    await add_asset(102, "equipment", carrier["id"], 100)     # انبار بزرگ مدافع
    await add_asset(102, "equipment", missile["id"], 30)
    await add_asset(101, "equipment", ship["id"], 5)          # تنها ۵ یگان مهاجم
    await add_asset(101, "equipment", carrier["id"], 40)      # ذخیره‌گاه بزرگ مهاجم
    def_ships_before = await qty(102, "equipment", carrier["id"])
    atk_reserve_before = await qty(101, "equipment", carrier["id"])

    war_id2 = await db.execute(
        "INSERT INTO wars(attacker_id, defender_id, reason, permission, status) VALUES(?,?,?,?,?)",
        (101, 102, "تست تلفات", 0, "active"))
    war2 = await db.fetchone("SELECT * FROM wars WHERE id=?", (war_id2,))
    H.SENT.clear()
    orig_random = random.random
    random.random = lambda: 0.01      # نبرد همیشه برده می‌شود (بدترین حالت برای مدافع)
    try:
        await resolve_battle(FakeCall(bot, 101), war2, {str(ship["id"]): 5}, "naval")
    finally:
        random.random = orig_random

    def_ships_after = await qty(102, "equipment", carrier["id"])
    atk_reserve_after = await qty(101, "equipment", carrier["id"])
    cap = await combat.defend_cap(101, 5)
    killed = def_ships_before - def_ships_after
    H.check(killed <= cap, f"تلفات مدافع در سقف نیروی اعزامی ماند ({killed} ≤ {cap})")
    H.check(killed < 20, f"۵ یگان مهاجر نتوانست ۱۰۰ ناو را نابود کند (نابودشده: {killed})")
    H.check(def_ships_after >= 80, f"ناوگان مدافع تقریباً سالم ماند ({def_ships_after} از ۱۰۰)")
    kept = atk_reserve_before - atk_reserve_after
    H.check(kept <= 4, f"ذخیره‌گاه مهاجم دست‌نخورده ماند (از دست رفته: {kept} از {atk_reserve_before})")
    rep = "\n".join(channel_texts())
    H.check(("یگان اعزامی" in rep or "یگانِ درگیر" in rep),
            "گزارش نبرد توضیح می‌دهد تلفات از یگان‌های اعزامی/درگیر است")

    print("\n=== TOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("   -", e)
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())

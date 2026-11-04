"""تست پنل ادمین داخل ربات بازی (/panel) + سوپرادمین‌های ثابت.

اجرا: /tmp/venv/bin/python tests/test_adminpanel.py   (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

SUPER1 = 8666501866
SUPER2 = 8358901937
PLAYER = 501
STRANGER = 502


async def money_of(uid: int) -> int:
    from core.db import db
    row = await db.fetchone("SELECT money, royal_coins FROM users WHERE id=?", (uid,))
    return int((row or {}).get("money") or 0), int((row or {}).get("royal_coins") or 0)


async def log_count() -> int:
    from core.db import db
    row = await db.fetchone("SELECT COUNT(*) c FROM admin_logs")
    return int(row["c"] if row else 0)


async def send_text(dp, bot, uid: int, text: str):
    await dp.feed_update(bot, H.msg_update(uid, text))


async def main():
    from core.db import db
    dp, bot = await H.new_game_dp()
    await H.make_world([(PLAYER, "بازیکن", 0), (STRANGER, "غریبه", 1)])

    # کاربر سوپرادمین را در جدول کاربران هم بسازیم (برای نمایش کارت)
    await db.execute("INSERT OR IGNORE INTO users(id, full_name, joined_at) VALUES(?,?,datetime('now'))",
                     (SUPER1, "سوپرادمین یک"))

    print("\n== TEST 1: ثبت خودکار سوپرادمین‌های ثابت ==")
    from core.config import DEFAULT_SUPER_ADMIN_IDS, SUPER_ADMIN_IDS
    from core.admins import ensure_super_admins, is_admin, is_super_admin
    H.check(SUPER1 in SUPER_ADMIN_IDS and SUPER2 in SUPER_ADMIN_IDS,
            f"هر دو آیدی در کانفیگ هستند {SUPER_ADMIN_IDS}")
    H.check(set(DEFAULT_SUPER_ADMIN_IDS) == {SUPER1, SUPER2}, "آیدی‌های پیش‌فرض درست است")
    await ensure_super_admins()
    rows = await db.fetchall("SELECT id, is_super FROM admins")
    ids = {int(r["id"]) for r in rows}
    H.check(SUPER1 in ids and SUPER2 in ids, "هر دو سوپرادمین در جدول admins ثبت شدند")
    H.check(all(int(r["is_super"]) == 1 for r in rows if int(r["id"]) in (SUPER1, SUPER2)),
            "هر دو is_super=1 دارند")
    H.check(await is_admin(SUPER1) and await is_super_admin(SUPER2), "دسترسی ادمین برای هر دو فعال است")
    H.check(not await is_admin(PLAYER), "بازیکن عادی ادمین نیست")

    print("\n== TEST 2: /panel فقط برای ادمین ==")
    H.SENT.clear()
    await send_text(dp, bot, PLAYER, "/panel")
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    H.check(any("مخصوص ادمین" in (t or "") for t in texts), "بازیکن عادی رد می‌شود")
    H.SENT.clear()
    await send_text(dp, bot, SUPER1, "/panel")
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    H.check(any("پنل مدیریت سریع" in (t or "") for t in texts), "سوپرادمین پنل را می‌بیند")
    H.check(any("سوپرادمین" in (t or "") for t in texts), "نقش سوپرادمین نمایش داده می‌شود")

    print("\n== TEST 3: واریز و برداشت پول ==")
    logs_before = await log_count()
    money_before, _ = await money_of(PLAYER)
    await dp.feed_update(bot, H.cb_update(SUPER1, "p|op|money_add"))
    await send_text(dp, bot, SUPER1, str(PLAYER))
    await send_text(dp, bot, SUPER1, "50m")
    money_after, _ = await money_of(PLAYER)
    H.check(money_after == money_before + 50_000_000,
            f"واریز ۵۰ میلیون انجام شد ({money_before:,}→{money_after:,})")

    await dp.feed_update(bot, H.cb_update(SUPER1, "p|op|money_sub"))
    await send_text(dp, bot, SUPER1, str(PLAYER))
    await send_text(dp, bot, SUPER1, "20m")
    money_after2, _ = await money_of(PLAYER)
    H.check(money_after2 == money_after - 20_000_000,
            f"برداشت ۲۰ میلیون انجام شد ({money_after:,}→{money_after2:,})")

    print("\n== TEST 4: سکه شاهی دادن و گرفتن ==")
    _, coins_before = await money_of(PLAYER)
    await dp.feed_update(bot, H.cb_update(SUPER2, "p|op|coin_add"))
    await send_text(dp, bot, SUPER2, str(PLAYER))
    await send_text(dp, bot, SUPER2, "25")
    _, coins_after = await money_of(PLAYER)
    H.check(coins_after == coins_before + 25, f"۲۵ سکه اضافه شد ({coins_before}→{coins_after})")

    await dp.feed_update(bot, H.cb_update(SUPER2, "p|op|coin_sub"))
    await send_text(dp, bot, SUPER2, str(PLAYER))
    await send_text(dp, bot, SUPER2, "10")
    _, coins_after2 = await money_of(PLAYER)
    H.check(coins_after2 == coins_after - 10, f"۱۰ سکه کم شد ({coins_after}→{coins_after2})")

    print("\n== TEST 5: عملیات دیگر (رضایت/دکل/بن/قفل) ==")
    await dp.feed_update(bot, H.cb_update(SUPER1, "p|op|sat_add"))
    await send_text(dp, bot, SUPER1, str(PLAYER))
    await send_text(dp, bot, SUPER1, "15")
    sat = (await db.fetchone("SELECT satisfaction FROM states WHERE user_id=?", (PLAYER,)))["satisfaction"]
    H.check(sat > 50, f"رضایت افزایش یافت ({round(sat)}/100)")

    await dp.feed_update(bot, H.cb_update(SUPER1, "p|op|rig_add"))
    await send_text(dp, bot, SUPER1, str(PLAYER))
    await send_text(dp, bot, SUPER1, "2")
    rig = await db.fetchone("SELECT a.quantity FROM player_assets a JOIN buildings b ON b.id=a.item_id "
                            "WHERE a.user_id=? AND b.name='دکل نفتی'", (PLAYER,))
    H.check(bool(rig) and int(rig["quantity"]) == 2, "۲ دکل نفتی اضافه شد")

    await dp.feed_update(bot, H.cb_update(SUPER1, "p|op|ban"))
    await send_text(dp, bot, SUPER1, str(STRANGER))
    banned = (await db.fetchone("SELECT banned FROM users WHERE id=?", (STRANGER,)))["banned"]
    H.check(int(banned) == 1, "کاربر مسدود شد")
    await dp.feed_update(bot, H.cb_update(SUPER1, "p|op|unban"))
    await send_text(dp, bot, SUPER1, str(STRANGER))
    banned = (await db.fetchone("SELECT banned FROM users WHERE id=?", (STRANGER,)))["banned"]
    H.check(int(banned) == 0, "مسدودی برداشته شد")

    await db.execute("UPDATE states SET leader_block_until='2099-01-01 00:00:00' WHERE user_id=?",
                     (PLAYER,))
    await dp.feed_update(bot, H.cb_update(SUPER1, "p|op|unlock"))
    await send_text(dp, bot, SUPER1, str(PLAYER))
    st = await db.fetchone("SELECT leader_block_until FROM states WHERE user_id=?", (PLAYER,))
    H.check(not st["leader_block_until"], "قفل رهبر آزاد شد")

    print("\n== TEST 6: تأیید فیش و تنظیمات ==")
    rid = await db.execute(
        "INSERT INTO receipts(user_id, kind, coins, toman, status) VALUES(?,?,?,?,'pending')",
        (PLAYER, "coins", 40, 0))
    _, coins_before_r = await money_of(PLAYER)
    await dp.feed_update(bot, H.cb_update(SUPER1, "p|rec"))
    await dp.feed_update(bot, H.cb_update(SUPER1, f"p|recok|{rid}"))
    _, coins_after_r = await money_of(PLAYER)
    status = (await db.fetchone("SELECT status FROM receipts WHERE id=?", (rid,)))["status"]
    H.check(status == "approved", "فیش تأیید شد")
    H.check(coins_after_r == coins_before_r + 40, f"سکهٔ فیش واریز شد ({coins_before_r}→{coins_after_r})")

    await dp.feed_update(bot, H.cb_update(SUPER1, "p|set|war_vote_minutes"))
    await send_text(dp, bot, SUPER1, "30")
    from core.db import get_setting
    H.check(await get_setting("war_vote_minutes", "") == "30", "تنظیمات سریع ذخیره شد")

    print("\n== TEST 7: هیچ لاگی در لاگ ادمین‌ها ثبت نشود ==")
    logs_after = await log_count()
    H.check(logs_after == logs_before,
            f"هیچ رکوردی به admin_logs اضافه نشد ({logs_before}→{logs_after})")
    events = await db.fetchone("SELECT COUNT(*) c FROM game_events")
    print(f"     (game_events = {events['c']} — مستقل از لاگ ادمین‌ها)")

    print("\n== TEST 8: کارت کاربر و پیام همگانی ==")
    await dp.feed_update(bot, H.cb_update(SUPER1, "p|op|card"))
    await send_text(dp, bot, SUPER1, str(PLAYER))
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(SUPER1, "p|bc"))
    await send_text(dp, bot, SUPER1, "📣 پیام آزمایشی")
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    H.check(any("پیام همگانی" in (t or "") for t in texts), "پیام همگانی ارسال شد")

    print("\n=== TOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("   -", e)
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())

"""تست نام بازی، تک‌ادمین بودن و ارسال اخبار به کانال.

اجرا: python3 tests/test_channel_admin.py      (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402


async def main():
    from core import config as cfg
    from core.db import db, get_setting, init_db, set_setting

    print("\n== TEST 1: نام بازی و کانال/گپ رسمی در کانفیگ ==")
    H.check(cfg.GAME_NAME == "جنگ جهانی ۳", f"نام بازی: {cfg.GAME_NAME}")
    H.check(cfg.OFFICIAL_GROUP == "@WordWarWord", f"گپ رسمی: {cfg.OFFICIAL_GROUP}")
    H.check(cfg.OFFICIAL_CHANNEL == "@Jangjhani313", f"کانال خبری: {cfg.OFFICIAL_CHANNEL}")
    H.check(set(cfg.OFFICIAL_CHANNELS) == {"@WordWarWord", "@Jangjhani313"},
            f"کانال‌های عضویت اجباری: {cfg.OFFICIAL_CHANNELS}")

    print("\n== TEST 2: فقط یک ادمین (۸۶۶۶۵۰۱۸۶۶) ==")
    H.check(cfg.DEFAULT_ADMIN_ID == 8666501866, "آیدی ادمین کل")
    H.check(cfg.DEFAULT_SUPER_ADMIN_IDS == (8666501866,), f"فقط یک سوپرادمین: {cfg.DEFAULT_SUPER_ADMIN_IDS}")
    H.check(8358901937 not in cfg.SUPER_ADMIN_IDS, "آیدی قدیمی در فهرست سوپرادمین‌ها نیست")
    H.check(8358901937 in cfg.LEGACY_ADMIN_IDS, "آیدی قدیمی در فهرست حذف قرار دارد")
    H.check(cfg.STRICT_SINGLE_ADMIN is True, "حالت تک‌ادمین فعال است")

    print("\n== TEST 3: پاکسازی خودکار ادمین‌های قدیمی در دیتابیس ==")
    await init_db()
    await db.execute("INSERT OR REPLACE INTO admins(id, name, is_super, perms) VALUES(?,?,1,'[]')",
                     (8358901937, "ادمین قدیمی"))
    await db.execute("INSERT OR REPLACE INTO admins(id, name, is_super, perms) VALUES(?,?,0,'[]')",
                     (555000111, "ادمین تستی"))
    from core.admins import ensure_super_admins
    await ensure_super_admins()
    rows = await db.fetchall("SELECT id, is_super FROM admins")
    ids = {int(r["id"]) for r in rows}
    H.check(8666501866 in ids, "ادمین کل حفظ شد")
    H.check(8358901937 not in ids, "ادمین قدیمی حذف شد")
    H.check(555000111 not in ids, "ادمین غیرمجاز (تک‌ادمین) حذف شد")

    print("\n== TEST 4: تنظیمات پیش‌فرض کانال در دیتابیس ==")
    await init_db()
    join = await get_setting("join_channels", "[]")
    H.check("@WordWarWord" in join and "@Jangjhani313" in join, f"عضویت اجباری: {join}")
    H.check(await get_setting("announcement_channel", "") == "@Jangjhani313",
            "کانال اعلانات روی @Jangjhani313")
    H.check(await get_setting("game_group", "") == "@WordWarWord", "گрупپ بازی روی @WordWarWord")
    start_text = await get_setting("start_text", "")
    H.check("جنگ جهانی ۳" in start_text, "متن /start نام بازی جدید را دارد")

    print("\n== TEST 4.5: مهاجرت مقادیر کهنهٔ دیتابیس در init_db ==")
    await set_setting("start_text", "به بازی «WORLD_WAR_FIRE» خوش آمدید!")
    await set_setting("season_name", "سیزن ۱ — جنگ جهانی")
    await init_db()
    H.check(await get_setting("start_text", "") == "", "متن استارت کهنه (WORLD_WAR_FIRE) پاک شد")
    H.check("جنگ جهانی ۳" in await get_setting("season_name", ""), "نام سیزن بهنگام شد")
    # متن دلخواه ادمین که نام قدیمی ندارد باید حفظ شود
    await set_setting("start_text", "🌍 سلام فرمانده، خوش آمدی!")
    await init_db()
    H.check(await get_setting("start_text", "") == "🌍 سلام فرمانده، خوش آمدی!",
            "متن دلخواه ادمین دست‌نخورده ماند")
    await set_setting("start_text", "")

    print("\n== TEST 5: اعلان کانال — هدر نام بازی + دکمهٔ ورود ==")
    dp, bot = await H.new_game_dp()
    await set_setting("announcement_channel", "@Jangjhani313")
    from core.economy import announce, announce_news
    H.SENT.clear()
    await announce(bot, "⚔️ ایران به عراق اعلان جنگ داد!", section="war_declare")
    H.check(len(H.SENT) > 0, f"خبر به کانال ارسال شد ({len(H.SENT)} پیام)")
    channel, text = None, ""
    for name, chat_id, msg_text, _photo in H.SENT:
        if str(chat_id) == "@Jangjhani313":
            channel, text = chat_id, msg_text or ""
    H.check(channel == "@Jangjhani313", "پیام به کانال خبری رفت")
    H.check("جنگ جهانی ۳" in text, "نام بازی در متن خبر هست")
    H.check("ایران به عراق" in text, "متن خبر دست‌نخورده مانده")

    H.SENT.clear()
    await announce_news(bot, "📰 وضعیت امروز جهان", ["👥 بازیکنان فعال: <b>7</b>"], "general")
    H.check(any(str(c) == "@Jangjhani313" for _n, c, _t, _p in H.SENT), "خبر وضعیت جهان ارسال شد")

    print("\n== TEST 6: بررسی سلامت کانال (check_channel) ==")
    from core.economy import check_channel, channel_target
    H.check(await channel_target() == "@Jangjhani313", "کانال هدف درست است")
    status = await check_channel(bot)
    H.check(isinstance(status, dict) and "ok" in status, f"خروجی بررسی کانال: {status.get('error') or 'ok'}")

    print("\n== TEST 6.5: منوی اصلی — دکمه‌های گپ/کانال از دیتابیس (نه هاردکد) ==")
    from gamebot.common import main_menu_kb
    async def menu_urls():
        kb_ = await main_menu_kb(is_admin=False)
        return [(b.text, b.url) for row in kb_.inline_keyboard for b in row if getattr(b, "url", None)]
    urls = await menu_urls()
    flat = " ".join(f"{t} {u}" for t, u in urls)
    H.check("https://t.me/WordWarWord" in flat, f"لینک گپ در منو: {flat[:90]}")
    H.check("https://t.me/Jangjhani313" in flat, "لینک کانال خبری در منو")
    H.check("worldwarFIRE" not in flat and "worldwarfire" not in flat, "هیچ لینک قدیمی در منو نیست")
    # تغییر تنظیمات باید فوراً در منو دیده شود
    await set_setting("game_group", "@AnotherGroup")
    urls2 = await menu_urls()
    flat2 = " ".join(f"{t} {u}" for t, u in urls2)
    H.check("https://t.me/AnotherGroup" in flat2, "تغییر game_group از پنل در منو اعمال شد")
    await set_setting("game_group", "@WordWarWord")
    # ربات ادمین: نام‌کاربری از کانفیگ
    from core import config as _cfg
    H.check(_cfg.ADMIN_BOT_USERNAME == "agfafagjganigagbot", f"نام ربات ادمین: {_cfg.ADMIN_BOT_USERNAME}")
    kb_admin = await main_menu_kb(is_admin=True)
    admin_urls = [b.url for row in kb_admin.inline_keyboard for b in row if getattr(b, "url", None)]
    H.check(any("agfafagjganigagbot" in (u or "") for u in admin_urls), "دکمهٔ پنل ادمین به ربات درست لینک است")
    H.check(not any("ADmminFIREWOrldBOT" in (u or "") for u in admin_urls), "لینک قدیمی پنل ادمین حذف شده")

    print("\n== TEST 6.8: فروشگاه سکه شاهی — فقط قیمت + آیدی پشتیبانی ==")
    from gamebot.handlers.misc import coin_shop_text, sales_support
    await db.execute("DELETE FROM coin_packages")
    for coins, price, disc in [(10, 10000, 0), (50, 47500, 5), (100, 90000, 10), (500, 425000, 15)]:
        await db.execute("INSERT INTO coin_packages(coins, price_toman, discount_percent, is_active) "
                         "VALUES(?,?,?,1)", (coins, price, disc))
    shop = await coin_shop_text(None)
    H.check(await sales_support() == "@MiddleEastDefendSupport", "آیدی پشتیبانی فروش")
    H.check("https://t.me/MiddleEastDefendSupport" in shop, "لینک پشتیبانی در متن")
    H.check("6037-9975-0764-0028" not in shop, "شماره کارت در متن نیست")
    H.check("کارت به کارت" not in shop, "هیچ اشاره‌ای به کارت به کارت نیست")
    H.check("محمد طاها" not in shop, "نام صاحب کارت حذف شد")
    H.check("10,000 تومان" in shop and "47,500 تومان" in shop
            and "90,000 تومان" in shop and "425,000 تومان" in shop, "هر چهار قیمت درست است")
    H.check("تخفیف 5٪" in shop and "تخفیف 10٪" in shop and "تخفیف 15٪" in shop, "درصد تخفیف‌ها درست است")
    # دکمه‌های حذف‌شده باید به فروشگاه هدایت شوند و هیچ کارتی نشان ندهند
    H.SENT.clear()
    for cb in ("g|coinbuy", "g|coinpkg", "g|coinconv", "g|coinhist"):
        await dp.feed_update(bot, H.cb_update(700001, cb))
    redirected = [t for _n, _c, t, _p in H.SENT if t]
    H.check(any("@MiddleEastDefendSupport" in (t or "") for t in redirected),
            "دکمه‌های خرید/تبدیل/فیش به فروشگاه با آیدی پشتیبانی می‌روند")
    H.check(not any("6037" in (t or "") or "کارت به کارت" in (t or "") for t in redirected),
            "هیچ‌کدام شماره کارت نشان نمی‌دهند")
    H.check(await get_setting("c2c_card", "") == "", "شماره کارت در تنظیمات خالی است")

    print("\n== TEST 7: دستور /testchannel در ربات ادمین ==")
    from adminbot.main import create_dispatcher as admin_dp_factory
    adp = admin_dp_factory()
    SENT_ADMIN = []
    orig = H.FakeBot.__call__

    async def capture(self, method, request_timeout=None):
        res = await orig(self, method, request_timeout)
        SENT_ADMIN.append((type(method).__name__, getattr(method, "text", "")))
        return res

    H.FakeBot.__call__ = capture
    try:
        H.SENT.clear()
        await adp.feed_update(bot, H.msg_update(8666501866, "/testchannel"))
        texts = [t for _n, t in SENT_ADMIN]
        H.check(any("کانال" in (t or "") for t in texts),
                f"پاسخ /testchannel برای ادمین ({str(texts)[:80]})")
        SENT_ADMIN.clear()
        await adp.feed_update(bot, H.msg_update(555777999, "/start"))
        texts = [t for _n, t in SENT_ADMIN]
        H.check(any("مدیریتی" in (t or "") or "ربات اصلی" in (t or "") for t in texts),
                "کاربر غیرادمین به ربات اصلی هدایت می‌شود (بدون دکمهٔ فعال‌سازی)")
        H.check(not any("فعال‌سازی" in (t or "") for t in texts), "دکمهٔ خودانتخابی ادمین حذف شده است")
    finally:
        H.FakeBot.__call__ = orig

    from core.db import db as _db
    await _db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        print("\n=== TOTAL ERRORS:", len(H.ERRORS))
        for e in H.ERRORS:
            print("  -", e)

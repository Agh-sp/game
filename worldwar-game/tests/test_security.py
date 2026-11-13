"""🛡 تست امنیت — آپدیت جعلی، وبهوک بی‌کلید، پنل وب بدون ورود، سوءاستفاده از همگانی.

اجرا: PAW_PROXY=0 python3 tests/test_security.py     (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

SUPER = 8666501866      # سوپرادمین ثابت کانفیگ
PLAIN_ADMIN = 870000123  # ادمین عادی (بدون is_super)
PLAYER = 870000456
ATTACKER = 870000789


async def main():
    from aiohttp.test_utils import TestClient, TestServer

    from core import security as sec
    from core.db import db, get_setting, init_db, set_setting
    import run_webhook as wh
    from adminbot.main import create_dispatcher as admin_dp_factory
    from gamebot.main import create_dispatcher as game_dp_factory

    await init_db()
    await sec.init_tables()

    # ─── کاربران تست ───
    for uid, name in ((SUPER, "سوپر"), (PLAIN_ADMIN, "ادمین عادی"),
                      (PLAYER, "بازیکن"), (ATTACKER, "مهاجم")):
        await db.execute("INSERT OR IGNORE INTO users(id, full_name) VALUES(?,?)", (uid, name))
    await db.execute("DELETE FROM admins WHERE id=?", (PLAIN_ADMIN,))
    await db.execute("INSERT OR REPLACE INTO admins(id, name, is_super, perms) VALUES(?,?,0,?)",
                     (PLAIN_ADMIN, "ادمین عادی", json.dumps(["broadcast", "settings"])))
    await set_setting("broadcast_lock_until", "")
    await set_setting("broadcast_require_code", "1")
    await set_setting("broadcast_max_recipients", "0")
    sec.reset_rate()

    gbot = H.FakeBot("42:GAME")
    H.BOT_REF["bot"] = gbot
    abot = H.FakeBot("43:ADMIN")
    gdp = game_dp_factory()
    adp = admin_dp_factory()
    gdp.errors.register(lambda e: (H.ERRORS.append(f"game: {e.exception}"), True)[1])
    adp.errors.register(lambda e: (H.ERRORS.append(f"admin: {e.exception}"), True)[1])

    # ═════════════════ ۱) وبهوک: کلید اجباری ═════════════════
    print("\n== TEST 1: وبهوک بدون کلید / با کلید غلط رد می‌شود ==")
    app = wh.create_app(gdp, gbot, adp, abot, secret="", base_url="http://localhost:9")
    forged = {
        "update_id": 91001,
        "message": {
            "message_id": 1, "date": 1700000000,
            "chat": {"id": SUPER, "type": "private"},
            "from": {"id": SUPER, "is_bot": False, "first_name": "Fake"},
            "text": "/panel",
        },
    }
    async with TestClient(TestServer(app)) as client:
        r = await client.post("/webhook/game", json=forged)
        H.check(r.status == 403, f"آپدیت جعلی بدون کلید رد شد ({r.status})")
        r = await client.post("/webhook/game", json=forged,
                              headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
        H.check(r.status == 403, f"کلید غلط رد شد ({r.status})")
        H.check(wh.STATS["game"]["rejected"] >= 2, "شمارندهٔ رد شدن‌ها زیاد شد")
        r = await client.post("/webhook/set", json={"baseUrl": "https://evil.example"})
        H.check(r.status == 403, f"تغییر وبهوک بدون کلید رد شد ({r.status})")
        r = await client.post("/webhook/delete")
        H.check(r.status == 403, f"حذف وبهوک بدون کلید رد شد ({r.status})")
    await db.connect()   # خاموشی سرویس وبهوک در تست، اتصال دیتابیس را می‌بندد

    # کلید درست + آپدیت تکراری
    app = wh.create_app(gdp, gbot, adp, abot, secret="k" * 24, base_url="http://localhost:9")
    async with TestClient(TestServer(app)) as client:
        headers = {"X-Telegram-Bot-Api-Secret-Token": "k" * 24}
        r = await client.post("/webhook/game", json=forged, headers=headers)
        H.check(r.status == 200, f"آپدیت با کلید درست پذیرفته شد ({r.status})")
        r2 = await client.post("/webhook/game", json=forged, headers=headers)
        body = await r2.json()
        H.check(body.get("duplicate") is True, "آپدیت تکراری (replay) دوباره اجرا نشد")
        H.check(wh.STATS["game"]["duplicates"] >= 1, "شمارندهٔ تکراری‌ها ثبت شد")
    await db.connect()

    # ═════════════════ ۲) کلید خودکار ═════════════════
    print("\n== TEST 2: اگر کلید تنظیم نشده باشد، خودکار ساخته می‌شود ==")
    os.environ.pop("WEBHOOK_SECRET", None)
    from core import config as cfg
    cfg.WEBHOOK_SECRET = ""
    from core.db import set_setting as _set
    await _set("webhook_secret", "")
    fresh, made = await sec.ensure_webhook_secret()
    H.check(len(fresh) >= 16, f"کلید ساخته شد (طول {len(fresh)})")
    H.check(made is True, "پرچم «تازه ساخته شد» درست است")
    again, made2 = await sec.ensure_webhook_secret()
    H.check(again == fresh and made2 is False, "بار دوم همان کلید برمی‌گردد (پایدار)")
    H.check(sec.secret_matches(fresh, fresh) and not sec.secret_matches(fresh, "x"),
            "مقایسهٔ کلید درست کار می‌کند")
    H.check(not sec.secret_matches("", ""), "کلید خالی هرگز تطبیق داده نمی‌شود")

    # ═════════════════ ۳) آپدیت‌های «غیرممکن» ═════════════════
    print("\n== TEST 3: آپدیت جعلی از طرف ربات / با تاریخ نامعتبر رد می‌شود ==")
    await db.connect()
    before_fail = len(await db.fetchall("SELECT id FROM security_events WHERE kind='auth_fail'"))
    H.SENT.clear()
    await gdp.feed_update(gbot, H.msg_update(ATTACKER, "/panel"))
    before = len(H.SENT)
    from aiogram.types import Chat, Message as TgMessage, Update, User as TgUser
    from datetime import datetime, timezone

    bot_msg = TgMessage(message_id=77, date=datetime.now(timezone.utc),
                        chat=Chat(id=SUPER, type="private"),
                        from_user=TgUser(id=555, is_bot=True, first_name="Evil"),
                        text="/start")
    await gdp.feed_update(gbot, Update(update_id=333, message=bot_msg.as_(gbot)))
    H.check(len(H.SENT) == before, "آپدیت از طرف یک ربات هیچ پاسخی نگرفت")

    stale = TgMessage(message_id=78, date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                      chat=Chat(id=SUPER, type="private"),
                      from_user=H.tg_uid(SUPER), text="/start")
    await gdp.feed_update(gbot, Update(update_id=334, message=stale.as_(gbot)))
    H.check(len(H.SENT) == before, "پیام با تاریخ ۲۰۲۰ رد شد")

    fake_private = TgMessage(message_id=79, date=datetime.now(timezone.utc),
                             chat=Chat(id=PLAYER, type="private"),
                             from_user=H.tg_uid(ATTACKER), text="/start")
    await gdp.feed_update(gbot, Update(update_id=335, message=fake_private.as_(gbot)))
    H.check(len(H.SENT) == before, "پیام خصوصی با chat/from ناسازگار رد شد")
    await db.connect()
    denied = await db.fetchall("SELECT * FROM security_events WHERE kind='auth_fail'")
    H.check(len(denied) >= before_fail + 3,
            f"همهٔ رد شدن‌ها لاگ شدند ({before_fail}→{len(denied)})")

    # ═════════════════ ۴) پنل وب: بدون ورود ═════════════════
    print("\n== TEST 4: پنل وب بدون نشست ۴۰۱/۳۰۳ می‌دهد ==")
    os.environ.pop("PANEL_PASSWORD", None)
    from webapp.server import create_app as create_web_app
    web_app = create_web_app(None, None, abot, None, autostart=False)
    async with TestClient(TestServer(web_app)) as client:
        r = await client.get("/api/secrets")
        H.check(r.status == 401, f"/api/secrets بدون ورود رد شد ({r.status})")
        r = await client.get("/api/users")
        H.check(r.status == 401, f"/api/users بدون ورود رد شد ({r.status})")
        r = await client.post("/api/users/1/adjust", json={"moneyDelta": 10 ** 9})
        H.check(r.status == 401, f"تغییر موجودی کاربر بدون ورود رد شد ({r.status})")
        r = await client.post("/api/bot-process/stop")
        H.check(r.status == 401, f"خاموش‌کردن ربات بدون ورود رد شد ({r.status})")
        r = await client.get("/health")
        H.check(r.status == 200, "سلامت سرویس همچنان عمومی است")
        r = await client.post("/api/panel/login", json={"password": "nope"})
        H.check(r.status == 401, "گذرواژهٔ اشتباه رد شد")
        pwd, _made = await sec.ensure_panel_password()
        r = await client.post("/api/panel/login", json={"password": pwd})
        body = await r.json()
        token = body.get("token", "")
        H.check(r.status == 200 and bool(token), "ورود با گذرواژهٔ درست کار می‌کند")
        r = await client.get("/api/secrets", headers={"Cookie": f"ww_panel={token}"})
        H.check(r.status == 200, f"با نشست معتبر دسترسی داده شد ({r.status})")
        r = await client.get("/api/panel/security", headers={"Cookie": f"ww_panel={token}"})
        sec_body = await r.json()
        H.check(r.status == 200 and "counts" in sec_body, "گزارش امنیتی پنل کار می‌کند")
        client.session.cookie_jar.clear()   # نشست معتبرِ ورود را دور بریزیم
        forged_cookie = f"{int(__import__('time').time()) + 3600}.deadbeef"
        r = await client.get("/api/secrets", headers={"Cookie": f"ww_panel={forged_cookie}"})
        H.check(r.status == 401, f"کوکی با امضای جعلی رد شد ({r.status})")
        expired = sec.sign_session(pwd, ttl=-10)
        r = await client.get("/api/secrets", headers={"Cookie": f"ww_panel={expired}"})
        H.check(r.status == 401, f"کوکی منقضی رد شد ({r.status})")
    await db.connect()

    # ═════════════════ ۵) پیام همگانی ═════════════════
    print("\n== TEST 5: پیام همگانی فقط با سوپرادمین + کد تأیید ==")
    from adminbot.handlers.broadcast import broadcast_guard

    ok, why = await broadcast_guard(PLAYER)
    H.check(not ok, f"کاربر عادی اجازهٔ همگانی ندارد ({why})")
    await db.execute("INSERT OR REPLACE INTO admins(id, name, is_super, perms) VALUES(?,?,0,?)",
                     (PLAIN_ADMIN, "ادمین عادی", json.dumps(["broadcast"])))
    ok, why = await broadcast_guard(PLAIN_ADMIN)
    H.check(not ok and "سوپرادمین" in why, "ادمین غیرسوپر هم اجازه ندارد")

    # قفل همگانی
    await sec.lock_broadcast(30, "تست")
    ok, why = await broadcast_guard(SUPER)
    H.check(not ok and "قفل" in why, "قفل ارسال همگانی اعمال شد")
    await sec.unlock_broadcast()
    ok, why = await broadcast_guard(SUPER)
    H.check(ok, "سوپرادمین با قفل باز اجازه دارد")

    sec.reset_rate()
    await set_setting("broadcast_max_per_hour", "1")
    await set_setting("broadcast_lock_until", "")

    # جریان کامل در ربات ادمین: متن → کد → ارسال
    print("\n   -- جریان ربات ادمین --")
    import adminbot.tools as admin_tools
    admin_tools._game_bot = gbot   # ارسال همگانی در تست باید از ربات جعلی رد شود
    H.SENT.clear()
    await adp.feed_update(abot, H.cb_update(SUPER, "a|bc"))
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    H.check(any("پیام همگانی" in (t or "") for t in texts), "ورود به جریان همگانی")
    H.SENT.clear()
    await adp.feed_update(abot, H.msg_update(SUPER, "سلام به همه <script>"))
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    preview = " ".join(t for t in texts if t)
    H.check("کد تأیید" in preview, "کد تأیید درخواست شد")
    H.check("<script>" not in preview, "تگ خطرناک از متن حذف شد")
    H.SENT.clear()
    await adp.feed_update(abot, H.msg_update(SUPER, "0000"))
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    H.check(any("اشتباه" in (t or "") for t in texts), "کد اشتباه رد شد")

    code = sec.make_code(SUPER, "پیام تست امنیتی")
    H.SENT.clear()
    await adp.feed_update(abot, H.msg_update(SUPER, code))
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    H.check(any("تمام شد" in (t or "") for t in texts), "با کد درست ارسال انجام شد")
    H.check(any(c == PLAYER for (_n, c, _t, _p) in H.SENT), "پیام به بازیکن رسید")
    logged = await db.fetchone(
        "SELECT * FROM security_events WHERE kind='broadcast' ORDER BY id DESC LIMIT 1")
    H.check(bool(logged), "ارسال همگانی در لاگ امنیتی ثبت شد")

    # سقف نرخ: بعد از یک ارسال واقعی، ارسال دوم در همان ساعت باید رد شود
    ok3, why3 = await broadcast_guard(SUPER)
    H.check(not ok3 and "سقف" in why3, f"سقف یک ارسال در ساعت اعمال شد ({why3})")
    await set_setting("broadcast_max_per_hour", "5")
    sec.reset_rate()

    # ادمین غیرسوپر نمی‌تواند
    H.SENT.clear()
    await adp.feed_update(abot, H.cb_update(PLAIN_ADMIN, "a|bc"))
    alerts = [t for (_n, _c, t, _p) in H.SENT if t]
    H.check(any("سوپرادمین" in (t or "") for t in alerts), "ادمین غیرسوپر رد شد")

    # ═════════════════ ۶) پنل امنیتی ═════════════════
    print("\n== TEST 6: پنل امنیت ربات ادمین ==")
    sec.reset_rate()
    H.SENT.clear()
    await adp.feed_update(abot, H.cb_update(SUPER, "a|sec"))
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    shown = texts[-1] if texts else ""
    H.check("امنیت" in shown, "صفحهٔ امنیت باز شد")
    H.check("ارسال همگانی" in shown, "وضعیت قفل همگانی نمایش داده شد")

    H.SENT.clear()
    await adp.feed_update(abot, H.cb_update(SUPER, "a|sec|lock"))
    H.check(await sec.broadcast_lock_active(), "قفل از پنل امنیت فعال شد")
    await adp.feed_update(abot, H.cb_update(SUPER, "a|sec|open"))
    H.check(not await sec.broadcast_lock_active(), "قفل از پنل امنیت باز شد")

    old_secret, _ = await sec.ensure_webhook_secret()
    H.SENT.clear()
    await adp.feed_update(abot, H.cb_update(SUPER, "a|sec|rot"))
    new_secret = await get_setting("webhook_secret", "")
    H.check(new_secret and new_secret != old_secret, "کلید وبهوک چرخانده شد")

    H.SENT.clear()
    await adp.feed_update(abot, H.cb_update(SUPER, "a|sec|pwd"))
    pwd = await get_setting("panel_password", "")
    H.check(len(pwd) >= 8, f"گذرواژهٔ پنل بازسازی شد (طول {len(pwd)})")

    # ═════════════════ ۷) متن و جست‌وجوی SQL ═════════════════
    print("\n== TEST 7: پاک‌سازی متن و نام جدول ==")
    dirty = "سلام\u202e کشیده\u200b <b>بولد</b> <iframe>"
    clean, warns = sec.sanitize_text(dirty)
    H.check("\u202e" not in clean and "\u200b" not in clean, "نویسه‌های کنترلی حذف شدند")
    H.check("<b>" in clean and "<iframe>" not in clean, "فقط تگ‌های مجاز ماندند")
    H.check(bool(warns), "هشدارهای پاک‌سازی برگشتند")
    from webapp import data_service
    bad_table = data_service.read_table("settings; DROP TABLE users")
    H.check("error" in bad_table, "نام جدول مخرب رد شد")

    # ═════════════════ ۸) مقدارهای محرمانه در جدول settings ═════════════════
    print("\n== TEST 8: مقدارهای محرمانه علامت‌گذاری و پنهان می‌شوند ==")
    sec_setting = await db.fetchone("SELECT * FROM settings WHERE key='webhook_secret'")
    H.check(bool(sec_setting) and int(sec_setting["secret"] or 0) == 1,
            "کلید وبهوک در تنظیمات «محرمانه» علامت خورد")
    pwd_setting = await db.fetchone("SELECT * FROM settings WHERE key='panel_password'")
    H.check(bool(pwd_setting) and int(pwd_setting["secret"] or 0) == 1,
            "گذرواژهٔ پنل هم محرمانه است")

    sec.reset_rate()
    await set_setting("broadcast_lock_until", "")
    print("\n=== TOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("   -", e)
    await db.close()


asyncio.run(main())

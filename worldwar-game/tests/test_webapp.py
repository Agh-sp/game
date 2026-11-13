"""تست سرور وب پایتونی (جایگزین server.ts) — بدون نیاز به تلگرام یا Node.

اجرا: python3 tests/test_webapp.py       (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402


async def main():
    from aiohttp.test_utils import TestClient, TestServer

    from core.db import db, init_db
    from webapp import config_service, data_service
    from webapp.server import create_app

    await init_db()
    dp, bot = await H.new_game_dp()
    app = create_app(bot, dp, None, None, autostart=False)
    # 🔐 پنل حالا پشت ورود است: در تست با همان گذرواژهٔ ساخته‌شده وارد می‌شویم
    from core import security as sec
    os.environ.pop("PANEL_PASSWORD", None)
    pwd, _fresh = await sec.ensure_panel_password()

    async with TestClient(TestServer(app)) as client:
        H.check((await client.get("/api/secrets")).status == 401,
                "بدون ورود، /api/secrets قفل است")
        r = await client.post("/api/panel/login", json={"password": "wrong-password"})
        H.check(r.status == 401, "گذرواژهٔ اشتباه رد می‌شود")
        r = await client.post("/api/panel/login", json={"password": pwd})
        H.check(r.status == 200 and (await r.json()).get("success") is True, "ورود به پنل")

        print("\n== TEST 1: /health و /api/health ==")
        r = await client.get("/health")
        data = await r.json()
        H.check(r.status == 200 and data["status"] == "ok", "GET /health → 200 ok")
        H.check(data.get("runtime") == "python", "سرویس با پایتون اجرا می‌شود")
        H.check("botRunning" in data and "keepalive" in data and "webhook" in data,
                "فیلدهای سلامت کامل هستند")
        r2 = await client.get("/api/health")
        H.check(r2.status == 200, "GET /api/health کار می‌کند")
        r3 = await client.head("/health")
        H.check(r3.status == 200, "HEAD /health کار می‌کند")

        print("\n== TEST 2: /api/secrets (توکن‌ها و آیدی ادمین ثابت) ==")
        r = await client.get("/api/secrets")
        s = (await r.json())["configured"]
        H.check(s["rawGameToken"].startswith("9201202722:"), f"توکن ربات بازی ثبت شده ({s['GAME_BOT_TOKEN']})")
        H.check(s["rawAdminToken"].startswith("9000162449:"), f"توکن ربات ادمین ثبت شده ({s['ADMIN_BOT_TOKEN']})")
        from core.config import DEFAULT_ADMIN_ID, SUPER_ADMIN_IDS
        H.check(str(DEFAULT_ADMIN_ID) in [str(i) for i in SUPER_ADMIN_IDS],
                f"آیدی ادمین کل {DEFAULT_ADMIN_ID} در فهرست سوپرادمین‌هاست {SUPER_ADMIN_IDS}")
        H.check(DEFAULT_ADMIN_ID == 8666501866, f"آیدی ادمین کل ثبت‌شده {DEFAULT_ADMIN_ID}")
        H.check(":" not in s["GAME_BOT_TOKEN"], "توکن در فیلد نمایشی ماسک شده است")

        print("\n== TEST 3: مدیریت کاربران (CRUD کامل) ==")
        new_user = {"id": 880001, "username": "webuser", "full_name": "کاربر وب",
                    "money": 12345, "royal_coins": 7}
        r = await client.post("/api/users", json=new_user)
        res = await r.json()
        H.check(res.get("success") is True, "افزودن کاربر از پنل")
        r = await client.get("/api/users/880001")
        user = await r.json()
        H.check(user["money"] == 12345 and user["royal_coins"] == 7, "مقادیر کاربر ذخیره شد")
        r = await client.put("/api/users/880001", json={"full_name": "نام ویرایش‌شده", "money": 999})
        H.check((await r.json()).get("success") is True, "ویرایش کاربر")
        user = await (await client.get("/api/users/880001")).json()
        H.check(user["full_name"] == "نام ویرایش‌شده" and user["money"] == 999, "ویرایش اعمال شد")
        r = await client.post("/api/users/880001/adjust", json={"moneyDelta": 1000, "coinsDelta": 3})
        H.check((await r.json()).get("success") is True, "تنظیم سریع موجودی")
        user = await (await client.get("/api/users/880001")).json()
        H.check(user["money"] == 1999 and user["royal_coins"] == 10, "موجودی درست تغییر کرد")
        r = await client.post("/api/users/880001/ban")
        b = await r.json()
        H.check(b.get("banned") == 1, "مسدودسازی کاربر")
        r = await client.post("/api/users/880001/admin", json={"name": "x", "isSuper": False})
        a = await r.json()
        H.check(a.get("is_admin") == 1, "دادن دسترسی ادمین")
        r = await client.get("/api/users")
        users = await r.json()
        H.check(any(u["id"] == 880001 for u in users), "کاربر در لیست پنل دیده می‌شود")
        r = await client.delete("/api/users/880001")
        H.check((await r.json()).get("success") is True, "حذف کاربر")
        r = await client.get("/api/users/880001")
        H.check(r.status == 404, "کاربر حذف‌شده 404 می‌دهد")

        print("\n== TEST 4: کشورها، فراداده بازی و شبیه‌ساز نبرد ==")
        countries = await (await client.get("/api/countries")).json()
        H.check(isinstance(countries, list) and len(countries) >= 40, f"{len(countries)} کشور برگشت")
        meta = await (await client.get("/api/game/metadata")).json()
        H.check(meta["runtime"]["language"] == "python", "فراداده زبان پایتون را نشان می‌دهد")
        H.check(8666501866 in meta["quickPanel"]["superAdminIds"] or meta["runtime"]["superAdminId"],
                "آیدی ادمین در فراداده درست است")
        battle = await (await client.post("/api/simulate/battle", json={
            "attacker": {"attackPower": 9000, "cyberPower": 2000, "treasury": 1000},
            "defender": {"defensePower": 1000, "cyberPower": 10, "treasury": 200000000},
        })).json()
        H.check(battle["isVictory"] is True and battle["spoilsOfWarMoney"] == 30_000_000,
                "شبیه‌ساز نبرد غنیمت ۱۵٪ خزانه را حساب می‌کند")

        print("\n== TEST 5: آمار دیتابیس و خواندن فایل پروژه ==")
        stats = await (await client.get("/api/db/stats")).json()
        H.check(stats["tableCount"] > 10, f"{stats['tableCount']} جدول در دیتابیس")
        table = await (await client.get("/api/db/table/users")).json()
        H.check("columns" in table, "خواندن جدول users")
        r = await client.get("/api/files/read", params={"path": "core/config.py"})
        f = await r.json()
        H.check(f.get("type") == "file" and "DEFAULT_ADMIN_ID" in f.get("content", ""),
                "خواندن فایل سورس پروژه")
        r = await client.get("/api/files/read", params={"path": "../../etc/passwd"})
        H.check(r.status in (403, 404), "دسترسی خارج از پروژه بلاک می‌شود")

        print("\n== TEST 6: پروسهٔ ربات‌ها و پینگ بیدارباش ==")
        st = await (await client.get("/api/bot-process/status")).json()
        H.check("isRunning" in st and "watchdog" in st, "وضعیت پروسهٔ ربات‌ها")
        logs = await (await client.get("/api/bot-process/logs")).json()
        H.check(isinstance(logs.get("logs"), list), "لاگ ربات‌ها برگشت")
        ka = await (await client.get("/api/keepalive")).json()
        H.check("intervalMinutes" in ka, "وضعیت پینگ بیدارباش")

        print("\n== TEST 7: وبهوک (بدون تماس واقعی با تلگرام) ==")
        wb = await (await client.get("/api/webhook/status")).json()
        H.check("relay" in wb and "telegram" in wb, "وضعیت وبهوک")
        r = await client.post("/webhook/game", json={"update_id": 1})
        tw = await client.get("/api/webhook/status")
        tw_body = await tw.json()
        H.check(tw.status == 200 and r.status == 403,
                f"آپدیت بدون کلید معتبر رد می‌شود ({r.status})")
        H.check("relay" in tw_body, "وضعیت وبهوک")
        r = await client.post("/api/webhook/mode", json={"mode": "nonsense"})
        H.check(r.status == 400, "حالت نامعتبر وبهوک رد می‌شود")

        print("\n== TEST 8: صفحهٔ پنل و مشتری React ==")
        r = await client.get("/")
        H.check(r.status == 200 and "text/html" in r.headers.get("Content-Type", ""),
                "صفحهٔ اصلی پنل سرو می‌شود")
        r = await client.get("/some/spa/route")
        H.check(r.status == 200, "مسیرهای SPA به index.html برمی‌گردند")

    print("\n== TEST 9: ذخیرهٔ تنظیمات در .env ==")
    tmp = tempfile.mkdtemp()
    original_env = config_service.ENV_PATH
    config_service.ENV_PATH = __import__("pathlib").Path(tmp) / ".env"
    try:
        config_service.write_env_file({"GAME_BOT_TOKEN": "123:abc", "ADMIN_BOT_TOKEN": "456:def",
                                       "SUPER_ADMIN_ID": "999"})
        parsed = config_service.parse_env_file(config_service.ENV_PATH)
        H.check(parsed.get("GAME_BOT_TOKEN") == "123:abc", "نوشتن توکن در .env")
        H.check(parsed.get("SUPER_ADMIN_ID") == "999", "نوشتن آیدی ادمین در .env")
        H.check(parsed.get("DB_PATH", "").endswith("wwgame.db"), "مسیر دیتابیس در .env ثبت شد")
    finally:
        config_service.ENV_PATH = original_env
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n== TEST 10: تست توکن نامعتبر (بدون شبکه) ==")
    bad = config_service.check_telegram_token("not-a-token")
    H.check(bad.get("ok") is False, "توکن بدشکل رد می‌شود")

    from core.db import db as _db
    await _db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        print("\n=== TOTAL ERRORS:", len(H.ERRORS))
        for e in H.ERRORS:
            print("  -", e)

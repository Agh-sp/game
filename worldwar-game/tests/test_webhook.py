"""تست سرویس Webhook و /health (بدون نیاز به تلگرام یا توکن واقعی)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import *  # noqa  (محیط تست، FakeBot، ابزارها)


async def run():
    from core.db import db, init_db
    await init_db()
    from aiohttp.test_utils import TestClient, TestServer
    import run_webhook as wh
    from gamebot.main import create_dispatcher as game_dp_factory
    from adminbot.main import create_dispatcher as admin_dp_factory

    await db.execute("INSERT OR IGNORE INTO users(id, full_name) VALUES(1001,'A')")
    bot = FakeBot("42:GAME")
    BOT_REF["bot"] = bot
    adp_bot = FakeBot("43:ADMIN")
    dp = game_dp_factory()
    adp = admin_dp_factory()
    dp.errors.register(lambda e: (ERRORS.append(f"game: {e.exception}"), True)[1])
    adp.errors.register(lambda e: (ERRORS.append(f"admin: {e.exception}"), True)[1])

    print("\n== TEST 1: /health ==")
    app = wh.create_app(dp, bot, adp, adp_bot, secret="s3cr3t", base_url="")
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/health")
        data = await r.json()
        print("   ", {k: data[k] for k in ("status", "mode", "uptime")})
        check(r.status == 200 and data["status"] == "ok", "GET /health → 200 ok")
        check(data["bots"]["game"]["configured"] and data["bots"]["admin"]["configured"],
              "both bots reported as configured")
        check(data["webhook"]["secret_set"] is True, "secret reported set")
        check(data["keepalive"]["interval_minutes"] == 10, "keepalive interval = 10 minutes")
        r2 = await client.get("/api/health")
        check(r2.status == 200, "GET /api/health alias works")
        r3 = await client.head("/health")
        check(r3.status == 200, "HEAD /health works (uptime pingers)")

        print("\n== TEST 2: webhook secret ==")
        bad = await client.post("/webhook/game", json={"update_id": 1})
        check(bad.status == 403, f"wrong secret rejected ({bad.status})")
        good = await client.post("/webhook/game", json={"update_id": 1},
                                 headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
        check(good.status == 200, "valid secret accepted")
        broken = await client.post("/webhook/admin", data="notjson",
                                   headers={"Content-Type": "application/json",
                                            "X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
        check(broken.status == 400, f"invalid body rejected ({broken.status})")

        print("\n== TEST 3: real update reaches the dispatcher ==")
        SENT.clear()
        update = {
            "update_id": 5,
            "message": {
                "message_id": 1,
                "date": 1700000000,
                "chat": {"id": 1001, "type": "private"},
                "from": {"id": 1001, "is_bot": False, "first_name": "A"},
                "text": "/start",
            },
        }
        r = await client.post("/webhook/game", json=update,
                              headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
        body = await r.json()
        check(r.status == 200 and body.get("ok"), "update accepted")
        check(len(SENT) > 0, f"bot answered the /start through the webhook ({len(SENT)} calls)")
        stats = (await (await client.get("/health")).json())["bots"]["game"]
        check(stats["updates"] >= 1, f"update counter incremented ({stats['updates']})")

        print("\n== TEST 4: keep-alive ping ==")
        ok = await wh.ping_once(str(client.server.make_url("")).rstrip("/"))
        check(ok is True, "ping_once hits /health successfully")
        check(wh.STATS["keepalive"]["count"] >= 1, "keepalive stats recorded")

        print("\n== TEST 4b: bot keep-alive helper ==")
        from core.keepalive import ping_once, resolve_webapp_url, keepalive_minutes
        bot_ok = await ping_once(str(client.server.make_url("")).rstrip("/"))
        check(bot_ok is True, "core.keepalive.ping_once reaches /health")
        os.environ["WEBAPP_URL"] = "https://example.test/"
        check(resolve_webapp_url() == "https://example.test", f"WEBAPP_URL resolves ({resolve_webapp_url()})")
        os.environ["KEEPALIVE_MINUTES"] = "10"
        check(keepalive_minutes() == 10, "KEEPALIVE_MINUTES default = 10")
        os.environ.pop("WEBAPP_URL", None)

        print("\n== TEST 5: webhook set/delete without a public URL ==")
        r = await client.post("/webhook/set", headers={"Host": "example.test"})
        body = await r.json()
        check("results" in body, f"set endpoint responds ({list(body)})")

    print("\n== TEST 6: no-secret mode still accepts updates ==")
    app2 = wh.create_app(dp, bot, None, None, secret="", base_url="http://localhost:9")
    async with TestClient(TestServer(app2)) as client:
        r = await client.post("/webhook/game", json={"update_id": 9})
        check(r.status == 200, "update accepted without a secret")
        r = await client.get("/webhook/info")
        data = await r.json()
        check("game" in data, f"webhook info endpoint responds ({data.get('game')})")

    await db.close()
    print("\n=== TOTAL ERRORS:", len(ERRORS))
    for e in ERRORS:
        print("  -", e)


asyncio.run(run())

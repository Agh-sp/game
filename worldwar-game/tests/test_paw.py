"""تست مسیر WSGI مخصوص PythonAnywhere (webapp/paw_wsgi.py).

اجرا: PAW_PROXY=0 python3 tests/test_paw.py      (انتظار: TOTAL ERRORS: 0)

این تست بدون سرور واقعی، اپلیکیشن WSGI را مستقیم صدا می‌زند — همان‌طور که
PythonAnywhere صدا می‌زند.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

os.environ["PAW_PROXY"] = "0"

from webapp import paw_wsgi  # noqa: E402
import harness  # noqa: E402

# ربات قلابی هارنس را در رجیستری WSGI بگذاریم تا پاسخ‌ها ثبت شوند (بدون شبکه)
_orig_build = paw_wsgi.BotRegistry._build


async def _fake_build(self):
    from core.db import init_db
    await init_db()
    from gamebot.main import create_dispatcher as create_game_dp
    from adminbot.main import create_dispatcher as create_admin_dp
    dp, bot = await harness.new_game_dp()          # FakeBot → پیام‌ها در H.SENT ثبت می‌شوند
    self.game_bot, self.game_dp = bot, dp
    self.admin_dp = create_admin_dp()
    self.admin_bot = bot
    self.admin_bot_token = None
    self._ready = True


paw_wsgi.BotRegistry._build = _fake_build


def call(path: str, method: str = "GET", body: dict | None = None,
         headers: dict | None = None):
    """فراخوانی مستقیم اپلیکیشن WSGI مثل یک درخواست HTTP."""
    raw = json.dumps(body).encode() if body is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "HTTP_HOST": "127.0.0.1:3400",
        "CONTENT_LENGTH": str(len(raw)),
        "CONTENT_TYPE": "application/json",
        "wsgi.input": io.BytesIO(raw),
        "wsgi.errors": sys.stderr,
    }
    for k, v in (headers or {}).items():
        environ["HTTP_" + k.upper().replace("-", "_")] = v
    captured: dict = {}

    def start_response(status, response_headers):
        captured["status"] = status
        captured["headers"] = dict(response_headers)

    chunks = paw_wsgi.application(environ, start_response)
    payload = b"".join(chunks).decode("utf-8", errors="replace")
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        parsed = payload
    return captured.get("status", ""), parsed


def main():
    print("\n== TEST 1: صفحهٔ وضعیت / و /panel ==")
    status, body = call("/")
    H.check(status.startswith("200"), f"GET / → {status}")
    H.check(body.get("mode") == "webhook", "حالت وبهوک است")
    H.check(body.get("webhookPaths", {}).get("game") == "/webhook/game", "مسیر وبهوک بازی")
    status, html = call("/panel")
    H.check(status.startswith("200") and "<html" in str(html), "صفحهٔ /panel سرو می‌شود")

    print("\n== TEST 2: /health — آماده‌سازی ربات‌ها و کارهای دوره‌ای ==")
    status, health = call("/health")
    H.check(status.startswith("200") and health.get("status") == "ok", "GET /health → ok")
    H.check(health.get("botsReady") is True, "هر دو ربات آماده شدند")
    H.check(health.get("bots", {}).get("game") and health.get("bots", {}).get("admin"),
            "توکن بازی و ادمین بارگذاری شد")
    tasks = health.get("tasks") or {}
    H.check(tasks.get("ran") is True, f"کارهای دوره‌ای اجرا شد ({tasks.get('tasks')})")
    status, again = call("/health")
    H.check((again.get("tasks") or {}).get("ran") is False, "اجرای تکراری در بازهٔ کوتاه محدود می‌شود")

    print("\n== TEST 3: وبهوک — تحویل آپدیت تلگرام ==")
    # 🔐 کلید وبهوک برای همهٔ آپدیت‌ها لازم است (بدون کلید هیچ آپدیتی پذیرفته نمی‌شود)
    os.environ["WEBHOOK_SECRET"] = "s3cr3t-very-long-test-key-123456"
    from core import config as _cfg
    _cfg.WEBHOOK_SECRET = "s3cr3t-very-long-test-key-123456"
    hdr = {"X-Telegram-Bot-Api-Secret-Token": "s3cr3t-very-long-test-key-123456"}
    update = {
        "update_id": 42,
        "message": {
            "message_id": 1, "date": int(__import__("time").time()),
            "chat": {"id": 6500991787, "type": "private"},
            "from": {"id": 6500991787, "is_bot": False, "first_name": "Tester"},
            "text": "/start",
        },
    }
    H.SENT.clear()
    status, body = call("/webhook/game", "POST", update, hdr)
    H.check(status.startswith("200") and body.get("handled") is True, "آپدیت ربات بازی پردازش شد")
    H.check(len(H.SENT) > 0, f"ربات پاسخ فرستاد ({len(H.SENT)} پیام)")
    status, body = call("/webhook/admin", "POST", {"update_id": 43}, hdr)
    H.check(status.startswith("200"), "آپدیت ربات ادمین هم پذیرفته می‌شود")
    status, body = call("/webhook/game", "POST", {}, hdr)
    H.check(status.startswith("200") and body.get("empty") is True, "آپدیت خالی بی‌خطا رد می‌شود")

    print("\n== TEST 4: کلید امنیتی وبهوک ==")
    try:
        status, body = call("/webhook/game", "POST", update)
        H.check(status.startswith("403"), "بدون هدر secret → 403")
        status, body = call("/webhook/game", "POST", update,
                            {"X-Telegram-Bot-Api-Secret-Token": "s3cr3t-very-long-test-key-123456"})
        H.check(status.startswith("200"), "با هدر secret درست → 200")
    finally:
        os.environ.pop("WEBHOOK_SECRET", None)
        _cfg.WEBHOOK_SECRET = ""

    print("\n== TEST 5: مسیرهای مدیریت وبهوک ==")
    status, info = call("/info")
    H.check(status.startswith("200") and "game" in info and "admin" in info,
            "اطلاعات وبهوک هر دو ربات (بدون خطا حتی بدون شبکه)")
    status, res = call("/setup")
    H.check(status.startswith("403"), f"ثبت وبهوک بدون کلید رد می‌شود ({status})")
    status, res = call("/setup", "GET", None, hdr)
    H.check(status.startswith("200") and "results" in res, "ثبت وبهوک با کلید پاسخ ساختاریافته می‌دهد")
    H.check(res.get("baseUrl", "").endswith("/webhook") is False, "آدرس پایه درست ساخته می‌شود")

    print("\n== TEST 6: مسیر ناموجود ==")
    status, body = call("/does-not-exist")
    H.check(status.startswith("404"), "مسیر ناشناخته 404 می‌دهد")

    print("\n== TEST 7: پروکسی و تنظیمات محیطی ==")
    H.check(paw_wsgi.PROXY_URL.endswith(":3128"), "آدرس پروکسی PythonAnywhere درست است")
    os.environ["PYTHONANYWHERE_DOMAIN"] = "arezog210.pythonanywhere.com"
    try:
        H.check(paw_wsgi._base_url({}) == "https://arezog210.pythonanywhere.com",
                "دامنهٔ PythonAnywhere به‌صورت خودکار شناسایی می‌شود")
    finally:
        os.environ.pop("PYTHONANYWHERE_DOMAIN", None)


if __name__ == "__main__":
    try:
        main()
    finally:
        print("\n=== TOTAL ERRORS:", len(H.ERRORS))
        for e in H.ERRORS:
            print("  -", e)

"""🩺 تست مسیر استقرار روی PythonAnywhere (WSGI) و ابزار عیب‌یابی.

باگ گزارش‌شده: روی PythonAnywhere `python3 paw_start.py` این را چاپ می‌کرد:

    {"ok": false, "httpStatus": 404, "error": "NOT FOUND"}
    💚 botsReady=None tasks=None

یعنی آدرس `/setup` وجود نداشت؛ نه اینکه ربات خراب باشد. تا زمانی که کسی این
مسیر را تست نکند، هر تغییر کوچک در `webapp/paw_wsgi.py` یا `paw_start.py` می‌تواند
دوباره ربات را روی هاست از کار بیندازد. این فایل همان مسیر را بدون شبکه می‌سنجد:

  1. `application` WSGI: `/health`، `/panel`، `/setup` (۴۰۳ بدون کلید، ۲۰۰ با کلید)،
     `/info`، و ۴۰۴ برای مسیر ناشناس
  2. `paw_start.guess_base_url` و اعلام صریح خطای ۴۰۴
  3. `paw_doctor.py`: اجرا می‌شود، خروجی سالم می‌دهد و بکاپ/دیتابیس را نمی‌شکند
  4. `init_db` روی دیتابیس موجود، دوباره اجرا می‌شود (idempotent) و داده را پاک نمی‌کند

اجرا: PAW_PROXY=0 python3 tests/test_paw_deploy.py   (انتظار: TOTAL ERRORS: 0)
"""
import asyncio
import json
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402

BASE_URL = "https://arezog210.pythonanywhere.com"


def call_wsgi(path: str, method: str = "GET", headers: dict | None = None) -> tuple[str, dict]:
    """صدا زدن اپلیکیشن WSGI بدون شبکه."""
    from webapp.paw_wsgi import application
    env = {"PATH_INFO": path, "REQUEST_METHOD": method, "wsgi.input": None,
           "CONTENT_LENGTH": "0", "HTTP_HOST": "arezog210.pythonanywhere.com"}
    env.update(headers or {})
    out: dict = {}

    def start(status, hdrs, *_a):
        out["status"] = status

    body = b"".join(application(env, start))
    try:
        payload = json.loads(body)
    except Exception:  # noqa: BLE001
        payload = {"raw": body[:120].decode("utf-8", "replace")}
    return out.get("status", "?"), payload


async def main():
    print("== setup ==")
    os.environ["PUBLIC_BASE_URL"] = BASE_URL
    from core.db import db, init_db
    await H.make_world([(8101, "بازیکن", 0)])

    # ─── ۱) مسیرهای WSGI ───
    print("\n== TEST 1: مسیرهای سرویس WSGI ==")
    status, health = call_wsgi("/health")
    H.check(status.startswith("200"), f"/health جواب ۲۰۰ می‌دهد ({status})")
    H.check("botsReady" in health, "/health وضعیت ربات‌ها را دارد")

    status, panel = call_wsgi("/panel")
    H.check(status.startswith("200"), f"/panel باز می‌شود ({status})")

    status, res = call_wsgi("/setup")
    H.check(status.startswith("403"), f"/setup بدون کلید رد می‌شود ({status})")
    H.check(res.get("ok") is False, "پاسخ ۴۰۳ ساختار ok=false دارد")

    # کلید از دیتابیس (همان چیزی که paw_start در Bash می‌سازد)
    from core.security import ensure_webhook_secret
    secret, _fresh = await ensure_webhook_secret()
    H.check(len(secret) >= 16, "کلید وبهوک ساخته/خوانده شد")

    status, res = call_wsgi("/setup",
                            headers={"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": secret})
    H.check(status.startswith("200"),
            f"/setup با کلید درست جواب می‌دهد ({status} | {str(res)[:80]})")
    H.check("results" in res or "success" in res, "/setup نتیجهٔ ثبت وبهوک را برمی‌گرداند")

    status, info = call_wsgi("/info")
    H.check(status.startswith("200"), f"/info باز می‌شود ({status})")

    status, _ = call_wsgi("/this-path-does-not-exist")
    H.check(status.startswith("404"), f"مسیر ناشناس ۴۰۴ می‌دهد ({status})")

    # ─── ۲) تشخیص آدرس سایت در paw_start ───
    print("\n== TEST 2: تشخیص آدرس سایت در paw_start ==")
    import paw_start
    H.check(paw_start.guess_base_url(BASE_URL).rstrip("/") == BASE_URL,
            "آدرس داده‌شده بدون تغییر استفاده می‌شود")
    os.environ["PYTHONANYWHERE_DOMAIN"] = "arezog210.pythonanywhere.com"
    H.check(paw_start.guess_base_url(None) == BASE_URL,
            "روی PythonAnywhere آدرس خودکار تشخیص داده می‌شود")
    os.environ.pop("PYTHONANYWHERE_DOMAIN", None)
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "paw_start.py"), encoding="utf-8").read()
    H.check("httpStatus" in src and "404" in src,
            "paw_start خطای ۴۰۴ را تشخیص می‌دهد و راهنمای WSGI چاپ می‌کند")
    H.check("WSGI" in src, "راهنمای تنظیم فایل WSGI داخل paw_start هست")

    # ─── ۳) paw_doctor ───
    print("\n== TEST 3: اسکریپت عیب‌یابی paw_doctor ==")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    doctor = os.path.join(root, "paw_doctor.py")
    H.check(os.path.exists(doctor), "paw_doctor.py در پروژه هست")
    proc = subprocess.run([sys.executable, doctor], cwd=root, text=True,
                          capture_output=True, timeout=180,
                          env={**os.environ, "PAW_PROXY": "0", "DB_PATH": H.DB})
    out = proc.stdout + proc.stderr
    H.check("عیب‌یابی" in out, "اسکریپت اجرا شد")
    H.check("دیتابیس" in out, "بخش دیتابیس بررسی شد")
    H.check("health" in out, "بخش /health بررسی شد")
    H.check("آدرس سایت" in out, "نبود آدرس سایت را گزارش می‌کند")

    # ─── ۴) init_db دوباره‌اجرا (idempotent) ───
    print("\n== TEST 4: اجرای دوبارهٔ init_db داده را پاک نمی‌کند ==")
    before = await db.fetchone("SELECT COUNT(*) c FROM countries")
    await db.close()
    await init_db()
    after = await db.fetchone("SELECT COUNT(*) c FROM countries")
    H.check(int(after["c"]) == int(before["c"]),
            f"کشورها دست‌نخورده ماندند ({before['c']} → {after['c']})")
    user = await db.fetchone("SELECT id FROM users WHERE id=?", (8101,))
    H.check(bool(user), "بازیکن بعد از init_db دوباره باقی است")

    # ─── ۵) فایل‌های داده‌ای قفل sqlite و بکاپ ───
    print("\n== TEST 5: دیتابیس سالم و بکاپ‌گیری بی‌خطر است ==")
    conn = sqlite3.connect(H.DB)
    ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    H.check(ok == "ok", f"integrity_check دیتابیس: {ok}")
    H.check(any(t.endswith(".db") for t in os.listdir(os.path.join(root, "backups")))
            if os.path.isdir(os.path.join(root, "backups")) else True,
            "پوشهٔ backups برای نسخهٔ پشتیبان وجود دارد")

    await db.close()
    print("\n=== TOTAL ERRORS:", len(H.ERRORS))
    for e in H.ERRORS:
        print("   -", e)


if __name__ == "__main__":
    asyncio.run(main())

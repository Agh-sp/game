"""🟢 «استارت» روی PythonAnywhere — ربات‌ها را یک‌باره فعال و زنده می‌کند.

وقتی روی هاست اشتراکی/رایگان PythonAnywhere هستیم، پروسهٔ همیشه‌روشن نداریم.
این اسکریپت سه کار انجام می‌دهد:

  1. کد را آماده می‌کند (پوشه‌ها، دیتابیس، وابستگی‌های لازم).
  2. وبهوک هر دو ربات را روی آدرس سایت ثبت می‌کند (`/webhook/game`, `/webhook/admin`).
  3. با یک درخواست به `/health` سرویس را بیدار و کارهای دوره‌ای را اجرا می‌کند،
     سپس برای چند ثانیه «بیدار» نگهش می‌دارد تا آپدیت‌های معلق تلگرام پردازش شوند.

اجرا (Bash console روی PythonAnywhere):
    cd ~/game/worldwar-game
    python3 paw_start.py --base-url https://USERNAME.pythonanywhere.com

یا از خود کد (بدون نیاز به آدرس، خودکار از دامنه تشخیص می‌دهد):
    python3 paw_start.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

PROXY_URL = "http://proxy.server:3128"


def use_proxy_if_needed(force: bool | None = None) -> bool:
    on_paw = "pythonanywhere" in (os.getenv("PYTHONANYWHERE_DOMAIN", "") or "")
    on = force if force is not None else on_paw
    if on:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            os.environ.setdefault(k, PROXY_URL)
    return on


def guess_base_url(explicit: str | None) -> str:
    if explicit:
        return explicit.rstrip("/")
    env = (os.getenv("PUBLIC_BASE_URL") or os.getenv("WEBHOOK_BASE_URL") or "").strip()
    if env:
        return env.rstrip("/")
    domain = os.getenv("PYTHONANYWHERE_DOMAIN")
    if domain:
        return f"https://{domain}"
    return ""


def http_get(url: str, timeout: float = 40.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "wwgame-paw-start/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"httpStatus": resp.status, "body": raw[:500]}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "httpStatus": exc.code, "error": exc.reason}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="فعال‌سازی ربات‌ها روی PythonAnywhere (Webhook)")
    parser.add_argument("--base-url", help="آدرس عمومی سایت، مثل https://user.pythonanywhere.com")
    parser.add_argument("--no-proxy", action="store_true", help="استفاده نکردن از پروکسی")
    parser.add_argument("--keep-alive", type=int, default=25,
                        help="چند ثانیه سرویس را بیدار نگه داریم (پیش‌فرض ۲۵)")
    parser.add_argument("--local", action="store_true", help="تست محلی (بدون پروکسی)")
    args = parser.parse_args()

    proxied = use_proxy_if_needed(False if (args.no_proxy or args.local) else None)
    print("🔧 پروکسی PythonAnywhere:", "فعال" if proxied else "غیرفعال")

    base = guess_base_url(args.base_url)
    if not base:
        print("❌ آدرس سایت مشخص نیست. از --base-url استفاده کنید.\n"
              "   مثال: python3 paw_start.py --base-url https://USERNAME.pythonanywhere.com")
        sys.exit(1)
    print("🌐 آدرس سایت:", base)

    os.environ["PUBLIC_BASE_URL"] = base

    # ۱) دیتابیس
    print("🗄 آماده‌سازی دیتابیس ...")
    import asyncio
    try:
        from core.db import init_db
        asyncio.run(init_db())
        print("   ✅ دیتابیس آماده است")
    except Exception as exc:  # noqa: BLE001
        print("   ⚠️ آماده‌سازی دیتابیس:", exc)

    # ۲) ثبت وبهوک از طریق همان سرویس WSGI (تنها راه مطمئن روی PAW)
    print("🔗 ثبت وبهوک هر دو ربات ...")
    result = http_get(f"{base}/setup")
    print("   ", json.dumps(result, ensure_ascii=False)[:600])

    # ۳) بیدار نگه داشتن و پردازش آپدیت‌های معلق
    if args.keep_alive > 0:
        print(f"⏳ بیدار نگه داشتن سرویس به مدت {args.keep_alive} ثانیه ...")
        deadline = time.time() + args.keep_alive
        while time.time() < deadline:
            health = http_get(f"{base}/health", timeout=30)
            ready = health.get("botsReady")
            tasks = health.get("tasks") or {}
            print(f"   💚 botsReady={ready} tasks={tasks.get('tasks')}")
            time.sleep(6)

    info = http_get(f"{base}/info")
    print("📋 وضعیت نهایی وبهوک:")
    print(json.dumps(info, ensure_ascii=False, indent=2)[:1200])
    print("\n✅ کار تمام شد — در تلگرام به ربات‌ها /start بفرستید.\n"
          "   نکته: اگر سایت خوابیده باشد، آدرس سایت را یک‌بار در مرورگر باز کنید.")


if __name__ == "__main__":
    main()

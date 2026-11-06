#!/usr/bin/env python3
"""🚀 نقطهٔ ورود اصلی پروژه — کامل پایتونی (جایگزین `server.ts`).

این فایل همان کاری را می‌کند که قبلاً `server.ts` (Express + Vite) انجام می‌داد،
اما فقط با پایتون:

  1. اگر dependencies پایتون نصب نیست، همان‌جا نصبشان می‌کند.
  2. اگر رابط کاربری ساخته نشده (`dist/`)، با `npx vite build` می‌سازد
     (در صورت نبود Node، پنل با یک صفحهٔ راهنمای داخلی بالا می‌آید).
  3. سرور وب پنل فرماندهی + ربات بازی + ربات ادمین را در یک پروسه اجرا می‌کند.

اجرا:
    python3 server.py               # پنل + هر دو ربات (پیش‌فرض)
    python3 server.py --web-only    # فقط پنل وب
    python3 server.py --port 8080   # پورت دلخواه
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WW_DIR = ROOT / "worldwar-game"
REQUIRED_PACKAGES = ("aiogram", "aiosqlite", "aiohttp")


def _python_has_deps() -> bool:
    import importlib.util
    return all(importlib.util.find_spec(pkg) is not None for pkg in REQUIRED_PACKAGES)


def ensure_python_deps() -> None:
    if _python_has_deps():
        return
    missing = [p for p in REQUIRED_PACKAGES]
    print(f"📦 نصب وابستگی‌های پایتون ({', '.join(missing)}) ...")
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", *missing]
    if subprocess.call(cmd) != 0:
        cmd.insert(4, "--break-system-packages")
        if subprocess.call(cmd) != 0:
            raise SystemExit(
                "❌ نصب وابستگی‌ها ناموفق بود. دستی اجرا کنید:\n"
                f"   {sys.executable} -m pip install -r worldwar-game/requirements.txt"
            )


def ensure_frontend() -> None:
    """اگر dist/ نبود، رابط کاربری را با Vite می‌سازد (اختیاری)."""
    index = ROOT / "dist" / "index.html"
    if index.exists():
        return
    if os.getenv("SKIP_FRONTEND_BUILD", "").lower() in ("1", "true", "yes"):
        return
    npx = shutil.which("npx")
    if not npx:
        print("ℹ️ Node/npx پیدا نشد — پنل با صفحهٔ راهنمای داخلی بالا می‌آید "
              "(همهٔ APIها فعال هستند).")
        return
    if not (ROOT / "node_modules").exists():
        print("📦 نصب وابستگی‌های رابط کاربری ...")
        install = [npx, "--yes", "npm", "install", "--no-fund", "--no-audit", "--legacy-peer-deps"]
        if subprocess.call(install, cwd=str(ROOT)) != 0:
            print("⚠️ نصب وابستگی‌های رابط کاربری ناموفق بود — پنل با صفحهٔ راهنما بالا می‌آید.")
            return
    print("🏗 ساخت رابط کاربری (vite build) ...")
    if subprocess.call([npx, "vite", "build"], cwd=str(ROOT)) != 0:
        print("⚠️ ساخت رابط کاربری ناموفق بود — پنل با صفحهٔ راهنما بالا می‌آید.")


def main() -> None:
    parser = argparse.ArgumentParser(description="پنل فرماندهی + ربات‌های بازی جنگ جهانی (پایتون)")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--web-only", action="store_true", help="فقط پنل وب")
    parser.add_argument("--no-web", action="store_true", help="بدون پنل وب؛ فقط ربات‌ها")
    parser.add_argument("--no-build", action="store_true", help="رابط کاربری ساخته نشود")
    args = parser.parse_args()

    ensure_python_deps()
    if args.no_build:
        os.environ["SKIP_FRONTEND_BUILD"] = "1"
    else:
        ensure_frontend()

    sys.path.insert(0, str(WW_DIR))
    os.chdir(WW_DIR)

    from run_all import run_panel  # noqa: E402  (بعد از تنظیم مسیرها)

    if args.host:
        os.environ["WEB_HOST"] = args.host
    if args.port:
        os.environ["PORT"] = str(args.port)

    import asyncio
    from core import config as cfg
    if args.host:
        cfg.WEB_HOST = args.host
    if args.port:
        cfg.WEB_PORT = args.port

    autostart = not args.web_only
    try:
        if args.no_web:
            from run_all import run_bots_in_process
            asyncio.run(run_bots_in_process())
        else:
            asyncio.run(run_panel(autostart=autostart))
    except KeyboardInterrupt:
        print("\n👋 سرور متوقف شد.")


if __name__ == "__main__":
    main()

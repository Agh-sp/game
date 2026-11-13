"""🩺 `paw_doctor.py` — عیب‌یابی «چرا ربات روی PythonAnywhere جواب نمی‌دهد؟»

روی PythonAnywhere (Bash console):

    cd ~/game/worldwar-game
    python3 paw_doctor.py                       # آدرس سایت خودکار تشخیص داده می‌شود
    python3 paw_doctor.py --base-url https://arezog210.pythonanywhere.com

هفت چیز را به ترتیب بررسی می‌کند و دقیقاً می‌گوید کدام مرحله جا افتاده:

  1. کد و نسخهٔ پایتون و ماژول‌های لازم (aiogram/aiosqlite/aiohttp)
  2. دیتابیس: مسیر، وجود، باز شدن، تعداد جدول‌ها، کاربران، تنظیمات کلیدی
  3. فایل WSGI واقعی سایت (وضعیت اتصال اپ وب به این پروژه)
  4. `/health` سایت → آیا سرویس زنده است و `botsReady` دارد؟
  5. `/setup` سایت → ثبت وبهوک (۴۰۴ = اپ وصل نیست، ۴۰۳ = اختلاف کلید)
  6. `/info` سایت → آدرس وبهوک هر دو ربات از خود تلگرام + آخرین خطا
  7. توکن‌ها و پروکسی

خروجی با ❌/⚠️/✅ خوانا است و در پایان «کار بعدی» را می‌گوید.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

PROXY_URL = "http://proxy.server:3128"
OK, BAD, WARN = "✅", "❌", "⚠️"
PROBLEMS: list[str] = []
NEXT: list[str] = []


def say(mark: str, text: str) -> None:
    print(f" {mark} {text}")


def problem(text: str, fix: str) -> None:
    PROBLEMS.append(text)
    if fix not in NEXT:
        NEXT.append(fix)


def http_json(url: str, secret: str = "", timeout: float = 30.0) -> dict:
    headers = {"User-Agent": "wwgame-paw-doctor/1.0"}
    if secret:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return {"httpStatus": resp.status, **json.loads(raw)}
            except json.JSONDecodeError:
                return {"httpStatus": resp.status, "body": raw[:300]}
    except urllib.error.HTTPError as exc:
        return {"httpStatus": exc.code, "error": exc.reason}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def guess_base(explicit: str | None) -> str:
    if explicit:
        return explicit.rstrip("/")
    for key in ("PUBLIC_BASE_URL", "WEBHOOK_BASE_URL", "PYTHONANYWHERE_DOMAIN"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val.rstrip("/") if val.startswith("http") else f"https://{val}"
    return ""


def check_code() -> None:
    print("\n1️⃣ کد و وابستگی‌ها")
    say(OK, f"پوشهٔ پروژه: {BASE}")
    say(OK, f"پایتون: {sys.version.split()[0]}")
    missing = []
    for mod in ("aiogram", "aiosqlite", "aiohttp"):
        try:
            __import__(mod)
            say(OK, f"ماژول {mod} نصب است")
        except Exception as exc:  # noqa: BLE001
            missing.append(mod)
            say(BAD, f"ماژول {mod} نصب نیست ({exc})")
    for mod in ("webapp.paw_wsgi",):
        try:
            __import__(mod)
            say(OK, f"ماژول {mod} ایمپورت شد")
        except Exception as exc:  # noqa: BLE001
            say(BAD, f"ایمپورت {mod} شکست خورد: {exc}")
            problem("پروژه از مسیر درست بالا نمی‌آید",
                    "داخل همان پوشهٔ worldwar-game دستور را اجرا کنید: "
                    "cd ~/game/worldwar-game && python3 paw_doctor.py")
    if missing:
        ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        problem(f"وابستگی‌های پایتون نصب نیستند: {', '.join(missing)}",
                f"python{ver} -m pip install --user -r requirements.txt")


def check_db() -> bool:
    print("\n2️⃣ دیتابیس")
    from core.config import DB_PATH
    p = Path(DB_PATH)
    say(OK if p.exists() else WARN, f"مسیر دیتابیس: {DB_PATH}"
        f"{'' if p.exists() else ' (هنوز ساخته نشده)'}")
    if p.exists():
        say(OK, f"حجم: {p.stat().st_size / 1024:.0f} کیلوبایت")
    import sqlite3
    try:
        conn = sqlite3.connect(str(p))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        say(OK if len(tables) > 20 else WARN, f"تعداد جدول‌ها: {len(tables)}")
        for key, sql in (("کاربران", "SELECT COUNT(*) FROM users"),
                         ("کشورها", "SELECT COUNT(*) FROM countries")):
            try:
                count = conn.execute(sql).fetchone()[0]
                say(OK, f"{key}: {count}")
            except Exception as exc:  # noqa: BLE001
                say(WARN, f"{key}: خوانده نشد ({exc})")
        try:
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
            say(OK if ok == "ok" else BAD, f"سلامت فایل sqlite: {ok}")
            if ok != "ok":
                problem("فایل دیتابیس آسیب دیده", "از پوشهٔ backups آخرین نسخه را "
                        "کپی کنید یا init_db را دوباره اجرا کنید")
        except Exception:  # noqa: BLE001
            pass
        try:
            row = conn.execute("SELECT value FROM settings WHERE key='webhook_secret'").fetchone()
            say(OK if row and len(str(row[0])) >= 16 else WARN,
                "کلید وبهوک در دیتابیس " + ("موجود است" if row else "وجود ندارد"))
        except Exception as exc:  # noqa: BLE001
            say(WARN, f"خواندن کلید وبهوک ممکن نشد: {exc}")
        conn.close()
        return len(tables) > 20
    except Exception as exc:  # noqa: BLE001
        say(BAD, f"باز کردن دیتابیس ممکن نشد: {exc}")
        problem("دیتابیس باز نمی‌شود",
                "python3 -c \"import asyncio; from core.db import init_db; asyncio.run(init_db())\"")
        return False


def check_wsgi_file() -> None:
    print("\n3️⃣ فایل WSGI سایت (اتصال اپ وب به پروژه)")
    home = Path(os.getenv("HOME") or Path.home())
    user = home.name
    candidates = sorted(Path("/var/www").glob("*_wsgi.py")) if Path("/var/www").exists() else []
    if not candidates:
        say(WARN, "پوشهٔ /var/www اینجا نیست (روی سیستم محلی طبیعی است)")
        return
    mine = [c for c in candidates if user.replace(".", "_") in c.name or user in c.name]
    target = mine[0] if mine else candidates[0]
    try:
        body = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        say(WARN, f"خواندن {target} ممکن نشد: {exc}")
        return
    say(OK, f"فایل WSGI: {target}")
    if "paw_wsgi" in body:
        say(OK, "به webapp.paw_wsgi.application وصل است")
    else:
        say(BAD, "این فایل به paw_wsgi وصل نیست — سایت پروژهٔ دیگری را اجرا می‌کند")
        problem("اپ وب به این پروژه وصل نیست (خطای 404 روی /setup)",
                "در تب Web → WSGI configuration file محتوای فایل را با نمونهٔ "
                "README (بخش PythonAnywhere) جایگزین و Reload کنید")
    if "worldwar-game" not in body:
        say(WARN, "مسیر sys.path شامل پوشهٔ worldwar-game نیست")
        problem("مسیر sys.path در فایل WSGI ناقص است",
                "sys.path.insert(0, '/home/USERNAME/game/worldwar-game') را اضافه کنید")


def check_health(base: str) -> str:
    """کلید وبهوک را از دیتابیس برمی‌گرداند (برای مرحلهٔ بعد)."""
    print("\n4️⃣ سرویس سایت (/health)")
    if not base:
        say(WARN, "آدرس سایت معلوم نیست — از --base-url استفاده کنید")
        return ""
    res = http_json(f"{base}/health")
    status = res.get("httpStatus")
    if status == 404:
        say(BAD, f"{base}/health → 404 (سرویس این پروژه روی سایت نیست)")
        problem("سایت به این پروژه وصل نیست",
                "تب Web → WSGI configuration file را با نمونهٔ README جایگزین و Reload کنید")
        return ""
    if res.get("error"):
        say(BAD, f"تماس با سایت ممکن نشد: {res['error']}")
        problem("سایت جواب نمی‌دهد", "آدرس سایت را در مرورگر باز کنید و دوباره امتحان کنید")
        return ""
    ready = res.get("botsReady")
    say(OK if ready else WARN, f"botsReady={ready} | tasks={res.get('tasks')}")
    if not ready:
        problem("سرویس زنده است ولی ربات‌ها آماده نشده‌اند",
                "/setup را اجرا کنید یا خطای Error log تب Web را ببینید")
    return str(res.get("secret") or "")


def read_secret_from_db() -> str:
    import sqlite3
    from core.config import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT value FROM settings WHERE key='webhook_secret'").fetchone()
        conn.close()
        return str(row[0]) if row else ""
    except Exception:  # noqa: BLE001
        return ""


def check_setup(base: str, secret: str) -> None:
    print("\n5️⃣ ثبت وبهوک (/setup)")
    if not base:
        return
    res = http_json(f"{base}/setup", secret=secret)
    status = res.get("httpStatus")
    if status == 404:
        say(BAD, "/setup → 404 (اپ وب وصل نیست)")
        problem("ثبت وبهوک ممکن نیست (404)",
                "تب Web → WSGI configuration file + Reload، بعد paw_start.py")
        return
    if status == 403:
        say(BAD, "/setup → 403 (کلید وبهوک سایت با کلید Bash یکی نیست)")
        problem("اختلاف کلید وبهوک بین سایت و Bash",
                "در Bash: python3 -c \"import asyncio;from core.security import ensure_webhook_secret as e;"
                "print(asyncio.run(e()))\" و همان کلید را در سایت (تنظیمات .env/WSGI) بگذارید")
        return
    print("   ", json.dumps(res, ensure_ascii=False)[:500])
    ok_any = bool(res.get("success")) or any(
        (v or {}).get("ok") for v in (res.get("results") or {}).values())
    say(OK if ok_any else BAD, "ثبت وبهوک " + ("انجام شد" if ok_any else "ناموفق بود"))
    if not ok_any:
        problem("تلگرام درخواست setWebhook را نپذیرفت",
                "/info و توکن‌های core/config.py را بررسی کنید یا توکن‌ها را Revoke/تازه کنید")


def check_info(base: str) -> None:
    print("\n6️⃣ وضعیت وبهوک از تلگرام (/info)")
    if not base:
        return
    res = http_json(f"{base}/info")
    if res.get("httpStatus") == 404:
        say(BAD, "/info → 404")
        return
    for kind in ("game", "admin"):
        info = res.get(kind) or {}
        if not info:
            say(WARN, f"{kind}: اطلاعاتی نبود")
            continue
        url = info.get("url") or ""
        say(OK if url else WARN, f"{kind}: url={url or '—'} | pending={info.get('pendingUpdates')}"
            f" | lastError={info.get('lastError') or '—'}")
        if url and not url.endswith(f"/webhook/{kind}"):
            problem(f"آدرس وبهوک {kind} درست نیست ({url})", "دوباره /setup را اجرا کنید")
        if info.get("lastError"):
            problem(f"تلگرام برای {kind} خطا داده: {info['lastError']}",
                    "اگر آخرین خطا مربوط به زمان قبل از اصلاح است، یک پیام در ربات بفرستید "
                    "و دوباره /info را ببینید")


def check_tokens() -> None:
    print("\n7️⃣ توکن‌ها و پروکسی")
    from core import config as cfg
    for name, token in (("GAME_BOT_TOKEN", cfg.GAME_BOT_TOKEN), ("ADMIN_BOT_TOKEN", cfg.ADMIN_BOT_TOKEN)):
        say(OK if token else BAD, f"{name}: " + ("تنظیم است" if token else "خالی است"))
        if not token:
            problem(f"{name} تنظیم نشده", "توکن را در core/config.py یا .env بگذارید")
    proxied = any(os.getenv(k) for k in ("HTTPS_PROXY", "https_proxy"))
    on_paw = "pythonanywhere" in (os.getenv("PYTHONANYWHERE_DOMAIN") or "")
    say(OK if (proxied or not on_paw) else WARN,
        "پروکسی: " + ("فعال" if proxied else "غیرفعال"))


def main() -> int:
    ap = argparse.ArgumentParser(description="عیب‌یابی اجرای ربات روی PythonAnywhere")
    ap.add_argument("--base-url", help="آدرس عمومی سایت")
    ap.add_argument("--no-proxy", action="store_true", help="بدون پروکسی (حساب پلاس)")
    ap.add_argument("--fix-db", action="store_true",
                    help="اگر دیتابیس نیم‌کاره/خراب است، init_db را روی همین فایل اجرا کن")
    args = ap.parse_args()

    on_paw = "pythonanywhere" in (os.getenv("PYTHONANYWHERE_DOMAIN") or "") or Path("/var/www").exists()
    if on_paw and not args.no_proxy:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            os.environ.setdefault(key, PROXY_URL)

    print("🩺 عیب‌یابی ربات جنگ جهانی ۳")
    check_code()
    if args.fix_db:
        print("\n🔧 اجرای init_db (ساخت/ترمیم جداول و داده‌های اولیه) ...")
        import asyncio
        try:
            from core.db import init_db
            asyncio.run(init_db())
            say(OK, "init_db با موفقیت تمام شد")
        except Exception as exc:  # noqa: BLE001
            say(BAD, f"init_db شکست خورد: {exc}")
            problem("ساخت/ترمیم دیتابیس شکست خورد", "خروجی خطا را ببینید؛ اگر «database is locked» "
                    "بود، پروسهٔ دیگری (ربات محلی) را ببندید و دوباره اجرا کنید")
    _db_ok = check_db()
    check_wsgi_file()
    base = guess_base(args.base_url)
    secret = check_health(base)
    if not secret:
        secret = read_secret_from_db()
        if secret:
            say(OK, "کلید وبهوک از دیتابیس خوانده شد")
    check_setup(base, secret)
    check_info(base)
    check_tokens()

    print("\n" + "─" * 60)
    verified = bool(base)      # فقط وقتی آدرس سایت داده شده، نتیجه معتبر است
    if not PROBLEMS:
        if verified:
            print("🎉 همه‌چیز سالم است: ربات‌ها با Webhook فعال‌اند.")
            print("   در تلگرام به ربات بازی /start بفرستید.")
            return 0
        print("⚠️ بررسی محلی سالم است، اما سرویس سایت بررسی نشد (آدرس سایت داده نشد).")
        print("   برای بررسی کامل اجرا کنید:")
        print("     python3 paw_doctor.py --base-url https://USERNAME.pythonanywhere.com")
        return 0
    print(f"❌ {len(PROBLEMS)} مشکل پیدا شد:")
    for i, (p_, n_) in enumerate(zip(PROBLEMS, NEXT), 1):
        print(f"  {i}. {p_}")
        print(f"     ↳ کار بعدی: {n_}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

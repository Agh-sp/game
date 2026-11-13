"""🚀 `paw_update.sh` — به‌روزرسانی امن کد روی PythonAnywhere بدون دردسر گیت.

مشکل رایج: `wwgame.db` و `fb_local.json` هم داخل گیت هستند و روی سرور تغییر
می‌کنند؛ نتیجه‌اش این می‌شود که `git pull` با پیام
«needs merge / no tracked files» یا درگیری فایل دودویی متوقف می‌شود.

این اسکریپت همان کاری را می‌کند که دستی باید بکنی، ولی مطمئن:

    cd ~/game/worldwar-game
    bash paw_update.sh                # بکاپ دیتابیس + ذخیرهٔ تغییرات محلی + pull + بازگردانی
    bash paw_update.sh --branch main  # از برنچ مشخص

مرحله‌ها:
  1. بکاپ دیتابیس با تاریخ (پوشهٔ `backups/`)
  2. `git stash push` فقط روی دو فایل داده‌ای (دیتابیس و اسنپ‌شات فایربیس)
  3. `git pull --ff-only`
  4. بازگردانی داده‌های محلی (`git checkout stash@{0} -- ...`)
  5. نصب وابستگی‌ها و اجرای «استارت» (`paw_start.py`) در صورت خواستن
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_FILES = ("wwgame.db", "fb_local.json")


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, cwd=BASE, check=check, text=True,
                          capture_output=capture)


def out(cmd: list[str]) -> str:
    try:
        return run(cmd, check=False, capture=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def backup_db() -> Path | None:
    db = BASE / "wwgame.db"
    if not db.exists():
        return None
    backups = BASE / "backups"
    backups.mkdir(exist_ok=True)
    target = backups / f"wwgame-{time.strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(db, target)
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description="به‌روزرسانی کد روی PythonAnywhere")
    ap.add_argument("--branch", help="برنچ موردنظر (پیش‌فرض: همان برنچ فعلی)")
    ap.add_argument("--no-start", action="store_true", help="بعد از آپدیت، paw_start را اجرا نکن")
    ap.add_argument("--base-url", help="آدرس سایت برای paw_start")
    args = ap.parse_args()

    print("🚀 به‌روزرسانی پروژه")
    if not (BASE / ".git").exists() and not (BASE.parent / ".git").exists():
        print("❌ این پوشه مخزن گیت نیست")
        return 1

    # حذف قفل‌های نصفه‌کارهٔ گیت (اگر pull قبلی نیمه‌کاره مانده باشد)
    state = out(["git", "status", "--porcelain"])
    for marker in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD"):
        path = Path(out(["git", "rev-parse", "--git-dir"]) or ".git") / marker
        if path.exists():
            print(f"⚠️ یک عملیات گیت نیمه‌کاره ({marker}) پیدا شد — پاک می‌شود")
            path.unlink(missing_ok=True)

    print("\n1️⃣ بکاپ دیتابیس")
    made = backup_db()
    print("   ", "✅ " + str(made) if made else "⚠️ دیتابیسی برای بکاپ نبود")

    print("\n2️⃣ کنار گذاشتن داده‌های محلی")
    tracked = [f for f in DATA_FILES if f"worldwar-game/{f}" in out(["git", "ls-files"]) or
               f in out(["git", "ls-files", "--", "."])]
    stash_ref = ""
    if tracked:
        res = run(["git", "stash", "push", "-m", "paw_update local data", "--", *tracked],
                  check=False)
        if res.returncode == 0 and "No local changes" not in out(["git", "stash", "list"]):
            stash_ref = "stash@{0}"
            print("   ✅ داده‌های محلی کنار گذاشته شد:", ", ".join(tracked))
        else:
            print("   ℹ️ تغییری برای کنار گذاشتن نبود")
    else:
        print("   ℹ️ این دو فایل در گیت نیستند (به‌روزرسانی ساده است)")

    print("\n3️⃣ دریافت کد تازه")
    branch = args.branch or out(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "main"
    if branch and branch != "HEAD":
        run(["git", "checkout", branch], check=False)
    pull = run(["git", "pull", "--ff-only"], check=False)
    if pull.returncode != 0:
        print("   ⚠️ pull --ff-only نشد؛ تلاش با rebase ...")
        run(["git", "pull", "--rebase"], check=False)

    print("\n4️⃣ بازگردانی داده‌های محلی")
    if stash_ref:
        for f in DATA_FILES:
            if (BASE / f).exists() or True:
                run(["git", "checkout", stash_ref, "--", f], check=False)
        run(["git", "stash", "drop", stash_ref], check=False)
        print("   ✅ دیتابیس و اسنپ‌شات محلی برگردانده شد")

    # اگر فایل‌های «نیازمند ادغام» باقی مانده باشند، از نسخهٔ بکاپ/HEAD استفاده کن
    conflicted = [line.split()[-1] for line in out(["git", "status", "--porcelain"]).splitlines()
                  if line.startswith(("UU", "AA", "DU", "UD"))]
    if conflicted:
        print("   ⚠️ فایل‌های درگیر:", ", ".join(conflicted))
        for f in conflicted:
            run(["git", "checkout", "--ours", "--", f], check=False)
            run(["git", "add", f], check=False)
        print("   ✅ با نسخهٔ محلی حل شد (داده‌ها حفظ شدند)")

    print("\n5️⃣ وابستگی‌ها")
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    run([f"python{ver}", "-m", "pip", "install", "--user", "-r", "requirements.txt"],
        check=False)

    print("\n📄 نسخهٔ فعلی:")
    print("   ", out(["git", "log", "-1", "--oneline"]))

    if not args.no_start:
        print("\n6️⃣ استارت ربات‌ها")
        cmd = [sys.executable, "paw_start.py"]
        if args.base_url:
            cmd += ["--base-url", args.base_url]
        rc = run(cmd, check=False).returncode
        if rc != 0:
            print("\n⚠️ استارت کامل نشد — عیب‌یابی خودکار:")
            run([sys.executable, "paw_doctor.py"] + (["--base-url", args.base_url]
                                                     if args.base_url else []), check=False)

    print("\n✅ تمام. یادت نرود در تب Web دکمهٔ **Reload** را هم بزنی.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

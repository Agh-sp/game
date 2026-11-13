#!/usr/bin/env python3
"""نقطهٔ ورود پنل فرماندهی وب — کاملاً پایتونی (بدون Node/Express).

اجرا:
    python3 web.py                 # پنل وب + اجرای خودکار ربات‌های تلگرام
    python3 web.py --web-only      # فقط پنل وب (ربات‌ها را جای دیگر اجرا کنید)
    python3 web.py --port 8080     # تغییر پورت (پیش‌فرض 3000 یا متغیر PORT)

مسیرها:
    /                     پنل فرماندهی (React ساخته‌شده در dist/)
    /health               وضعیت سرویس، ربات‌ها و پینگ بیدارباش
    /login                ورود به پنل (گذرواژه از ربات ادمین → 🔐 امنیت)
    /api/secrets          توکن‌ها و آیدی ادمین (خواندن/ذخیره) — نیازمند نشست
    /api/users            مدیریت کاربران بازی
    /webhook/game|admin   دریافت آپدیت‌های تلگرام (حالت وبهوک)
"""
from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from webapp.server import main  # noqa: E402

if __name__ == "__main__":
    main()

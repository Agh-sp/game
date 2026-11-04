# تست‌های خودکار (بدون تلگرام)

این تست‌ها ربات‌ها را با یک Bot قلابی و `Dispatcher.feed_update` اجرا می‌کنند؛ نیازی به توکن تلگرام نیست.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install aiogram aiosqlite

python3 tests/smoke.py               # همه منوهای ربات بازی و ادمین (بدون خطا)
python3 tests/test_new_features.py   # پرچم، عکس اعلان‌ها، سایبری، اهداف جنگ، مالیات میلیونی
python3 tests/test_regression.py     # رای ۳۰ دقیقه‌ای، حمله موشکی/زمینی، مذاکره، فیش ادمین
```

هر فایل در پایان `=== TOTAL ERRORS: 0` چاپ می‌کند. دیتابیس تست در `/tmp` ساخته می‌شود و به `wwgame.db` واقعی دست نمی‌زند.

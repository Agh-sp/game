# تست‌های خودکار (بدون تلگرام و بدون Node)

این تست‌ها ربات‌ها را با یک Bot قلابی و `Dispatcher.feed_update` اجرا می‌کنند؛ نیازی به
توکن تلگرام نیست. تست پنل وب هم سرور `aiohttp` را در حافظه بالا می‌آورد.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python3 tests/test_webapp.py         # سرور وب پایتونی
PAW_PROXY=0 python3 tests/test_paw.py   # اپلیکیشن WSGI مخصوص PythonAnywhere: health، info، setup، webhook
python3 tests/test_webhook.py        # سرویس وبهوک + سلامت + رله آپدیت
python3 tests/smoke.py               # همهٔ منوهای ربات بازی و ادمین (بدون خطا)
python3 tests/test_new_features.py   # پرچم، عکس اعلان‌ها، سایبری، اهداف جنگ، مالیات میلیونی
python3 tests/test_regression.py     # رای ۳۰ دقیقه‌ای، حمله موشکی/زمینی، مذاکره، فیش ادمین
python3 tests/test_adminpanel.py     # پنل /panel، سوپرادمین ۸۶۶۶۵۰۱۸۶۶ و لاگ ادمین‌ها
python3 tests/test_combat.py         # نبرد واقعی تنگه‌ها و تلفات دو طرف
python3 tests/test_politics_oil.py   # انقلاب، انتخابات، دکل نفت و تجارت خودکار
```

هر فایل در پایان `=== TOTAL ERRORS: 0` چاپ می‌کند. دیتابیس تست در `/tmp` ساخته
می‌شود و به `wwgame.db` واقعی دست نمی‌زند.

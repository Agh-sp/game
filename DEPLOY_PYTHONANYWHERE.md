# 🚀 اجرای ربات‌ها روی PythonAnywhere (حساب `arezog210`)

> ## ⚡️ اگر `paw_start.py` می‌گوید `404 NOT FOUND`
>
> پیام `{"ok": false, "httpStatus": 404}` و `botsReady=None` یعنی **اپ وب روی
> PythonAnywhere به این پروژه وصل نیست** — نه اینکه ربات خراب باشد. کد پایتون
> **هرگز** نباید در Bash console اجرا شود؛ محتوای زیر فقط داخل فایل WSGI
> (تب **Web → WSGI configuration file**) قرار می‌گیرد.
>
> سریع‌ترین مسیر:
> ```bash
> cd ~/game/worldwar-game
> python3 paw_update.py --base-url https://arezog210.pythonanywhere.com   # کد تازه + استارت
> python3 paw_doctor.py --base-url https://arezog210.pythonanywhere.com # عیب‌یابی دقیق
> ```
> و اگر `paw_doctor` گفت «اپ وب وصل نیست»، فقط مرحلهٔ ۳ همین راهنما (فایل WSGI +
> Reload) را انجام بده و دوباره `paw_start.py` را بزن.

این راهنما دقیقاً برای مسیر `/home/arezog210/game` نوشته شده است.
اطلاعات ربات‌ها از قبل داخل کد ثبت شده و **هیچ فایل `.env`ی لازم نیست**:

| مورد | مقدار |
|---|---|
| 🎮 توکن ربات بازی | `9201202722:AAGuSaJQw16F_ugrKXUidttYfMqI9Cz3SVE` |
| 🛡 توکن ربات ادمین | `9000162449:AAG-xoIDUSgE1LFWr1L3BOZjygueYuCZOfU` |
| 👑 آیدی ادمین کل | `8666501866` |

> روی PythonAnywhere نمی‌شود ربات را با `polling` (پروسهٔ همیشه روشن) اجرا کرد —
> پلن رایگان نه پروسهٔ دائمی دارد نه ترد. بنابراین پروژه یک حالت **Webhook** دارد
> (`worldwar-game/webapp/paw_wsgi.py`): خودِ تلگرام هر پیام را به آدرس سایت شما
> POST می‌کند و ربات همان‌جا جواب می‌دهد. کد آماده است؛ فقط ۵ مرحله زیر را انجام دهید.

---

## ۱) کد را روی PythonAnywhere بیاورید

در **Bash console** (تب Consoles → Bash):

```bash
cd /home/arezog210
rm -rf game                       # اگر پوشهٔ قبلی ناقص است
git clone https://github.com/Agh-sp/game.git
cd /home/arezog210/game
```

اگر مخزن خصوصی است یا Git در دسترس نبود، فایل ZIP پروژه را از تب **Files → Upload**
آپلود و در Bash باز کنید:

```bash
cd /home/arezog210
unzip game.zip -d game            # نام فایل آپلودشده
```

## ۲) وابستگی‌ها را نصب کنید

پایتون PythonAnywhere معمولاً ۳.۱۰ است (`python3 --version` را چک کنید):

```bash
cd /home/arezog210/game
python3 -m pip install --user -r worldwar-game/requirements.txt
python3 -m pip install --user flask      # فقط برای بخش اختیاری «پنل وب»
```

## ۳) فایل WSGI را در تب **Web** تنظیم کنید

1. تب **Web** → دکمهٔ **Add a new web app** → **Manual configuration** →
   نسخهٔ پایتون (۳.۱۰) را انتخاب کنید.
2. در همان صفحه، لینک **WSGI configuration file** را باز کنید
   (`/var/www/arezog210_pythonanywhere_com_wsgi.py`).
3. **کل محتوای فایل** را پاک کنید و این را بگذارید (فقط `USERNAME` را اگر
   متفاوت است عوض کنید).

   > ⛔️ این متن را در **Bash console** اجرا نکنید؛ فقط داخل فایل WSGI در تب Web.
   > اگر در Bash اجرا شود خطاهایی مثل `USERNAME: command not found` می‌گیری.

```python
import sys, os

USERNAME = "arezog210"
BASE = f"/home/{USERNAME}/game"

sys.path.insert(0, os.path.join(BASE, "worldwar-game"))
sys.path.insert(0, BASE)

# پروکسی حساب رایگان PythonAnywhere (برای تماس با api.telegram.org)
os.environ["PAW_PROXY"] = "1"

# آدرس عمومی سایت — برای ثبت وبهوک
os.environ["PUBLIC_BASE_URL"] = f"https://{USERNAME}.pythonanywhere.com"

# دیتابیس SQLite کنار پروژه
os.environ["DB_PATH"] = os.path.join(BASE, "worldwar-game", "wwgame.db")

from webapp.paw_wsgi import application   # noqa: E402
```

4. دکمهٔ **Reload** (سبز) را بزنید.

## ۴) «استارت» بزنید تا ربات روشن شود ✅

در Bash console:

```bash
cd /home/arezog210/game/worldwar-game
python3 paw_start.py --base-url https://arezog210.pythonanywhere.com
```

این دستور:

- دیتابیس را می‌سازد (۴۵ کشور، تجهیزات، تنگه‌ها، ماموریت‌ها…)،
- وبهوک **هر دو ربات** را روی آدرس سایت ثبت می‌کند
  (`/webhook/game` و `/webhook/admin`)،
- سایت را بیدار می‌کند و کارهای دوره‌ای (درآمد، انقلاب، نفت، رأی‌گیری…) را اجرا می‌کند.

اگر ترجیح می‌دهید بدون Bash باشد، همین آدرس را در مرورگر باز کنید:

```
https://arezog210.pythonanywhere.com/setup
```

بعد از آن در تلگرام به ربات‌ها `/start` بفرستید. 🎉

## ۵) بررسی سلامت

| آدرس | کار |
|---|---|
| `https://arezog210.pythonanywhere.com/` | صفحهٔ وضعیت |
| `https://arezog210.pythonanywhere.com/health` | آمادگی ربات‌ها + اجرای کارهای دوره‌ای |
| `https://arezog210.pythonanywhere.com/info` | اطلاعات وبهوک هر دو ربات از تلگرام |
| `https://arezog210.pythonanywhere.com/setup` | ثبت دوبارهٔ وبهوک |
| `https://arezog210.pythonanywhere.com/panel` | صفحهٔ وضعیت ساده |

---

## نکته‌های مهم

- **بیدار نگه داشتن:** PythonAnywhere سایت رایگان را بعد از مدتی بی‌استفادگی
  می‌خوابانَد. هر بار که آدرس سایت را باز کنید (یا `/health` را صدا بزنید) بیدار
  می‌شود و آپدیت‌های معلق تلگرام پردازش می‌شوند. برای همیشه‌روشن بودن، یک
  **Always-on task** (پلن Hacker) یا یک سرویس پینگ بیرونی روی `/health` بگذارید.
- **پروکسی:** حساب رایگان فقط از طریق `http://proxy.server:3128` به اینترنت وصل
  می‌شود؛ `PAW_PROXY=1` این کار را خودکار انجام می‌دهد. اگر حساب پلاس دارید،
  آن را `0` بگذارید.
- **مدیریت دیتابیس:** از `/api/db/stats` روی VPS استفاده کنید؛ روی PythonAnywhere
  همین دستور در Bash کافی است:

  ```bash
  cd /home/arezog210/game/worldwar-game
  python3 -c "import db_bridge, json; print(json.dumps(db_bridge.get_users(), ensure_ascii=False)[:500])"
  ```

- **پشتیبان‌گیری:** فایل `worldwar-game/wwgame.db` را از تب **Files** دانلود کنید.
- **پنل کامل React:** روی PythonAnywhere رایگان سرور دائمی ممکن نیست؛ پنل کامل
  با `python3 server.py` روی یک VPS اجرا می‌شود. برای فقط‌خواندن، `/panel` و
  `/health` همیشه در دسترس‌اند.

## اگر ربات جواب نداد

1. `https://arezog210.pythonanywhere.com/info` را باز کنید؛ باید `url` برابر
   `https://arezog210.pythonanywhere.com/webhook/game` باشد و `lastError` خالی.
2. در تب **Web → Error log** آخرین خطا را ببینید.
3. مقدار `WEBHOOK_SECRET` را ست نکنید مگر آن‌که در `.env` هم همان باشد.
4. اگر `pendingUpdates` بزرگ است، صفحه را چند بار باز کنید تا صف خالی شود.
5. مطمئن شوید توکن‌ها همان‌هایی هستند که در `worldwar-game/core/config.py` ثبت شده‌اند.

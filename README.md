<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://ai.google.dev/static/site-assets/images/share-ais-513315318.png" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/e36bf87a-e4b3-444b-9ec3-b8d88f451dfd

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## ⚔️ نبرد واقعی (تنگه‌ها و حملات)

- همهٔ حملات در `worldwar-game/core/combat.py` حل می‌شوند: توان دو طرف از تجهیزات/سرباز واقعی، انتخاب **استراتژی حمله** بر اساس ترکیب نیروها، شانس پیروزی بر پایهٔ نسبت توان و **تلفات واقعی هر دو طرف** (کسر از انبار).
- تسخیر تنگه یک **نبرد دریایی** است: باید با ناوگان/زیردریایی بجنگید (پدافند ساحلی مدافع هم حساب می‌شود)، با پیروزی مالکیت منتقل می‌شود، با شکست دست مدافع می‌ماند؛ در هر دو حالت ناوگان و سرباز دو طرف آسیب می‌بیند.
- گزارش کانال شامل نوع استراتژی، توان مهاجم/مدافع، شانس و بخش «خسارات طرفین» با فهرست تلفات هر دو کشور است.
- تست: `worldwar-game/tests/test_combat.py`.

## 🌐 سلامت سرویس، وبهوک و پینگ بیدارباش

- `GET /health` (و `HEAD /health`) — وضعیت سرویس وب: uptime، اجرای ربات، watchdog، وضعیت وبهوک و آخرین پینگ.
- **پینگ هر ۱۰ دقیقه**: سرویس هر ۱۰ دقیقه یک درخواست فیک به `https://<آدرس Web App>/health` می‌زند تا خاموش نشود (`KEEPALIVE_MINUTES=10`، با `KEEPALIVE=0` خاموش، آدرس از `WEBAPP_URL` یا خودکار از دامنهٔ درخواست‌ها). اگر آدرس عمومی از داخل کانتینر در دسترس نباشد، به‌صورت خودکار همان پینگ را محلی (`127.0.0.1`) تکرار می‌کند و در `/health` با `lastFallback: true` گزارش می‌دهد.
- `AUTOSTART_BOTS=0` اجرای خودکار ربات‌ها را (برای پیش‌نمایش/توسعه) متوقف می‌کند.
- **سیستم وبهوک تلگرام**: `POST /webhook/game` و `POST /webhook/admin` (رله به سرویس پایتون `run_webhook.py`) + مدیریت کامل با `/api/webhook/status`، `/api/webhook/set`، `/api/webhook/delete`، `/api/webhook/mode`.
- سرویس پایتون: `python3 worldwar-game/run_webhook.py` — مسیرهای `/health`، `/webhook/game`، `/webhook/admin`، `/webhook/info`، `/webhook/set`، `/webhook/delete` با کلید امنیتی `WEBHOOK_SECRET`.

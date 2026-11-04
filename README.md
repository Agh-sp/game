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

## 🌐 سلامت سرویس، وبهوک و پینگ بیدارباش

- `GET /health` (و `HEAD /health`) — وضعیت سرویس وب: uptime، اجرای ربات، watchdog، وضعیت وبهوک و آخرین پینگ.
- **پینگ هر ۱۰ دقیقه**: سرویس به‌طور خودکار به آدرس Web App یک درخواست فیک می‌زند تا خاموش نشود (`KEEPALIVE_MINUTES=10`، با `KEEPALIVE=0` خاموش می‌شود، آدرس از `WEBAPP_URL` یا خودکار از دامنهٔ درخواست‌ها).
- **سیستم وبهوک تلگرام**: `POST /webhook/game` و `POST /webhook/admin` (رله به سرویس پایتون `run_webhook.py`) + مدیریت کامل با `/api/webhook/status`، `/api/webhook/set`، `/api/webhook/delete`، `/api/webhook/mode`.
- سرویس پایتون: `python3 worldwar-game/run_webhook.py` — مسیرهای `/health`، `/webhook/game`، `/webhook/admin`، `/webhook/info`، `/webhook/set`، `/webhook/delete` با کلید امنیتی `WEBHOOK_SECRET`.

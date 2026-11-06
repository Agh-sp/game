"""سرور وب پنل فرماندهی بازی جنگ جهانی — کاملاً پایتونی (aiohttp).

این فایل جایگزین کامل `server.ts` (Express + Vite) است:
  • همان APIهایی که پنل React صدا می‌زند (`/api/secrets`, `/api/users`, ...)
  • همان سلامت سرویس و پینگ بیدارباش (`/health`, `/api/keepalive`)
  • مدیریت وبهوک تلگرام و رلهٔ آپدیت‌ها به ربات‌های aiogram
  • اجرا/توقف/ری‌استارت/نگهبانی پروسهٔ ربات‌ها با پایتون
  • سرو کردن رابط کاربری ساخته‌شده (dist/) یا حالت توسعه (proxy به Vite)

اجرا:
    cd worldwar-game && python3 web.py            # پنل + ربات‌ها
    cd worldwar-game && python3 web.py --web-only # فقط پنل وب
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout, web

from core import config as cfg

from . import config_service, data_service, game_meta
from .process_manager import process_manager

log = logging.getLogger("webapp")
STARTED_AT = time.time()
REPO_ROOT = cfg.BASE_DIR.parent
DIST_DIR = REPO_ROOT / "dist"

# ─── پینگ بیدارباش ───
KEEPALIVE_DISABLED = os.getenv("KEEPALIVE", "1").strip().lower() in ("0", "false", "no", "off")
EXTERNAL_WEBAPP_URL = (os.getenv("WEBAPP_URL") or os.getenv("PUBLIC_URL")
                       or os.getenv("SELF_URL") or "").strip().rstrip("/")
learned_base_url = ""
self_ping = {
    "enabled": not KEEPALIVE_DISABLED,
    "intervalMinutes": max(1, cfg.KEEPALIVE_MINUTES),
    "target": EXTERNAL_WEBAPP_URL,
    "count": 0,
    "lastPingAt": None,
    "lastStatus": None,
    "lastError": "",
    "lastTrigger": "",
    "lastFallback": False,
}

# ─── آمار وبهوک ───
webhook_stats: dict[str, dict[str, Any]] = {
    "game": {"hits": 0, "relayed": 0, "lastHitAt": None, "lastStatus": None, "lastError": ""},
    "admin": {"hits": 0, "relayed": 0, "lastHitAt": None, "lastStatus": None, "lastError": ""},
}
WEBHOOK_PY_URL = f"http://127.0.0.1:{cfg.WEBHOOK_PORT}"


# ─────────────────────────── کمکی‌ها ───────────────────────────

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def json_body(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def ok(data: Any = None, **extra: Any) -> web.Response:
    payload: dict[str, Any] = {"success": True}
    if data is not None:
        payload.update(data if isinstance(data, dict) else {"data": data})
    payload.update(extra)
    return web.json_response(payload, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


def err(message: str, status: int = 400) -> web.Response:
    return web.json_response({"success": False, "error": message}, status=status,
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


def resolve_self_url(request: web.Request | None = None) -> str:
    if EXTERNAL_WEBAPP_URL:
        return EXTERNAL_WEBAPP_URL
    if learned_base_url:
        return learned_base_url
    return f"http://127.0.0.1:{cfg.WEB_PORT}"


def learn_base_url(request: web.Request) -> None:
    """آدرس عمومی سرویس را از اولین درخواست ورودی یاد می‌گیرم تا پینگ به همان برود."""
    global learned_base_url
    if learned_base_url:
        return
    host = (request.headers.get("X-Forwarded-Host") or request.headers.get("Host") or "").split(",")[0].strip()
    if not host:
        return
    proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    is_local = any(host.startswith(p) for p in ("localhost", "127.0.0.1", "[::1]"))
    learned_base_url = f"{proto or ('http' if is_local else 'https')}://{host}"


async def ping_url(url: str, timeout: float = 15.0) -> dict[str, Any]:
    try:
        async with ClientSession(timeout=ClientTimeout(total=timeout)) as session:
            async with session.get(url, headers={"X-Keepalive": "1",
                                                 "User-Agent": "wwgame-keepalive/1.0"}) as r:
                return {"ok": r.status == 200, "status": r.status, "error": "" if r.status == 200 else f"HTTP {r.status}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": 0, "error": str(exc)}


async def self_ping_once(trigger: str = "interval") -> dict[str, Any]:
    if not self_ping["enabled"]:
        return self_ping
    base = resolve_self_url()
    result = await ping_url(f"{base}/health")
    if not result["ok"]:
        # اگر آدرس عمومی از داخل کانتینر در دسترس نبود، همان پینگ را محلی تکرار می‌کنیم
        local = await ping_url(f"http://127.0.0.1:{cfg.WEB_PORT}/health")
        if local["ok"]:
            result = {"ok": True, "status": local["status"],
                      "error": f"public ping failed ({result['error']}) — local fallback ok"}
            self_ping["lastFallback"] = True
    self_ping.update({
        "count": self_ping["count"] + 1,
        "lastPingAt": now_iso(),
        "lastStatus": result["status"],
        "lastError": result["error"],
        "lastTrigger": trigger,
        "target": base,
    })
    return self_ping


async def keepalive_loop(app: web.Application) -> None:
    interval = max(1, int(self_ping["intervalMinutes"])) * 60
    await asyncio.sleep(min(15, interval))
    while True:
        try:
            await self_ping_once("interval")
        except Exception as exc:  # noqa: BLE001
            log.warning("پینگ بیدارباش ناموفق: %s", exc)
        await asyncio.sleep(max(1, self_ping["intervalMinutes"]) * 60)


# ─────────────────────────── سلامت ───────────────────────────

async def health_payload() -> dict[str, Any]:
    st = process_manager.status()
    return {
        "status": "ok",
        "service": "worldwar-command-center",
        "runtime": "python",
        "mode": "webhook" if cfg.WEBHOOK_MODE else "polling",
        "uptime": int(time.time() - STARTED_AT),
        "timestamp": now_iso(),
        "botRunning": st["isRunning"],
        "botPid": st["pid"],
        "bot": st,
        "watchdog": st["watchdog"],
        "keepalive": {**self_ping, "target": self_ping["target"] or resolve_self_url(),
                      "resolvedTarget": resolve_self_url()},
        "webhook": {
            "enabled": cfg.WEBHOOK_MODE,
            "pythonService": WEBHOOK_PY_URL,
            "paths": {"game": "/webhook/game", "admin": "/webhook/admin"},
            "stats": webhook_stats,
        },
        "db": _db_info(),
    }


def _db_info() -> dict[str, Any]:
    path = Path(data_service.db_path())
    return {"path": str(path), "size": path.stat().st_size if path.exists() else 0}


# ─────────────────────────── وبهوک ───────────────────────────

async def relay_webhook(kind: str, request: web.Request) -> web.Response:
    stat = webhook_stats[kind]
    stat["hits"] += 1
    stat["lastHitAt"] = now_iso()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

    # ۱) اگر سرویس وبهوک پایتون جداگانه بالا باشد، آپدیت را به آن رله می‌کنیم
    try:
        async with ClientSession(timeout=ClientTimeout(total=12)) as session:
            headers = {"Content-Type": "application/json"}
            if secret:
                headers["X-Telegram-Bot-Api-Secret-Token"] = secret
            async with session.post(f"{WEBHOOK_PY_URL}/webhook/{kind}", json=payload,
                                    headers=headers) as r:
                stat["relayed"] += 1
                stat["lastStatus"] = r.status
                stat["lastError"] = ""
                return web.json_response({"ok": True, "relayed": True, "upstreamStatus": r.status})
    except Exception as exc:  # noqa: BLE001
        stat["lastError"] = str(exc)
        stat["lastStatus"] = 0

    # ۲) رله ممکن نشد → اگر خود همین سرور دیسپچر زنده دارد، مستقیم پردازش می‌کنیم
    bots = request.app.get("bots") or {}
    dps = request.app.get("dps") or {}
    bot, dp = bots.get(kind), dps.get(kind)
    if bot is not None and dp is not None:
        try:
            from aiogram.types import Update
            update = Update.model_validate(payload, context={"bot": bot})
            await dp.feed_update(bot, update)
            stat["relayed"] += 1
            stat["lastStatus"] = 200
            return web.json_response({"ok": True, "relayed": False, "handledLocally": True})
        except Exception as exc:  # noqa: BLE001
            stat["lastError"] = str(exc)
            log.exception("خطا در پردازش محلی آپدیت %s", kind)

    return web.json_response({
        "ok": True, "relayed": False,
        "warning": "سرویس وبهوک پایتون در دسترس نیست — ربات‌ها در حالت polling کار می‌کنند",
        "error": stat["lastError"],
    })


def _tokens() -> dict[str, str]:
    return {"game": cfg.GAME_BOT_TOKEN, "admin": cfg.ADMIN_BOT_TOKEN}


async def webhook_status_payload() -> dict[str, Any]:
    tokens = _tokens()
    info: dict[str, Any] = {}
    for kind, token in tokens.items():
        if not token:
            info[kind] = {"configured": False}
            continue
        tg = config_service.telegram_api(token, "getWebhookInfo")
        result = tg.get("result") or {}
        info[kind] = {
            "configured": True,
            "ok": bool(tg.get("ok")),
            "url": result.get("url", ""),
            "pendingUpdates": result.get("pending_update_count"),
            "lastError": result.get("last_error_message"),
            "lastErrorAt": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(result["last_error_date"]))
                            if result.get("last_error_date") else None),
        }
    python_service = False
    try:
        async with ClientSession(timeout=ClientTimeout(total=3)) as session:
            async with session.get(f"{WEBHOOK_PY_URL}/health") as r:
                python_service = r.status == 200
    except Exception:
        python_service = False
    return {
        "mode": "webhook" if cfg.WEBHOOK_MODE else "polling",
        "baseUrl": EXTERNAL_WEBAPP_URL or learned_base_url or None,
        "relay": {"pythonService": python_service, "target": WEBHOOK_PY_URL,
                  "paths": {"game": "/webhook/game", "admin": "/webhook/admin"},
                  "stats": webhook_stats},
        "telegram": info,
        "keepalive": dict(self_ping),
    }


def _set_webhook_tasks(base: str, secret: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    allowed = ["message", "callback_query", "inline_query", "channel_post",
               "chat_member", "my_chat_member"]
    for kind, token in _tokens().items():
        if not token:
            results[kind] = {"ok": False, "error": "توکن تنظیم نشده"}
            continue
        url = f"{base}/webhook/{kind}"
        payload: dict[str, Any] = {"url": url, "drop_pending_updates": False,
                                   "allowed_updates": allowed}
        if secret:
            payload["secret_token"] = secret
        tg = config_service.telegram_api(token, "setWebhook", payload)
        results[kind] = {"ok": bool(tg.get("ok")), "url": url, "description": tg.get("description")}
    return results


def _delete_webhook_tasks() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for kind, token in _tokens().items():
        if not token:
            results[kind] = {"ok": False, "error": "توکن تنظیم نشده"}
            continue
        tg = config_service.telegram_api(token, "deleteWebhook", {"drop_pending_updates": False})
        results[kind] = {"ok": bool(tg.get("ok")), "description": tg.get("description")}
    return results


# ─────────────────────────── هندلرهای API ───────────────────────────

async def h_secrets(request: web.Request) -> web.Response:
    learn_base_url(request)
    tokens = _tokens()
    checks = {
        "gameBot": config_service.check_telegram_token(tokens["game"]) if tokens["game"] else None,
        "adminBot": config_service.check_telegram_token(tokens["admin"]) if tokens["admin"] else None,
    }
    return ok(config_service.secrets_payload(process_manager.status(), checks))


async def h_secrets_save(request: web.Request) -> web.Response:
    payload = await json_body(request)
    config_service.save_settings(payload)
    tokens = _tokens()
    checks = {
        "gameBot": config_service.check_telegram_token(tokens["game"]) if tokens["game"] else None,
        "adminBot": config_service.check_telegram_token(tokens["admin"]) if tokens["admin"] else None,
    }
    pid = await asyncio.get_running_loop().run_in_executor(None, process_manager.restart)
    return ok({
        "message": "تنظیمات با موفقیت در .env ذخیره و ربات‌ها بازراه‌اندازی شدند.",
        "pid": pid,
        "checks": checks,
    })


async def h_test_token(request: web.Request) -> web.Response:
    payload = await json_body(request)
    token = str(payload.get("token") or "").strip()
    if not token:
        return err("توکن ارسال نشده است.")
    return await asyncio.get_running_loop().run_in_executor(None, config_service.test_token, token)


async def h_test_firebase(request: web.Request) -> web.Response:
    payload = await json_body(request)
    result = await asyncio.get_running_loop().run_in_executor(
        None, config_service.test_firebase,
        str(payload.get("firebaseUrl") or ""), str(payload.get("firebaseAuth") or ""))
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


# ── کاربران ──
async def h_users(request: web.Request) -> web.Response:
    rows = await asyncio.get_running_loop().run_in_executor(None, data_service.list_users)
    return web.json_response(rows, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_user(request: web.Request) -> web.Response:
    user_id = int(request.match_info["id"])
    row = await asyncio.get_running_loop().run_in_executor(None, data_service.get_user, user_id)
    if not row:
        return err("کاربر یافت نشد", 404)
    return web.json_response(row, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_user_update(request: web.Request) -> web.Response:
    user_id = int(request.match_info["id"])
    payload = await json_body(request)
    result = await asyncio.get_running_loop().run_in_executor(
        None, data_service.update_user, user_id, payload)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_user_add(request: web.Request) -> web.Response:
    payload = await json_body(request)
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.add_user, payload)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_user_ban(request: web.Request) -> web.Response:
    user_id = int(request.match_info["id"])
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.toggle_ban, user_id)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_user_adjust(request: web.Request) -> web.Response:
    user_id = int(request.match_info["id"])
    payload = await json_body(request)
    result = await asyncio.get_running_loop().run_in_executor(
        None, data_service.adjust_balance, user_id,
        int(payload.get("moneyDelta") or 0), int(payload.get("coinsDelta") or 0))
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_user_admin(request: web.Request) -> web.Response:
    user_id = int(request.match_info["id"])
    payload = await json_body(request)
    result = await asyncio.get_running_loop().run_in_executor(
        None, data_service.toggle_admin, user_id, str(payload.get("name") or ""),
        1 if payload.get("isSuper") else 0)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_user_delete(request: web.Request) -> web.Response:
    user_id = int(request.match_info["id"])
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.delete_user, user_id)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_users_reset_players(request: web.Request) -> web.Response:
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.reset_all_players)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_users_reset_wealth(request: web.Request) -> web.Response:
    payload = await json_body(request)
    mode = str(payload.get("mode") or "both_default")
    result = await asyncio.get_running_loop().run_in_executor(
        None, data_service.reset_all_wealth, mode)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_users_sync(request: web.Request) -> web.Response:
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.sync_firebase)
    users = await asyncio.get_running_loop().run_in_executor(None, data_service.list_users)
    return web.json_response({**result, "users": users},
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_countries(request: web.Request) -> web.Response:
    rows = await asyncio.get_running_loop().run_in_executor(None, data_service.list_countries)
    return web.json_response(rows, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


# ── سلامت / پینگ بیدارباش / وبهوک ──
async def h_health(request: web.Request) -> web.Response:
    learn_base_url(request)
    return web.json_response(await health_payload(), dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_keepalive(request: web.Request) -> web.Response:
    if request.method == "POST":
        payload = await json_body(request)
        if isinstance(payload.get("enabled"), bool):
            self_ping["enabled"] = payload["enabled"]
        try:
            minutes = int(payload.get("intervalMinutes") or self_ping["intervalMinutes"])
            if minutes >= 1:
                self_ping["intervalMinutes"] = minutes
        except (TypeError, ValueError):
            pass
    return web.json_response({**self_ping, "target": resolve_self_url(),
                              "external": bool(EXTERNAL_WEBAPP_URL)},
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_keepalive_ping(request: web.Request) -> web.Response:
    state = await self_ping_once("manual")
    return web.json_response({**state, "success": state.get("lastStatus") == 200})


async def h_webhook_status(request: web.Request) -> web.Response:
    return web.json_response(await webhook_status_payload(),
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_webhook_set(request: web.Request) -> web.Response:
    payload = await json_body(request)
    base = str(payload.get("baseUrl") or EXTERNAL_WEBAPP_URL or learned_base_url or
               resolve_self_url(request)).rstrip("/")
    if not base:
        return err("آدرس عمومی مشخص نیست — baseUrl یا WEBHOOK_BASE_URL را تنظیم کنید")
    secret = str(payload.get("secret") or cfg.WEBHOOK_SECRET or "")
    results = await asyncio.get_running_loop().run_in_executor(None, _set_webhook_tasks, base, secret)
    globals()["learned_base_url"] = base
    return ok({"baseUrl": base, "results": results},
              success=any(r.get("ok") for r in results.values()))


async def h_webhook_delete(request: web.Request) -> web.Response:
    results = await asyncio.get_running_loop().run_in_executor(None, _delete_webhook_tasks)
    return ok({"results": results}, success=any(r.get("ok") for r in results.values()))


async def h_webhook_mode(request: web.Request) -> web.Response:
    payload = await json_body(request)
    mode = str(payload.get("mode") or "").lower()
    if mode not in ("webhook", "polling"):
        return err("mode باید 'webhook' یا 'polling' باشد")
    want_webhook = mode == "webhook"
    update: dict[str, Any] = {"WEBHOOK_MODE": "1" if want_webhook else "0"}
    if payload.get("baseUrl"):
        update["WEBHOOK_BASE_URL"] = str(payload["baseUrl"]).rstrip("/")
    if payload.get("secret"):
        update["WEBHOOK_SECRET"] = str(payload["secret"])
    config_service.save_settings(update)
    base = str(payload.get("baseUrl") or cfg.PUBLIC_BASE_URL or EXTERNAL_WEBAPP_URL
               or learned_base_url or "").rstrip("/")
    loop = asyncio.get_running_loop()
    if want_webhook:
        if not base:
            return err("baseUrl لازم است")
        wb = await loop.run_in_executor(None, _set_webhook_tasks, base, cfg.WEBHOOK_SECRET)
    else:
        wb = await loop.run_in_executor(None, _delete_webhook_tasks)
    pid = await loop.run_in_executor(None, process_manager.restart)
    return ok({"mode": mode, "pid": pid, "webhook": wb})


async def h_webhook_relay_game(request: web.Request) -> web.Response:
    return await relay_webhook("game", request)


async def h_webhook_relay_admin(request: web.Request) -> web.Response:
    return await relay_webhook("admin", request)


# ── پروسهٔ ربات‌ها ──
async def h_bot_status(request: web.Request) -> web.Response:
    return web.json_response(process_manager.status(),
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_bot_logs(request: web.Request) -> web.Response:
    lines = await asyncio.get_running_loop().run_in_executor(None, process_manager.logs)
    return web.json_response({"logs": lines, "pid": process_manager.pid},
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_bot_restart(request: web.Request) -> web.Response:
    pid = await asyncio.get_running_loop().run_in_executor(None, process_manager.restart)
    return ok({"message": "ربات‌ها با موفقیت ری‌استارت شدند", "pid": pid})


async def h_bot_start(request: web.Request) -> web.Response:
    pid = await asyncio.get_running_loop().run_in_executor(None, process_manager.start)
    return ok({"message": "ربات‌ها فعال شدند", "pid": pid})


async def h_bot_stop(request: web.Request) -> web.Response:
    await asyncio.get_running_loop().run_in_executor(None, process_manager.stop)
    return ok({"message": "ربات‌ها متوقف شدند"})


# ── بازی / دیتابیس ──
async def h_game_metadata(request: web.Request) -> web.Response:
    return web.json_response(game_meta.metadata(),
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_simulate_battle(request: web.Request) -> web.Response:
    payload = await json_body(request)
    result = game_meta.simulate_battle(payload.get("attacker") or {}, payload.get("defender") or {})
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_db_stats(request: web.Request) -> web.Response:
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.database_stats)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_db_table(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.read_table, name)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_db_backup(request: web.Request) -> web.Response:
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.backup_database)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def h_files_read(request: web.Request) -> web.Response:
    rel = request.query.get("path", "")
    if not rel:
        return err("path is required")
    result = await asyncio.get_running_loop().run_in_executor(None, data_service.read_source_file, rel)
    if "error" in result and "type" not in result:
        return err(result["error"], 404)
    return web.json_response(result, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


# ─────────────────────────── سرو کردن رابط کاربری ───────────────────────────

async def h_index(request: web.Request) -> web.StreamResponse:
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return web.FileResponse(index_file)
    return web.Response(text=_dev_placeholder(), content_type="text/html", charset="utf-8")


def _dev_placeholder() -> str:
    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>پنل فرماندهی جنگ جهانی — سرور پایتونی</title>
<style>body{{font-family:system-ui,sans-serif;background:#020617;color:#e2e8f0;padding:48px;line-height:2}}
code,pre{{background:#0f172a;padding:4px 8px;border-radius:6px;display:inline-block}}
a{{color:#38bdf8}}</style></head><body>
<h1>✅ سرور پایتونی پنل بالا آمد</h1>
<p>پوشهٔ رابط کاربری ساخته‌شده (<code>{DIST_DIR}</code>) پیدا نشد. برای ساخت آن یک بار اجرا کنید:</p>
<pre>cd {REPO_ROOT}
npm install --legacy-peer-deps
npx vite build</pre>
<p>یا در حالت توسعه، Vite را جدا اجرا و آدرس آن را با
<code>VITE_DEV_URL=http://127.0.0.1:5173</code> به این سرور بدهید.</p>
<p>وضعیت سرویس و ربات‌ها: <a href="/health">/health</a> •
آمار دیتابیس: <a href="/api/db/stats">/api/db/stats</a> •
فراداده بازی: <a href="/api/game/metadata">/api/game/metadata</a></p>
</body></html>"""


async def h_static(request: web.Request) -> web.StreamResponse:
    rel = request.match_info.get("path", "")
    target = (DIST_DIR / rel).resolve()
    if DIST_DIR.resolve() in target.parents and target.is_file():
        ctype, _ = mimetypes.guess_type(str(target))
        return web.FileResponse(target, headers={"Content-Type": ctype or "application/octet-stream"})
    # SPA fallback
    return await h_index(request)


async def h_dev_proxy(request: web.Request) -> web.StreamResponse:
    """در حالت توسعه، درخواست‌های صفحه را به سرور Vite (npm run dev) پاس می‌دهیم."""
    target_base = os.getenv("VITE_DEV_URL", "http://127.0.0.1:5173").rstrip("/")
    url = f"{target_base}{request.rel_url}"
    try:
        async with ClientSession(timeout=ClientTimeout(total=20)) as session:
            async with session.get(url, headers={"accept": request.headers.get("accept", "*/*")}) as r:
                body = await r.read()
                headers = {k: v for k, v in r.headers.items()
                           if k.lower() not in ("content-encoding", "transfer-encoding", "connection")}
                return web.Response(body=body, status=r.status, headers=headers)
    except Exception:
        return web.Response(text=_dev_placeholder(), content_type="text/html", charset="utf-8")


# ─────────────────────────── ساخت برنامه ───────────────────────────

def create_app(game_bot: Any = None, game_dp: Any = None,
               admin_bot: Any = None, admin_dp: Any = None,
               autostart: bool = False) -> web.Application:
    app = web.Application(client_max_size=16 * 1024 * 1024)
    app["bots"] = {"game": game_bot, "admin": admin_bot}
    app["dps"] = {"game": game_dp, "admin": admin_dp}

    r = app.router
    # سلامت و مانیتورینگ
    for method in ("GET", "HEAD"):
        r.add_route(method, "/health", h_health)
        r.add_route(method, "/api/health", h_health)
        r.add_route(method, "/api/bot-process/status", h_bot_status)
    r.add_get("/api/keepalive", h_keepalive)
    r.add_post("/api/keepalive", h_keepalive)
    r.add_post("/api/keepalive/ping", h_keepalive_ping)

    # تنظیمات و توکن‌ها
    r.add_get("/api/secrets", h_secrets)
    r.add_post("/api/secrets", h_secrets_save)
    r.add_post("/api/test-token", h_test_token)
    r.add_post("/api/test-firebase", h_test_firebase)

    # کاربران
    r.add_get("/api/users", h_users)
    r.add_post("/api/users", h_user_add)
    r.add_post("/api/users/sync", h_users_sync)
    r.add_post("/api/users/reset-all-players", h_users_reset_players)
    r.add_post("/api/users/reset-all-wealth", h_users_reset_wealth)
    r.add_get("/api/users/{id}", h_user)
    r.add_put("/api/users/{id}", h_user_update)
    r.add_delete("/api/users/{id}", h_user_delete)
    r.add_post("/api/users/{id}/ban", h_user_ban)
    r.add_post("/api/users/{id}/adjust", h_user_adjust)
    r.add_post("/api/users/{id}/admin", h_user_admin)
    r.add_get("/api/countries", h_countries)

    # وبهوک
    r.add_post("/webhook/game", h_webhook_relay_game)
    r.add_post("/webhook/admin", h_webhook_relay_admin)
    r.add_get("/api/webhook/status", h_webhook_status)
    r.add_post("/api/webhook/set", h_webhook_set)
    r.add_post("/api/webhook/delete", h_webhook_delete)
    r.add_post("/api/webhook/mode", h_webhook_mode)

    # پروسهٔ ربات‌ها
    r.add_get("/api/bot-process/logs", h_bot_logs)
    r.add_post("/api/bot-process/restart", h_bot_restart)
    r.add_post("/api/bot-process/start", h_bot_start)
    r.add_post("/api/bot-process/stop", h_bot_stop)

    # بازی / دیتابیس / فایل‌ها
    r.add_get("/api/game/metadata", h_game_metadata)
    r.add_post("/api/simulate/battle", h_simulate_battle)
    r.add_get("/api/db/stats", h_db_stats)
    r.add_get("/api/db/table/{name}", h_db_table)
    r.add_post("/api/db/backup", h_db_backup)
    r.add_get("/api/files/read", h_files_read)

    # رابط کاربری
    dev_proxy = os.getenv("VITE_DEV_URL", "").strip()
    if DIST_DIR.exists() and (DIST_DIR / "index.html").exists():
        r.add_get("/assets/{path:.*}", h_static)
        r.add_get("/{path:.*}", h_static)
    elif dev_proxy:
        r.add_get("/{path:.*}", h_dev_proxy)
    else:
        r.add_get("/{path:.*}", h_index)

    async def _on_startup(app: web.Application) -> None:
        app["keepalive_task"] = asyncio.create_task(keepalive_loop(app))
        # اجرای خودکار ربات‌ها فقط از طریق run_all.py/serve.py یا AUTOSTART_BOTS=1
        if autostart and cfg.BOTS_AUTOSTART:
            await asyncio.get_running_loop().run_in_executor(None, process_manager.autostart)
        elif autostart:
            log.info("[Bots] اجرای خودکار ربات‌ها خاموش است (AUTOSTART_BOTS=0)")

    async def _on_cleanup(app: web.Application) -> None:
        task = app.get("keepalive_task")
        if task:
            task.cancel()
        process_manager.stop_watchdog()

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app


async def run(host: str, port: int, web_only: bool = False) -> None:
    try:
        from core.db import init_db
        await init_db()
    except Exception as exc:  # noqa: BLE001
        log.warning("آماده‌سازی دیتابیس انجام نشد (پنل باز هم بالا می‌آید): %s", exc)

    game_bot = game_dp = admin_bot = admin_dp = None
    if not web_only and cfg.WEBHOOK_MODE:
        try:
            from adminbot.main import create_dispatcher as create_admin_dp
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            from gamebot.main import create_dispatcher as create_game_dp
            if cfg.GAME_BOT_TOKEN:
                game_bot = Bot(cfg.GAME_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                game_dp = create_game_dp()
            if cfg.ADMIN_BOT_TOKEN:
                admin_bot = Bot(cfg.ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                admin_dp = create_admin_dp()
        except Exception as exc:  # noqa: BLE001
            log.warning("ساخت ربات‌های وبهوک ناموفق بود: %s", exc)

    app = create_app(game_bot, game_dp, admin_bot, admin_dp, autostart=not web_only)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("🌐 پنل فرماندهی جنگ جهانی (پایتون) روی http://%s:%s", host, port)
    log.info("   سلامت سرویس: /health   |   توکن‌ها: /api/secrets")
    try:
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await runner.cleanup()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    parser = argparse.ArgumentParser(description="سرور وب پنل فرماندهی بازی جنگ جهانی (پایتون)")
    parser.add_argument("--host", default=cfg.WEB_HOST)
    parser.add_argument("--port", type=int, default=cfg.WEB_PORT)
    parser.add_argument("--web-only", action="store_true", help="فقط پنل وب؛ ربات‌ها اجرا نشوند")
    parser.add_argument("--no-autostart", action="store_true", help="ربات‌ها خودکار اجرا نشوند")
    args = parser.parse_args(argv)
    if args.no_autostart:
        os.environ["AUTOSTART_BOTS"] = "0"
        cfg.BOTS_AUTOSTART = False
    try:
        asyncio.run(run(args.host, args.port, web_only=args.web_only))
    except KeyboardInterrupt:
        log.info("سرور وب متوقف شد.")


if __name__ == "__main__":
    sys.path.insert(0, str(cfg.BASE_DIR))
    main()

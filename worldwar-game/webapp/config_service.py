"""سرویس تنظیمات وب — خواندن/نوشتن توکن‌ها و آیدی ادمین در فایل .env.

کل منطق «دریافت سکرت‌ها» و «ذخیرهٔ سکرت‌ها» که قبلاً در `server.ts` نوشته شده بود،
این‌جا با پایتون بازنویسی شده است. توکن‌های پیش‌فرض از `core/config.py` می‌آیند
و پنل وب می‌تواند آن‌ها را در `worldwar-game/.env` تغییر دهد.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import core.config as cfg

ENV_PATH: Path = cfg.BASE_DIR / ".env"
_TokenCache = dict[str, tuple[float, dict[str, Any]]]
_token_cache: _TokenCache = {}
TOKEN_CACHE_TTL = 30  # ثانیه


# ─────────────────────────── فایل .env ───────────────────────────

def parse_env_file(path: Path | str | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    p = Path(path) if path is not None else ENV_PATH
    if not p.exists():
        return result
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, val = s.split("=", 1)
            result[key.strip()] = val.strip()
    except Exception:
        pass
    return result


def write_env_file(data: dict[str, str], path: Path | str | None = None) -> None:
    """نوشتن تنظیمات در .env با ساختار خوانا (همان کلیدهایی که ربات‌ها می‌خوانند)."""
    p = Path(path) if path is not None else ENV_PATH
    db_path = str((cfg.BASE_DIR / "wwgame.db").resolve())
    lines = [
        "# ─── تنظیمات بازی جنگ جهانی ───",
        "# این فایل توسط پنل وب (worldwar-game/webapp) یا دستی به‌روزرسانی شده است",
        "",
        "# توکن ربات اصلی بازی (از @BotFather)",
        f"GAME_BOT_TOKEN={data.get('GAME_BOT_TOKEN') or cfg.DEFAULT_GAME_BOT_TOKEN}",
        "",
        "# توکن ربات ادمین (ربات جداگانه از @BotFather)",
        f"ADMIN_BOT_TOKEN={data.get('ADMIN_BOT_TOKEN') or cfg.DEFAULT_ADMIN_BOT_TOKEN}",
        "",
        "# آیدی عددی ادمین کل (سوپرادمین)",
        f"SUPER_ADMIN_ID={data.get('SUPER_ADMIN_ID') or cfg.DEFAULT_ADMIN_ID}",
        f"SUPER_ADMIN_IDS={data.get('SUPER_ADMIN_IDS') or ''}",
        f"DB_PATH={data.get('DB_PATH') or db_path}",
        "",
        "# ─── اتصال فایربیس (اختیاری) ───",
        f"FIREBASE_DB_URL={data.get('FIREBASE_DB_URL') or ''}",
        f"FIREBASE_AUTH={data.get('FIREBASE_AUTH') or ''}",
        "",
        "# ─── وبهوک تلگرام و پینگ بیدارباش ───",
        f"WEBHOOK_MODE={data.get('WEBHOOK_MODE') or '0'}",
        f"WEBHOOK_BASE_URL={data.get('WEBHOOK_BASE_URL') or ''}",
        f"WEBHOOK_PORT={data.get('WEBHOOK_PORT') or '8080'}",
        f"WEBHOOK_SECRET={data.get('WEBHOOK_SECRET') or ''}",
        f"KEEPALIVE_MINUTES={data.get('KEEPALIVE_MINUTES') or '10'}",
    ]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def current_settings() -> dict[str, str]:
    """تنظیمات فعال = مقادیر .env روی پیش‌فرض‌های داخل کد."""
    return {
        "GAME_BOT_TOKEN": cfg.GAME_BOT_TOKEN,
        "ADMIN_BOT_TOKEN": cfg.ADMIN_BOT_TOKEN,
        "SUPER_ADMIN_ID": str(cfg.SUPER_ADMIN_ID),
        "FIREBASE_DB_URL": os.getenv("FIREBASE_DB_URL", ""),
        "FIREBASE_AUTH": os.getenv("FIREBASE_AUTH", ""),
        "WEBHOOK_MODE": "1" if cfg.WEBHOOK_MODE else "0",
        "WEBHOOK_BASE_URL": cfg.PUBLIC_BASE_URL,
        "WEBHOOK_PORT": str(cfg.WEBHOOK_PORT),
        "WEBHOOK_SECRET": cfg.WEBHOOK_SECRET,
        "KEEPALIVE_MINUTES": str(cfg.KEEPALIVE_MINUTES),
    }


def save_settings(payload: dict[str, Any]) -> dict[str, str]:
    """ذخیرهٔ مقادیر ورودی پنل در .env و بازخوانی کانفیگ در همان پروسه."""
    saved = parse_env_file()
    saved.update(current_settings())
    for key in ("GAME_BOT_TOKEN", "ADMIN_BOT_TOKEN", "SUPER_ADMIN_ID", "SUPER_ADMIN_IDS",
                "DB_PATH", "FIREBASE_DB_URL", "FIREBASE_AUTH", "WEBHOOK_MODE",
                "WEBHOOK_BASE_URL", "WEBHOOK_PORT", "WEBHOOK_SECRET", "KEEPALIVE_MINUTES"):
        if key in payload and payload[key] is not None:
            saved[key] = str(payload[key]).strip()
    write_env_file(saved)

    # بازخوانی فوری تنظیمات در همین پروسه (بدون نیاز به ری‌استارت)
    os.environ.update({k: v for k, v in saved.items() if v})
    cfg.GAME_BOT_TOKEN = saved.get("GAME_BOT_TOKEN") or cfg.DEFAULT_GAME_BOT_TOKEN
    cfg.ADMIN_BOT_TOKEN = saved.get("ADMIN_BOT_TOKEN") or cfg.DEFAULT_ADMIN_BOT_TOKEN
    cfg.SUPER_ADMIN_ID = int(saved.get("SUPER_ADMIN_ID") or cfg.DEFAULT_ADMIN_ID)
    cfg.SUPER_ADMIN_IDS = tuple(dict.fromkeys([cfg.SUPER_ADMIN_ID, *cfg.DEFAULT_SUPER_ADMIN_IDS]))
    if saved.get("WEBHOOK_MODE") is not None:
        cfg.WEBHOOK_MODE = str(saved.get("WEBHOOK_MODE")).lower() in ("1", "true", "yes")
    if saved.get("WEBHOOK_BASE_URL") is not None:
        cfg.PUBLIC_BASE_URL = str(saved.get("WEBHOOK_BASE_URL")).rstrip("/")
    if saved.get("WEBHOOK_SECRET") is not None:
        cfg.WEBHOOK_SECRET = str(saved.get("WEBHOOK_SECRET"))
    _token_cache.clear()
    return current_settings()


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 18:
        return token[:4] + "..." + token[-3:]
    return f"{token[:10]}...{token[-5:]}"


def secrets_payload(bot_process: dict[str, Any] | None = None,
                    checks: dict[str, Any] | None = None) -> dict[str, Any]:
    """پاسخ /api/secrets — همان ساختاری که پنل React انتظار دارد."""
    s = current_settings()
    return {
        "configured": {
            "GAME_BOT_TOKEN": mask_token(s["GAME_BOT_TOKEN"]),
            "ADMIN_BOT_TOKEN": mask_token(s["ADMIN_BOT_TOKEN"]),
            "SUPER_ADMIN_ID": s["SUPER_ADMIN_ID"],
            "SUPER_ADMIN_IDS": list(cfg.SUPER_ADMIN_IDS),
            "DB_PATH": cfg.DB_PATH,
            "FIREBASE_DB_URL": s["FIREBASE_DB_URL"],
            "FIREBASE_AUTH": "••••••••" if s["FIREBASE_AUTH"] else "",
            "WEBHOOK_MODE": s["WEBHOOK_MODE"],
            "KEEPALIVE_MINUTES": s["KEEPALIVE_MINUTES"],
            "hasFullGameToken": bool(s["GAME_BOT_TOKEN"]),
            "hasFullAdminToken": bool(s["ADMIN_BOT_TOKEN"]),
            # توکن کامل برای فرم ویرایش پنل (همان رفتار نسخهٔ قبلی)
            "rawGameToken": s["GAME_BOT_TOKEN"],
            "rawAdminToken": s["ADMIN_BOT_TOKEN"],
        },
        "checks": checks or {},
        "process": bot_process or {"isRunning": False, "pid": None},
        "files": {
            "hasEnv": ENV_PATH.exists(),
            "hasDb": Path(cfg.DB_PATH).exists(),
            "hasSource": (cfg.BASE_DIR).exists(),
        },
    }


# ─────────────────────────── تست توکن تلگرام ───────────────────────────

def _http_json(method: str, url: str, payload: dict[str, Any] | None = None,
               timeout: float = 15.0) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def telegram_api(token: str, method: str, payload: dict[str, Any] | None = None,
                 timeout: float = 15.0) -> dict[str, Any]:
    """فراخوانی متد Bot API تلگرام (با توکن) و برگرداندن JSON."""
    try:
        return _http_json("POST", f"https://api.telegram.org/bot{token}/{method}",
                          payload or {}, timeout=timeout)
    except urllib.error.HTTPError as exc:  # تلگرام خطاها را با 4xx/5xx و JSON می‌دهد
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "description": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc),
                "description": "خطا در برقراری ارتباط با سرور تلگرام"}


def check_telegram_token(token: str) -> dict[str, Any]:
    """getMe با کش ۳۰ ثانیه‌ای — برای نمایش وضعیت آنلاین ربات‌ها در پنل."""
    if not token or ":" not in token:
        return {"ok": False, "error": "فرمت توکن نامعتبر است (باید شامل شناسه و رشتهٔ توکن با «:» باشد)"}
    now = time.time()
    cached = _token_cache.get(token)
    if cached and now - cached[0] < TOKEN_CACHE_TTL:
        return cached[1]
    result = telegram_api(token, "getMe")
    _token_cache[token] = (now, result)
    return result


def test_token(token: str) -> dict[str, Any]:
    """/api/test-token — بدون کش تا نتیجهٔ واقعی برگردد."""
    return telegram_api((token or "").strip(), "getMe")


# ─────────────────────────── فایربیس ───────────────────────────

def test_firebase(url: str, auth: str = "") -> dict[str, Any]:
    """/api/test-firebase — تست واقعی اتصال به Firebase Realtime Database."""
    if not url:
        return {"ok": False, "error": "آدرس فایربیس (FIREBASE_DB_URL) وارد نشده است."}
    clean = re.sub(r"/+$", "", url.strip())
    if not clean.startswith("https://"):
        return {"ok": False, "error": "آدرس فایربیس باید با https:// شروع شود."}
    target = f"{clean}/status.json"
    if auth and auth.strip():
        target += "?auth=" + urllib.parse.quote(auth.strip())
    started = time.time()
    try:
        body = _http_json("GET", target, timeout=8.0)
    except urllib.error.HTTPError as exc:
        latency = int((time.time() - started) * 1000)
        if exc.code in (401, 403):
            return {"ok": False, "statusCode": exc.code, "latencyMs": latency,
                    "error": "خطای عدم دسترسی (Permission Denied). قوانین Realtime Database "
                             "باید مجوز خواندن/نوشتن بدهند یا Database Secret در FIREBASE_AUTH باشد."}
        if exc.code == 404:
            return {"ok": False, "statusCode": 404, "latencyMs": latency,
                    "error": "مسیر دیتابیس یافت نشد (404). بررسی کنید Realtime Database فعال باشد."}
        return {"ok": False, "statusCode": exc.code, "latencyMs": latency,
                "error": f"پاسخ سرور فایربیس (HTTP {exc.code})"}
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        friendly = "مهلت زمانی اتصال تمام شد (Timeout)" if "timed out" in msg.lower() else msg
        return {"ok": False, "error": friendly or "خطا در برقراری ارتباط با فایربیس"}
    latency = int((time.time() - started) * 1000)
    return {"ok": True, "statusCode": 200, "latencyMs": latency, "url": clean,
            "message": "اتصال به Firebase Realtime Database با موفقیت برقرار شد!", "data": body}

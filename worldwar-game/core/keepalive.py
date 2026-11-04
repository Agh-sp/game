"""پینگ بیدارباش (Keep-alive).

هر ``KEEPALIVE_MINUTES`` دقیقه یک درخواست فیک به آدرس Web App زده می‌شود تا سرویس
(و در نتیجه خود ربات) توسط هاست خواب نرود. این ماژول عمداً هیچ وابستگی به بقیهٔ
بازی ندارد تا اگر Web App خاموش بود، خطایی در ربات ایجاد نکند.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

from aiohttp import ClientSession, ClientTimeout

log = logging.getLogger("keepalive")

STATS = {"count": 0, "last_at": None, "last_ok": None, "target": ""}


def resolve_webapp_url() -> str:
    """آدرس Web App برای پینگ (اول WEBAPP_URL، بعد 127.0.0.1:PORT)."""
    for key in ("WEBAPP_URL", "PUBLIC_URL", "SELF_URL", "WEBHOOK_BASE_URL"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value.rstrip("/")
    port = os.getenv("PORT") or os.getenv("WEBHOOK_PORT") or "3000"
    return f"http://127.0.0.1:{port}"


def keepalive_minutes() -> int:
    try:
        return max(1, int(float(os.getenv("KEEPALIVE_MINUTES", "10") or 10)))
    except (TypeError, ValueError):
        return 10


async def ping_once(base: str | None = None, timeout: float = 15.0) -> bool:
    """یک درخواست فیک به ``/health`` می‌زند؛ True اگر پاسخ ۲۰۰ بود."""
    target = (base or resolve_webapp_url()).rstrip("/")
    STATS["target"] = target
    ok = False
    try:
        async with ClientSession(timeout=ClientTimeout(total=timeout)) as session:
            async with session.get(f"{target}/health?ping=1",
                                   headers={"X-Keepalive": "1",
                                            "User-Agent": "wwgame-bot-keepalive/1.0"}) as resp:
                ok = resp.status == 200
    except Exception as exc:
        log.warning("پینگ بیدارباش ناموفق (%s): %s", target, exc)
    STATS["count"] += 1
    STATS["last_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    STATS["last_ok"] = ok
    return ok


async def keepalive_loop(base: str | None = None, minutes: int | None = None) -> None:
    """حلقهٔ بی‌پایان پینگ (برای استفاده به‌صورت asyncio.create_task)."""
    interval = (minutes or keepalive_minutes()) * 60
    await asyncio.sleep(min(20, interval))  # فرصت بالا آمدن سرویس
    while True:
        ok = await ping_once(base)
        log.info("💓 پینگ سلامت %s: %s", STATS["target"], "ok" if ok else "failed")
        await asyncio.sleep(interval)


def start_keepalive(base: str | None = None, minutes: int | None = None) -> asyncio.Task | None:
    """شروع پینگ در پس‌زمینه؛ با KEEPALIVE=0 خاموش می‌شود."""
    if str(os.getenv("KEEPALIVE", "1")).lower() in ("0", "false", "no", "off"):
        log.info("پینگ بیدارباش خاموش است (KEEPALIVE=0)")
        return None
    task = asyncio.create_task(keepalive_loop(base, minutes))
    log.info("💓 پینگ بیدارباش هر %s دقیقه به %s", minutes or keepalive_minutes(),
             (base or resolve_webapp_url()).rstrip("/"))
    return task

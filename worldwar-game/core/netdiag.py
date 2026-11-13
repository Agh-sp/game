"""🌐 عیب‌یابی و اصلاح خودکار مسیر شبکهٔ aiohttp.

چرا این ماژول لازم است؟
روی برخی هاست‌ها (مثلاً PythonAnywhere پلن رایگان) `urllib`/`requests` وصل
می‌شوند ولی `aiohttp` با خطای زیر شکست می‌خورد:

    ClientConnectorError: Cannot connect to host api.telegram.org:443 ssl:default [None]

سه علت رایج دارد و این ماژول هر سه را خودکار امتحان می‌کند:

1. 🧱 **فایروال خروجی**: ترافیک فقط از پروکسی هاست (`proxy.server:3128`) می‌گذرد،
   ولی `aiohttp` به‌صورت پیش‌فرض `trust_env=False` است و پروکسی را نادیده می‌گیرد.
   → راه‌حل: `trust_env=True` یا پاس‌دادن صریح `proxy=`.
2. 🏠 **پروکسی محیط کار نکرد**: `HTTP_PROXY` اشتباه/قدیمی در محیط تنظیم شده.
   → راه‌حل: پاک‌کردن پروکسی و تست اتصال مستقیم.
3. 🔐 **TLS/SNI محلی**: بعضی شبکه‌ها با گواهی محلی کار می‌کنند و `ssl.create_default_context()`
   شکست می‌خورد.
   → راه‌حل: ساخت کانتکست SSL بدون بررسی گواهی (فقط برای تماس با تلگرام).

نتیجه به‌صورت `dict` برمی‌گردد و در لاگ نوشته می‌شود تا در همان نگاه اول معلوم باشد
کدام مسیر جواب داده است.
"""
from __future__ import annotations

import logging
import os
import socket
import ssl
from typing import Any

log = logging.getLogger(__name__)

PAW_PROXY_URL = "http://proxy.server:3128"
FLAG_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
TEST_HOST = os.getenv("NET_TEST_HOST", "api.telegram.org")
TEST_PORT = 443

_CHOSEN: dict[str, Any] = {"ready": False, "mode": "", "proxy": "", "insecure_ssl": False}


def _env_flag(name: str) -> str:
    return (os.getenv(name, "") or "").strip().lower()


def proxy_enabled(force: bool | None = None) -> bool:
    """آیا پروکسی هاست استفاده شود؟ (PAW_PROXY بر تشخیص خودکار اولویت دارد)"""
    if force is not None:
        return bool(force)
    flag = _env_flag("PAW_PROXY")
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    return "pythonanywhere" in (os.getenv("PYTHONANYWHERE_DOMAIN", "") or "")


def system_ssl_context():
    """کانتکست SSL بر پایهٔ مخزن گواهی **سیستم** (همان چیزی که urllib استفاده می‌کند).

    aiogram به‌صورت پیش‌فرض فقط `certifi` را می‌شناسد؛ اگر هاست یک CA محلی
    (MITM/فایروال شفاف) داشته باشد، `urllib` وصل می‌شود ولی `aiohttp` شکست
    می‌خورد. این تابع هر دو مخزن را با هم بار می‌کند.
    """
    ctx = ssl.create_default_context()          # مخزن سیستم + متغیرهای SSL_CERT_*
    try:
        import certifi
        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:
        pass
    extra = (os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or "").strip()
    if extra and os.path.exists(extra):
        try:
            ctx.load_verify_locations(cafile=extra)
        except Exception:
            pass
    return ctx


async def _aiohttp_can_connect(proxy: str | None = None,
                               insecure: bool = False,
                               trust_env: bool = False,
                               system_ca: bool = False,
                               timeout: float = 8.0) -> tuple[bool, str]:
    """آیا aiohttp می‌تواند به تلگرام وصل شود؟ (اتصال واقعی، بدون ارسال داده)"""
    import aiohttp

    kwargs: dict[str, Any] = {"trust_env": trust_env}
    if system_ca:
        kwargs["connector"] = aiohttp.TCPConnector(ssl=system_ssl_context())
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["connector"] = aiohttp.TCPConnector(ssl=ctx)
    try:
        async with aiohttp.ClientSession(**kwargs) as session:
            async with session.get(
                    f"https://{TEST_HOST}/", proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                await resp.read()
                return True, f"HTTP {resp.status}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def _socket_can_connect(host: str = TEST_HOST, port: int = TEST_PORT,
                        timeout: float = 6.0) -> bool:
    """تست خام TCP (بدون TLS) — فقط برای تشخیص اینکه DNS/شبکه کار می‌کند."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def diagnose() -> dict:
    """امتحان همهٔ حالت‌ها و انتخاب اولین حالتی که کار می‌کند."""
    results: list[dict] = []

    # ۰) وضعیت پایه: DNS/TCP
    tcp = _socket_can_connect()
    results.append({"mode": "tcp", "ok": tcp,
                    "detail": "اتصال TCP خام"})

    # ۱) مستقیم با تنظیمات محیط
    ok, detail = await _aiohttp_can_connect(trust_env=True)
    results.append({"mode": "env", "ok": ok, "detail": detail})
    if ok:
        return _finish(results, "env")

    # ۲) مستقیم بدون پروکسی محیط (اگر پروکسی خراب در محیط مانده باشد)
    for key in FLAG_KEYS:
        os.environ.pop(key, None)
    ok, detail = await _aiohttp_can_connect(trust_env=False)
    results.append({"mode": "direct", "ok": ok, "detail": detail})
    if ok:
        return _finish(results, "direct")

    # ۲b) مستقیم با مخزن گواهی سیستم (رفع اختلاف urllib/aiohttp)
    ok, detail = await _aiohttp_can_connect(system_ca=True)
    results.append({"mode": "direct+system-ca", "ok": ok, "detail": detail,
                    "system_ca": True})
    if ok:
        return _finish(results, "direct+system-ca", system_ca=True)

    # ۳) مستقیم با SSL آسان‌گیر
    ok, detail = await _aiohttp_can_connect(insecure=True)
    results.append({"mode": "direct+insecure-ssl", "ok": ok, "detail": detail,
                    "insecure_ssl": True})
    if ok:
        return _finish(results, "direct+insecure-ssl", insecure_ssl=True)

    # ۴) از طریق پروکسی هاست (صریح)
    for key in FLAG_KEYS:
        os.environ[key] = PAW_PROXY_URL
    ok, detail = await _aiohttp_can_connect(proxy=PAW_PROXY_URL, trust_env=False)
    results.append({"mode": "paw-proxy", "ok": ok, "detail": detail,
                    "proxy": PAW_PROXY_URL})
    if ok:
        return _finish(results, "paw-proxy", proxy=PAW_PROXY_URL)

    # ۵) پروکسی + SSL آسان‌گیر
    ok, detail = await _aiohttp_can_connect(proxy=PAW_PROXY_URL, insecure=True,
                                            trust_env=False)
    results.append({"mode": "paw-proxy+insecure-ssl", "ok": ok, "detail": detail,
                    "proxy": PAW_PROXY_URL, "insecure_ssl": True})
    if ok:
        return _finish(results, "paw-proxy+insecure-ssl", proxy=PAW_PROXY_URL,
                       insecure_ssl=True)

    return _finish(results, "")


def _finish(results: list[dict], mode: str, proxy: str = "",
            insecure_ssl: bool = False, system_ca: bool = False) -> dict:
    for r in results:
        mark = "✅" if r["ok"] else "❌"
        log.info("%s مسیر %-24s %s", mark, r["mode"], r["detail"][:100])
    if mode:
        log.info("🌐 مسیر انتخاب‌شده برای تلگرام: %s%s", mode,
                 f" (پروکسی {proxy})" if proxy else "")
    else:
        log.error("⛔️ هیچ مسیری به api.telegram.org باز نشد — "
                  "فایروال هاست دسترسی را بسته است. با پشتیبانی هاست تماس بگیرید.")
    _CHOSEN.update(ready=bool(mode), mode=mode, proxy=proxy,
                   insecure_ssl=insecure_ssl, system_ca=system_ca)
    return {"chosen": mode, "proxy": proxy, "insecure_ssl": insecure_ssl,
            "system_ca": system_ca, "ready": bool(mode), "results": results}


def apply(chosen: dict | None = None) -> None:
    """اعمال مسیر انتخاب‌شده روی aiohttp (idempotent)."""
    if chosen:
        _CHOSEN.update({k: chosen.get(k) for k in
                        ("mode", "proxy", "insecure_ssl", "ready")})
    import aiohttp

    if getattr(aiohttp.ClientSession, "_ww_net_patched", False):
        return
    original_init = aiohttp.ClientSession.__init__
    want_proxy = _CHOSEN.get("proxy") or ""
    insecure = bool(_CHOSEN.get("insecure_ssl"))
    use_system_ca = bool(_CHOSEN.get("system_ca"))

    def _init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        # پروکسی محیط را فقط وقتی می‌پذیریم که واقعاً انتخاب شده باشد
        kwargs.setdefault("trust_env", bool(want_proxy) or _CHOSEN["mode"] == "env")
        if want_proxy:
            kwargs.setdefault("proxy", want_proxy)
        if insecure and not kwargs.get("connector"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs["connector"] = aiohttp.TCPConnector(ssl=ctx)
        elif use_system_ca and not kwargs.get("connector"):
            kwargs["connector"] = aiohttp.TCPConnector(ssl=system_ssl_context())
        return original_init(self, *args, **kwargs)

    aiohttp.ClientSession.__init__ = _init  # type: ignore[method-assign]
    aiohttp.ClientSession._ww_net_patched = True  # type: ignore[attr-defined]
    log.info("🔧 پچ شبکه اعمال شد (مسیر: %s)", _CHOSEN.get("mode") or "پیش‌فرض")


async def setup(auto: bool = True, force_proxy: bool | None = None) -> dict:
    """عیب‌یابی + انتخاب مسیر + اعمال پچ. خروجی: نتیجهٔ کامل تشخیص."""
    if force_proxy is not None:
        if force_proxy:
            for key in FLAG_KEYS:
                os.environ[key] = PAW_PROXY_URL
        else:
            for key in FLAG_KEYS:
                os.environ.pop(key, None)
    if not auto:
        apply({"ready": True, "mode": "manual", "proxy": "", "insecure_ssl": False})
        return {"chosen": "manual", "ready": True, "results": []}
    result = await diagnose()
    apply(result)
    return result


# ─── کمک‌کنندهٔ ساخت Bot با همان مسیر شبکهٔ انتخاب‌شده ───

def bot_session():
    """ساخت `AiohttpSession` با پروکسی/SSL همان مسیری که تست شد."""
    from aiogram.client.session.aiohttp import AiohttpSession

    kwargs: dict[str, Any] = {}
    if _CHOSEN.get("proxy"):
        kwargs["proxy"] = _CHOSEN["proxy"]
    if _CHOSEN.get("insecure_ssl"):
        kwargs["connector"] = _insecure_connector()
    return AiohttpSession(**kwargs)


def _insecure_connector():
    import aiohttp
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return aiohttp.TCPConnector(ssl=ctx)


def make_bot(token: str, **kwargs):
    """ساخت `Bot` با تنظیمات شبکهٔ درست (پروکسی/SSL)."""
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    kwargs.setdefault("default", DefaultBotProperties(parse_mode="HTML"))
    session = bot_session()
    bot = Bot(token, session=session, **kwargs)
    if _CHOSEN.get("proxy"):
        log.info("🤖 ساخت Bot با پروکسی صریح %s", _CHOSEN["proxy"])
    elif _CHOSEN.get("mode"):
        log.info("🤖 ساخت Bot با مسیر شبکه: %s", _CHOSEN["mode"])
    return bot

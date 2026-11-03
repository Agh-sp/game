"""اتصال به سرور به شکل فایربیس — Realtime Database (REST) + همگام‌سازی.

- اگر FIREBASE_DB_URL در .env تنظیم شده باشد، اتصال REAL به Firebase RTDB برقرار می‌شود
  (نوشتن/خواندن/پوش کردن با REST + heartbeat + صف همگام‌سازی).
- اگر تنظیم نشده باشد، بازی در «حالت محلی» با همان API ادامه می‌دهد
  (اسنپ‌شات JSON روی دیسک + همه امکانات بازی سالم می‌ماند).
- وضعیت اتصال (🟢 متصل / 🔴 قطع / 🟡 محلی) همه‌جا قابل نمایش است.
"""
import asyncio
import json
import logging
import time
from pathlib import Path

log = logging.getLogger("firebase")

try:
    import aiohttp
except ImportError:  # pragma: no cover
    aiohttp = None

from core.config import BASE_DIR
from core.db import db
from core.utils import iso, jdumps

# ─── پیکربندی ───
FIREBASE_DB_URL = ""   # از .env خوانده می‌شود (زیر تنظیم می‌شود)
FIREBASE_AUTH = ""

try:  # خواندن مستقیم از .env (مستقل از ترتیب import)
    _env = BASE_DIR / ".env"
    if _env.exists():
        for _line in _env.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _k, _v = _k.strip(), _v.strip()
                if _k == "FIREBASE_DB_URL":
                    FIREBASE_DB_URL = _v.rstrip("/")
                elif _k == "FIREBASE_AUTH":
                    FIREBASE_AUTH = _v
except Exception:
    pass

LOCAL_SNAPSHOT = BASE_DIR / "fb_local.json"

# جدول‌هایی که اسنپ‌شات کاملشان به سرور_mirror می‌شود
SNAPSHOT_TABLES = ["users", "countries", "states", "settings", "straits",
                   "treaties", "seasons", "wars", "negotiations", "direct_trades"]


class FirebaseSync:
    """لایه همگام‌سازی فایربیس‌مانند: صف نوشتن، heartbeat، اسنپ‌شات، وضعیت."""

    def __init__(self):
        self.mode = "local" if not FIREBASE_DB_URL else "remote"  # remote|local
        self.connected = False
        self.latency_ms = 0
        self.last_error = ""
        self.last_sync = ""
        self._session = None
        self._local: dict = {}
        self._started = False

    # ─── API فایربیس‌مانند ───

    def _url(self, path: str) -> str:
        url = f"{FIREBASE_DB_URL}/{path.lstrip('/')}.json"
        if FIREBASE_AUTH:
            url += f"?auth={FIREBASE_AUTH}"
        return url

    async def _request(self, method: str, path: str, payload=None):
        if self.mode == "local":
            return None
        if aiohttp is None:
            raise RuntimeError("aiohttp در دسترس نیست")
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        t0 = time.monotonic()
        try:
            async with self._session.request(method, self._url(path), json=payload) as resp:
                self.latency_ms = int((time.monotonic() - t0) * 1000)
                if resp.status >= 400:
                    self.last_error = f"HTTP {resp.status}"
                    self.connected = False
                    return None
                self.connected = True
                self.last_error = ""
                if method == "GET":
                    return await resp.json(content_type=None)
                return True
        except Exception as e:
            self.connected = False
            self.last_error = str(e)[:120]
            return None

    async def get(self, path: str, default=None):
        """خواندن مسیر (مثل ref(path).get())."""
        if self.mode == "local":
            node = self._local
            for part in path.strip("/").split("/"):
                if not part:
                    continue
                node = node.get(part) if isinstance(node, dict) else None
                if node is None:
                    return default
            return node
        return await self._request("GET", path) or default

    async def set(self, path: str, value) -> bool:
        """نوشتن کامل مسیر (مثل ref(path).set())."""
        if self.mode == "local":
            self._local_set(path, value)
            self._flush_local()
            return True
        return await self._request("PUT", path, _plain(value)) is not None

    async def update(self, path: str, values: dict) -> bool:
        """به‌روزرسانی چند کلید (مثل ref(path).update())."""
        if self.mode == "local":
            for k, v in values.items():
                self._local_set(f"{path}/{k}", v)
            self._flush_local()
            return True
        return await self._request("PATCH", path, _plain(values)) is not None

    async def push(self, path: str, value) -> bool:
        """افزودن به لیست (مثل ref(path).push())."""
        key = iso().replace("-", "").replace(":", "").replace(" ", "_")
        return await self.set(f"{path}/{key}", value)

    async def delete(self, path: str) -> bool:
        if self.mode == "local":
            parts = path.strip("/").split("/")
            node = self._local
            for part in parts[:-1]:
                if not isinstance(node, dict):
                    return True
                node = node.get(part)
            if isinstance(node, dict):
                node.pop(parts[-1], None)
            self._flush_local()
            return True
        return await self._request("DELETE", path) is not None

    # ─── ذخیره محلی (fallback) ───

    def _local_set(self, path: str, value):
        parts = [p for p in path.strip("/").split("/") if p]
        node = self._local
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def _flush_local(self):
        try:
            LOCAL_SNAPSHOT.write_text(jdumps(self._local), encoding="utf-8")
        except Exception:
            pass

    def _load_local(self):
        try:
            if LOCAL_SNAPSHOT.exists():
                self._local = json.loads(LOCAL_SNAPSHOT.read_text(encoding="utf-8"))
        except Exception:
            self._local = {}

    # ─── چرخه حیات ───

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._load_local()
        if self.mode == "remote":
            ok = await self.set("status", {"state": "online", "started_at": iso()})
            if ok:
                log.info("🔥 فایربیس متصل شد: %s", FIREBASE_DB_URL)
            else:
                log.warning("🔥 اتصال فایربیس برقرار نشد — در پس‌زمینه تلاش مجدد می‌شود")
        else:
            log.info("🔥 فایربیس تنظیم نشده — حالت محلی (پشتیبان JSON)")

    async def stop(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def test(self) -> bool:
        """تست اتصال (دکمه تست پنل ادمین)."""
        return await self.set("status/last_ping", iso())

    # ─── صف همگام‌سازی ───

    async def mirror(self, path: str, value, op: str = "set") -> None:
        """صف کردن نوشتن مسیر روی سرور (fire-and-forget)."""
        if self.mode == "local":
            await self.set(path, value)
            return
        try:
            await db.execute(
                "INSERT INTO fb_queue(path, payload, op) VALUES(?,?,?)",
                (path, jdumps(_plain(value)), op))
        except Exception:
            pass

    async def flush_queue(self, limit: int = 40) -> int:
        """اعمال صف روی سرور — تعداد ردیف‌های موفق را برمی‌گرداند."""
        if self.mode == "local":
            return 0
        rows = await db.fetchall(
            "SELECT * FROM fb_queue ORDER BY id LIMIT ?", (limit,))
        done = 0
        for r in rows:
            try:
                value = json.loads(r["payload"])
            except Exception:
                value = r["payload"]
            ok = await self.set(r["path"], value)
            if ok:
                await db.execute("DELETE FROM fb_queue WHERE id=?", (r["id"],))
                done += 1
            else:
                break  # سرور در دسترس نیست — بعداً دوباره
        if done:
            self.last_sync = iso()
        return done

    async def heartbeat(self) -> None:
        """نبض سرور — هر دقیقه صدا زده می‌شود."""
        await self.set("status", {
            "state": "online" if (self.mode == "local" or self.connected) else "reconnecting",
            "updated_at": iso(),
            "latency_ms": self.latency_ms,
            "mode": self.mode,
        })
        if self.mode == "local":
            self.connected = True

    async def push_snapshot(self) -> int:
        """اسنپ‌شات کامل جداول مهم روی سرور."""
        sent = 0
        for table in SNAPSHOT_TABLES:
            try:
                rows = await db.fetchall(f"SELECT * FROM {table} LIMIT 2000")
                data = {str(r.get("id", r.get("user_id", r.get("key", i)))): r
                        for i, r in enumerate(rows)}
                if await self.set(f"game/{table}", data):
                    sent += 1
            except Exception:
                continue
        self.last_sync = iso()
        return sent

    # ─── نمایش وضعیت ───

    def status_line(self) -> str:
        if self.mode == "local":
            return "📡 سرور: 🟡 محلی (پشتیبان JSON)"
        if self.connected:
            return f"📡 سرور: 🟢 متصل ({self.latency_ms}ms)"
        return f"📡 سرور: 🔴 قطع{(' — ' + self.last_error) if self.last_error else ''}"

    def status_dict(self) -> dict:
        return {
            "mode": "فایربیس واقعی" if self.mode == "remote" else "حالت محلی (بدون FIREBASE_DB_URL)",
            "connected": self.connected,
            "latency_ms": self.latency_ms,
            "last_error": self.last_error,
            "last_sync": self.last_sync or "—",
            "url": FIREBASE_DB_URL or "—",
        }


def _plain(value):
    """تبدیل مقدار به JSON-serializable ساده."""
    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
        return value
    return str(value)


# نمونه سراسری
fb = FirebaseSync()

"""مدیریت پروسهٔ ربات‌ها — اجرا، توقف، ری‌استارت و نگهبان خودکار (Watchdog).

معادل پایتونی همان کاری که `server.ts` با `spawn('python3', ...)` و `pkill` انجام
می‌داد. ربات‌ها در یک پروسهٔ فرزندِ **فقط ربات** (`run_bots.py`) بالا می‌آیند،
لاگ‌شان در `/tmp/bot.log` ذخیره می‌شود و اگر از کار بیفتند، نگهبان هر ۲۰ ثانیه
دوباره راه‌اندازی‌شان می‌کند (با محافظ ضدِ حلقهٔ بی‌پایان در صورت خطای مکرر).
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from core import config as cfg

log = logging.getLogger("webapp.process")

BOT_LOG_PATH = Path(os.getenv("BOT_LOG_PATH", "/tmp/bot.log"))
BOT_PID_FILE = Path(os.getenv("BOT_PID_FILE", "/tmp/wwgame_bots.pid"))
LOG_TAIL_LINES = 60
WATCHDOG_INTERVAL = 20  # ثانیه
MIN_RESTART_GAP = 25    # حداقل فاصله بین دو ری‌استارت خودکار (ضد حلقه)
MAX_CONSECUTIVE_FAILURES = 5


class BotProcessManager:
    """اجرا و پایش ربات‌ها از داخل سرور وب پایتونی."""

    def __init__(self) -> None:
        self.child: subprocess.Popen[bytes] | None = None
        self.pid: int | None = None
        self.started_at: float | None = None
        self.intentional_stop = False
        self.watchdog_enabled = True
        self.last_restart_at: float | None = None
        self.restart_count = 0
        self.consecutive_failures = 0
        self.last_exit_code: int | None = None
        self._lock = threading.RLock()
        self._watchdog: threading.Thread | None = None
        self._stop_watchdog = threading.Event()

    # ─────────────── اجرا و توقف ───────────────

    def alive(self) -> bool:
        with self._lock:
            if self.child is not None:
                code = self.child.poll()
                if code is not None:
                    self.last_exit_code = code
                return code is None
            if self.pid:
                try:
                    os.kill(self.pid, 0)
                    return True
                except OSError:
                    return False
            return False

    def _script_name(self) -> str:
        return "run_webhook.py" if cfg.WEBHOOK_MODE else "run_bots.py"

    def start(self) -> int | None:
        """اجرای پروسهٔ ربات‌ها (اگر از قبل در حال اجراست، همان PID برمی‌گردد)."""
        with self._lock:
            if self.alive():
                return self.pid
            self._cleanup_stale()
            BOT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            logf = open(BOT_LOG_PATH, "ab")  # noqa: SIM115 (تا پایان عمر پروسه باز می‌ماند)
            logf.write(f"\n===== شروع اجرای ربات‌ها {time.strftime('%Y-%m-%d %H:%M:%S')} "
                       f"({self._script_name()}) =====\n".encode())
            logf.flush()
            env = os.environ.copy()
            env.setdefault("PYTHONPATH", ".")
            env.setdefault("PYTHONUNBUFFERED", "1")
            env["PORT"] = str(cfg.WEB_PORT)
            env["AUTOSTART_BOTS"] = "0"
            try:
                child = subprocess.Popen(  # noqa: S603
                    [sys.executable, "-u", self._script_name()],
                    cwd=str(cfg.BASE_DIR),
                    env=env,
                    stdout=logf,
                    stderr=logf,
                    start_new_session=True,
                )
            except Exception as exc:  # noqa: BLE001
                log.error("اجرای ربات‌ها ناموفق بود: %s", exc)
                logf.write(f"اجرای ربات‌ها ناموفق بود: {exc}\n".encode())
                logf.close()
                return None
            self.child = child
            self.pid = child.pid
            self.started_at = time.time()
            self.intentional_stop = False
            log.info("🤖 ربات‌ها اجرا شدند — PID %s (%s)", self.pid, self._script_name())
            return self.pid

    def _cleanup_stale(self) -> None:
        """اگر پروسهٔ رباتی از اجرای قبلی (بعد از کرش سرور) مانده باشد، می‌بندیمش."""
        try:
            if not BOT_PID_FILE.exists():
                return
            old = int(BOT_PID_FILE.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            return
        if not old or old == self.pid:
            return
        try:
            os.kill(old, 0)
        except OSError:
            return
        try:
            os.kill(old, signal.SIGKILL)
            log.info("پروسهٔ ربات قدیمی (PID %s) بسته شد", old)
        except OSError:
            pass

    def stop(self, timeout: float = 8.0) -> None:
        """توقف امن پروسهٔ ربات‌ها (SIGTERM و سپس SIGKILL)."""
        with self._lock:
            self.intentional_stop = True
            child, pid = self.child, self.pid
            if child is not None and child.poll() is None:
                self._terminate(child, timeout)
            elif pid:
                self._kill_pid(pid, timeout)
            self.child = None
            self.pid = None
            self.started_at = None
            log.info("🛑 ربات‌ها متوقف شدند")

    def _terminate(self, child: subprocess.Popen[bytes], timeout: float) -> None:
        try:
            os.killpg(os.getpgid(child.pid), signal.SIGTERM)
        except Exception:
            try:
                child.terminate()
            except Exception:
                pass
        try:
            child.wait(timeout=timeout)
            self.last_exit_code = child.returncode
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(os.getpgid(child.pid), signal.SIGKILL)
        except Exception:
            try:
                child.kill()
            except Exception:
                pass

    @staticmethod
    def _kill_pid(pid: int, timeout: float) -> None:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.kill(pid, sig)
            except OSError:
                return
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    os.kill(pid, 0)
                except OSError:
                    return
                time.sleep(0.15)

    def restart(self) -> int | None:
        with self._lock:
            self.stop()
            time.sleep(0.8)
            self.restart_count += 1
            self.last_restart_at = time.time()
            return self.start()

    # ─────────────── وضعیت و لاگ ───────────────

    def status(self) -> dict[str, Any]:
        running = self.alive()
        if running and self.started_at is None:
            self.started_at = time.time()
        return {
            "isRunning": running,
            "pid": self.pid if running else None,
            "mode": "webhook" if cfg.WEBHOOK_MODE else "polling",
            "script": self._script_name(),
            "uptime": int(time.time() - self.started_at) if running and self.started_at else 0,
            "watchdog": self.watchdog_enabled and not self.intentional_stop,
            "restartCount": self.restart_count,
            "lastRestartAt": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_restart_at))
                              if self.last_restart_at else None),
            "lastExitCode": self.last_exit_code,
            "consecutiveFailures": self.consecutive_failures,
        }

    @staticmethod
    def logs(lines: int = LOG_TAIL_LINES) -> list[str]:
        try:
            if not BOT_LOG_PATH.exists():
                return ["درحال راه‌اندازی ربات‌ها..."]
            content = BOT_LOG_PATH.read_text(encoding="utf-8", errors="replace").strip()
            if not content:
                return ["درحال راه‌اندازی ربات‌ها..."]
            return content.splitlines()[-lines:]
        except Exception as exc:  # noqa: BLE001
            return [f"خطا در خواندن لاگ: {exc}"]

    # ─────────────── نگهبان خودکار ───────────────

    def start_watchdog(self) -> None:
        if self._watchdog and self._watchdog.is_alive():
            return
        self._stop_watchdog.clear()
        self._watchdog = threading.Thread(target=self._watchdog_loop, name="bot-watchdog", daemon=True)
        self._watchdog.start()
        log.info("🐕 نگهبان ربات‌ها فعال شد (بررسی هر %s ثانیه)", WATCHDOG_INTERVAL)

    def stop_watchdog(self) -> None:
        self._stop_watchdog.set()

    def _watchdog_loop(self) -> None:
        while not self._stop_watchdog.wait(WATCHDOG_INTERVAL):
            if not self.watchdog_enabled or self.intentional_stop:
                continue
            if self.alive():
                # ربات سالم است: شمارندهٔ خطاها را صفر می‌کنیم
                uptime = time.time() - (self.started_at or time.time())
                if uptime > 60:
                    self.consecutive_failures = 0
                continue
            self.consecutive_failures += 1
            if self.consecutive_failures > MAX_CONSECUTIVE_FAILURES:
                log.error("⛔ ربات‌ها %s بار پشت‌سرهم از کار افتادند — اجرای خودکار متوقف شد "
                          "(لاگ: %s)", self.consecutive_failures - 1, BOT_LOG_PATH)
                self.watchdog_enabled = False
                continue
            if self.last_restart_at and time.time() - self.last_restart_at < MIN_RESTART_GAP:
                continue
            log.warning("⚠️ پروسهٔ ربات‌ها خاموش است — راه‌اندازی مجدد خودکار "
                        "(تلاش %s از %s)...", self.consecutive_failures, MAX_CONSECUTIVE_FAILURES)
            self.restart_count += 1
            self.last_restart_at = time.time()
            self.start()

    def autostart(self) -> None:
        """شروع اولیه هنگام بالا آمدن سرور وب."""
        self.watchdog_enabled = True
        if not cfg.BOTS_AUTOSTART:
            log.info("[Bots] اجرای خودکار ربات‌ها خاموش است (AUTOSTART_BOTS=0)")
            return
        if not self.alive():
            log.info("اجرای ربات‌های تلگرام (%s)...", self._script_name())
            self.start()
        self.start_watchdog()


process_manager = BotProcessManager()

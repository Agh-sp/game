"""لایهٔ دادهٔ پنل وب — خواندن/نوشتن امن روی همان دیتابیس SQLite بازی.

توابعی که در `db_bridge.py` به‌صورت اسکریپت خط فرمان نوشته شده بودند، این‌جا به
صورت تابع پایتونی در دسترس سرور وب قرار می‌گیرند (بدون exec کردن پایتون از داخل
پایتون). ستون‌های موجود در هر جدول به‌صورت خودکار تشخیص داده می‌شوند تا نوشتن
روی دیتابیس‌های قدیمی/جدید هر دو کار کند.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import sys
from pathlib import Path as _Path

_ROOT = str(_Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import config as cfg  # noqa: E402


def db_path() -> str:
    return os.environ.get("DB_PATH") or cfg.DB_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.row_factory = sqlite3.Row
    return conn


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(r["name"]) for r in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _filter(payload: dict[str, Any], cols: set[str]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k in cols and v is not None}


# ─────────────────────────── کاربران ───────────────────────────

_USER_SELECT = """
    SELECT
        u.id,
        u.username,
        u.full_name,
        u.joined_at,
        u.royal_coins,
        u.money,
        u.country_id,
        u.country_taken_at,
        u.banned,
        c.name  AS country_name,
        c.flag  AS country_flag,
        c.iso_code AS country_iso,
        c.flag_url AS country_flag_url,
        s.satisfaction,
        s.cyber_power,
        s.currency_name,
        a.is_super AS is_super_admin,
        CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END AS is_admin,
        a.perms AS admin_perms
    FROM users u
    LEFT JOIN countries c ON u.country_id = c.id
    LEFT JOIN states s ON u.id = s.user_id
    LEFT JOIN admins a ON u.id = a.id
    ORDER BY u.joined_at DESC
"""


def list_users() -> list[dict[str, Any]]:
    conn = connect()
    try:
        users = _rows(conn.execute(_USER_SELECT))
        try:
            orphans = _rows(conn.execute(
                "SELECT a.id, a.name, a.is_super, a.perms, a.added_at FROM admins a "
                "WHERE a.id NOT IN (SELECT id FROM users)"
            ))
        except sqlite3.Error:
            orphans = []
        for oa in orphans:
            users.append({
                "id": oa["id"], "username": "", "full_name": oa.get("name") or "مدیر سیستم",
                "joined_at": oa.get("added_at"), "royal_coins": 0, "money": 0,
                "country_id": None, "country_name": "نامشخص", "country_flag": "👑",
                "country_taken_at": None, "banned": 0, "satisfaction": 100,
                "cyber_power": 10000, "currency_name": "ریال",
                "is_super_admin": oa.get("is_super"), "is_admin": 1,
                "admin_perms": oa.get("perms"),
            })
        return users
    finally:
        conn.close()


def get_user(user_id: int) -> dict[str, Any] | None:
    conn = connect()
    try:
        row = conn.execute("""
            SELECT u.*, c.name AS country_name, c.flag AS country_flag, c.population,
                   c.has_sea, c.oil_reserve, s.satisfaction, s.cyber_power,
                   s.currency_name, s.tax_rate, s.subsidy_daily,
                   a.is_super AS is_super_admin,
                   CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END AS is_admin,
                   a.perms AS admin_perms
            FROM users u
            LEFT JOIN countries c ON u.country_id = c.id
            LEFT JOIN states s ON u.id = s.user_id
            LEFT JOIN admins a ON u.id = a.id
            WHERE u.id = ?
        """, (user_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        for key, sql in (
            ("assets", "SELECT pa.*, eq.name AS equip_name, eq.emoji AS equip_emoji, "
                       "eq.attack_power, eq.defense_power FROM player_assets pa "
                       "LEFT JOIN equipment eq ON pa.item_id = eq.id WHERE pa.user_id = ?"),
            ("receipts", "SELECT * FROM receipts WHERE user_id = ? ORDER BY id DESC LIMIT 5"),
            ("tickets", "SELECT * FROM tickets WHERE user_id = ? ORDER BY id DESC LIMIT 5"),
        ):
            try:
                data[key] = _rows(conn.execute(sql, (user_id,)))
            except sqlite3.Error:
                data[key] = []
        return data
    finally:
        conn.close()


def update_user(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    conn = connect()
    try:
        cols = table_columns(conn, "users")
        data = _filter(payload, cols)
        if data:
            sets = ", ".join(f"{k} = ?" for k in data)
            conn.execute(f"UPDATE users SET {sets} WHERE id = ?", (*data.values(), user_id))
        state_cols = table_columns(conn, "states")
        state = _filter(payload, state_cols & {"satisfaction", "cyber_power", "currency_name",
                                               "tax_rate", "subsidy_daily"})
        if state:
            existing = conn.execute("SELECT user_id FROM states WHERE user_id = ?", (user_id,)).fetchone()
            if existing:
                sets = ", ".join(f"{k} = ?" for k in state)
                conn.execute(f"UPDATE states SET {sets} WHERE user_id = ?", (*state.values(), user_id))
            else:
                keys = ["user_id", *state.keys()]
                conn.execute(f"INSERT INTO states ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                             (user_id, *state.values()))
        conn.commit()
        return {"success": True, "message": f"کاربر {user_id} با موفقیت به‌روزرسانی شد"}
    finally:
        conn.close()


def add_user(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        user_id = int(payload.get("id"))
    except (TypeError, ValueError):
        return {"success": False, "error": "شناسهٔ تلگرام باید عددی باشد"}
    username = str(payload.get("username") or "").lstrip("@")
    full_name = str(payload.get("full_name") or "") or username or f"کاربر {user_id}"
    money = int(payload.get("money") or 0)
    royal_coins = int(payload.get("royal_coins") or 0)
    country_id = payload.get("country_id") or None
    banned = int(payload.get("banned") or 0)
    conn = connect()
    try:
        conn.execute("""
            INSERT INTO users (id, username, full_name, joined_at, royal_coins, money, country_id, banned)
            VALUES (?, ?, ?, datetime('now'), ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username, full_name = excluded.full_name,
                royal_coins = excluded.royal_coins, money = excluded.money,
                country_id = excluded.country_id, banned = excluded.banned
        """, (user_id, username, full_name, royal_coins, money, country_id, banned))
        conn.execute("""
            INSERT INTO states (user_id, satisfaction, cyber_power, currency_name)
            VALUES (?, 50.0, 10000, 'ریال') ON CONFLICT(user_id) DO NOTHING
        """, (user_id,))
        conn.commit()
        return {"success": True, "message": f"کاربر {full_name} با موفقیت افزوده شد", "id": user_id}
    finally:
        conn.close()


def toggle_ban(user_id: int) -> dict[str, Any]:
    conn = connect()
    try:
        row = conn.execute("SELECT banned FROM users WHERE id = ?", (user_id,)).fetchone()
        new_banned = 0 if (row and int(row["banned"] or 0) == 1) else 1
        conn.execute("UPDATE users SET banned = ? WHERE id = ?", (new_banned, user_id))
        conn.commit()
        return {"success": True, "banned": new_banned,
                "message": "کاربر مسدود شد" if new_banned else "کاربر رفع مسدودیت شد"}
    finally:
        conn.close()


def adjust_balance(user_id: int, money_delta: int, coins_delta: int) -> dict[str, Any]:
    conn = connect()
    try:
        cur = conn.execute("""
            UPDATE users SET money = MAX(0, money + ?), royal_coins = MAX(0, royal_coins + ?)
            WHERE id = ?
        """, (money_delta, coins_delta, user_id))
        conn.commit()
        if cur.rowcount == 0:
            return {"success": False, "error": "کاربر یافت نشد"}
        return {"success": True, "message": f"موجودی کاربر {user_id} به‌روزرسانی شد"}
    finally:
        conn.close()


def toggle_admin(user_id: int, name: str = "", is_super: int = 0) -> dict[str, Any]:
    conn = connect()
    try:
        row = conn.execute("SELECT id FROM admins WHERE id = ?", (user_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM admins WHERE id = ?", (user_id,))
            conn.commit()
            return {"success": True, "is_admin": 0, "message": "دسترسی ادمین حذف شد"}
        cols = table_columns(conn, "admins")
        payload = {"id": user_id, "name": name or f"ادمین {user_id}", "is_super": int(is_super)}
        if "added_at" in cols:
            payload["added_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            from core.admins import ALL_PERMS
            payload["perms"] = json.dumps(list(ALL_PERMS), ensure_ascii=False)
        except Exception:
            payload["perms"] = "[]"
        payload = _filter(payload, cols)
        keys = list(payload)
        conn.execute(f"INSERT INTO admins ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                     tuple(payload.values()))
        conn.commit()
        return {"success": True, "is_admin": 1, "message": "دسترسی ادمین داده شد"}
    finally:
        conn.close()


def delete_user(user_id: int) -> dict[str, Any]:
    conn = connect()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        for table in ("states", "player_assets", "admins"):
            try:
                conn.execute(f"DELETE FROM {table} WHERE {'user_id' if table != 'admins' else 'id'} = ?",
                             (user_id,))
            except sqlite3.Error:
                pass
        conn.commit()
        return {"success": True, "message": f"کاربر {user_id} حذف شد"}
    finally:
        conn.close()


def _initial_money() -> int:
    conn = connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key='initial_money'").fetchone()
        if row and row["value"]:
            return int(float(row["value"]))
    except (sqlite3.Error, TypeError, ValueError):
        pass
    finally:
        conn.close()
    return 200_000_000


def reset_all_players() -> dict[str, Any]:
    """🧨 ریست کامل بازی از پنل وب — همان موتور `core.fullreset`.

    پیش‌تر این تابع فقط `states` را پاک می‌کرد؛ نتیجه: ☢️ هسته‌ای، 🛢 ارتقا،
    🌐 اینترنت، 🗺 استان‌ها و 🎖 تجهیزات باقی می‌ماندند.
    """
    from core.fullreset import sync_full_reset
    conn = connect()
    try:
        stats = sync_full_reset(conn, reset_wealth=True, keep_bans=True,
                                initial_money=_initial_money(), log_errors=True)
        return {
            "success": True,
            "message": (f"{stats['users']} بازیکن به‌طور کامل ریست شدند، "
                        f"{stats['countries']} کشور آزاد شد و "
                        f"{stats['cleared']} جدول پاک‌سازی شد"),
            "count": stats["users"],
            "tables": stats["cleared"],
            "countries": stats["countries"],
        }
    finally:
        conn.close()


def reset_all_wealth(mode: str = "both_default") -> dict[str, Any]:
    initial = _initial_money()
    conn = connect()
    try:
        total = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        if mode == "both_default":
            conn.execute("UPDATE users SET royal_coins = 0, money = ?", (initial,))
            msg = f"سکه شاهی (۰) و بودجه پایه ({initial:,}) برای تمام {total} کاربر ریست شد"
        elif mode == "coins_zero":
            conn.execute("UPDATE users SET royal_coins = 0")
            msg = f"سکه شاهی تمام {total} کاربر صفر شد"
        elif mode == "money_default":
            conn.execute("UPDATE users SET money = ?", (initial,))
            msg = f"بودجه پایه تمام {total} کاربر روی {initial:,} تنظیم شد"
        elif mode == "money_zero":
            conn.execute("UPDATE users SET money = 0")
            msg = f"موجودی پول تمام {total} کاربر صفر شد"
        else:
            return {"success": False, "error": f"حالت نامعتبر: {mode}"}
        conn.commit()
        return {"success": True, "message": msg, "count": total}
    finally:
        conn.close()


# ─────────────────────────── کشورها و آمار بازی ───────────────────────────

def list_countries() -> list[dict[str, Any]]:
    conn = connect()
    try:
        return _rows(conn.execute(
            "SELECT id, name, flag, iso_code, flag_url, is_special, coin_price, toman_price, "
            "population, has_sea, region, currency, oil_reserve, oil_richness, owner_id "
            "FROM countries ORDER BY id ASC"))
    except sqlite3.Error:
        return []


def sync_firebase() -> dict[str, Any]:
    """همگام‌سازی دوطرفه با فایربیس (همان منطق db_bridge.py، این‌جا بدون exec)."""
    import sys

    bridge_path = str(Path(cfg.BASE_DIR))
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)
    try:
        import db_bridge
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"ماژول پل دیتابیس بارگذاری نشد: {exc}"}
    if not (os.getenv("FIREBASE_DB_URL") or getattr(db_bridge, "FIREBASE_DB_URL", "")):
        return {"success": False,
                "message": "FIREBASE_DB_URL تنظیم نشده است — بازی در حالت محلی کار می‌کند",
                "mode": "local"}
    try:
        result = db_bridge.sync_from_firebase() or {}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
    return {"success": not result.get("error"), "message": result.get("message", "همگام‌سازی انجام شد"),
            "result": result}


def database_stats() -> dict[str, Any]:
    """فهرست جدول‌ها با تعداد سطر — برای صفحهٔ دیتابیس پنل."""
    conn = connect()
    try:
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        out = []
        for t in tables:
            try:
                count = int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
            except sqlite3.Error:
                count = 0
            out.append({"name": t, "rows": count})
        path = Path(db_path())
        return {"path": str(path), "size": path.stat().st_size if path.exists() else 0,
                "tableCount": len(out), "tables": out}
    finally:
        conn.close()


def read_table(name: str, limit: int = 100) -> dict[str, Any]:
    if not name.replace("_", "").isalnum():
        return {"error": "نام جدول نامعتبر است"}
    conn = connect()
    try:
        rows = _rows(conn.execute(f"SELECT * FROM {name} LIMIT ?", (limit,)))
        return {"table": name, "rows": rows, "columns": list(rows[0].keys()) if rows else []}
    except sqlite3.Error as exc:
        return {"error": str(exc)}
    finally:
        conn.close()


# ─────────────────────────── فایل‌های سورس (تب دیتابیس و کد) ───────────────────────────

TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".json", ".md", ".txt", ".css", ".html", ".env", ".example"}


def read_source_file(rel_path: str) -> dict[str, Any]:
    base = Path(cfg.BASE_DIR).resolve()
    safe = (base / rel_path).resolve()
    if base not in safe.parents and safe != base:
        return {"error": "دسترسی خارج از پوشهٔ پروژه مجاز نیست"}
    if not safe.exists():
        return {"error": "فایل یافت نشد"}
    if safe.is_dir():
        files = []
        for f in sorted(safe.iterdir()):
            try:
                files.append({"name": f.name, "isDir": f.is_dir(),
                              "size": f.stat().st_size if f.is_file() else 0})
            except OSError:
                continue
        return {"type": "directory", "files": files}
    if safe.suffix.lower() not in TEXT_EXTENSIONS and safe.name not in (".env.example",):
        return {"type": "file", "content": "", "size": safe.stat().st_size,
                "error": "فایل متنی نیست و نمایش داده نمی‌شود"}
    return {"type": "file", "content": safe.read_text(encoding="utf-8", errors="replace"),
            "size": safe.stat().st_size}


def backup_database() -> dict[str, Any]:
    src = Path(db_path())
    if not src.exists():
        return {"success": False, "error": "دیتابیس یافت نشد"}
    dest_dir = Path(cfg.BASE_DIR) / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"wwgame_{time.strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(src, dest)
    return {"success": True, "path": str(dest), "size": dest.stat().st_size}

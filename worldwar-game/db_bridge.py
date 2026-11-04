#!/usr/bin/env python3
"""
World War Game Database Bridge
Provides JSON-based SQLite queries and Firebase Realtime Database bi-directional sync
"""

import sys
import os
import json
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime

DB_PATH = os.path.abspath(os.environ.get('DB_PATH') or os.path.join(os.path.dirname(__file__), 'wwgame.db'))
ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')

def load_env():
    env_vars = {}
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env_vars[k.strip()] = v.strip()
        except Exception:
            pass
    return env_vars

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.row_factory = sqlite3.Row
    return conn

def get_setting_value(key, default=None):
    """خواندن یک تنظیم از جدول settings (بدون نیاز به import بخش بازی)."""
    try:
        conn = get_conn()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        finally:
            conn.close()
        if row and row[0] not in (None, ""):
            return row[0]
    except Exception:
        pass
    return default


def get_initial_money():
    """بودجه اولیهٔ بازیکن تازه‌وارد (تنظیم initial_money — پیش‌فرض ۲۰۰)."""
    try:
        return int(float(get_setting_value("initial_money", 200)))
    except (TypeError, ValueError):
        return 200


def firebase_request(method, path, data=None):
    env_vars = load_env()
    base_url = env_vars.get('FIREBASE_DB_URL') or os.environ.get('FIREBASE_DB_URL', '')
    auth = env_vars.get('FIREBASE_AUTH') or os.environ.get('FIREBASE_AUTH', '')
    
    if not base_url:
        return None
        
    clean_url = base_url.rstrip('/')
    url = f"{clean_url}/{path.lstrip('/')}.json"
    if auth:
        url += f"?auth={auth}"
        
    try:
        req_data = None
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if data is not None:
            req_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
            
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8')
            return json.loads(content) if content else None
    except Exception as e:
        sys.stderr.write(f"Firebase error: {str(e)}\n")
        return None

def sync_from_firebase():
    initial_money = get_initial_money()
    """Import users and states from Firebase Realtime Database into SQLite with full field protection"""
    fb_users = firebase_request('GET', 'game/users')
    fb_states = firebase_request('GET', 'game/states')
    
    conn = get_conn()
    cur = conn.cursor()
    synced_users = 0
    synced_states = 0
    
    if fb_users and isinstance(fb_users, dict):
        for uid_str, u in fb_users.items():
            if not u or not isinstance(u, dict):
                continue
            uid = int(u.get('id') or uid_str)
            cur.execute("""
                INSERT INTO users (id, username, full_name, joined_at, royal_coins, money, country_id, country_taken_at, banned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    royal_coins = excluded.royal_coins,
                    money = excluded.money,
                    country_id = excluded.country_id,
                    country_taken_at = excluded.country_taken_at,
                    banned = excluded.banned
            """, (
                uid,
                u.get('username', ''),
                u.get('full_name', ''),
                u.get('joined_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                int(u.get('royal_coins', 0)),
                int(u.get('money', initial_money)),
                u.get('country_id'),
                u.get('country_taken_at'),
                int(u.get('banned', 0))
            ))
            # Sync country owner
            cid = u.get('country_id')
            if cid:
                cur.execute("UPDATE countries SET owner_id = ? WHERE id = ?", (uid, cid))
            synced_users += 1

    if fb_states and isinstance(fb_states, dict):
        for uid_str, s in fb_states.items():
            if not s or not isinstance(s, dict):
                continue
            uid = int(s.get('user_id') or uid_str)
            cur.execute("SELECT user_id FROM states WHERE user_id = ?", (uid,))
            existing = cur.fetchone()
            if existing:
                cur.execute("""
                    UPDATE states SET
                        satisfaction = COALESCE(?, satisfaction),
                        currency_name = COALESCE(?, currency_name),
                        cyber_power = COALESCE(?, cyber_power),
                        materials = COALESCE(?, materials),
                        energy = COALESCE(?, energy),
                        water = COALESCE(?, water),
                        gas = COALESCE(?, gas),
                        oil_stock = COALESCE(?, oil_stock),
                        diplomacy = COALESCE(?, diplomacy),
                        tax_rate = COALESCE(?, tax_rate),
                        subsidy_daily = COALESCE(?, subsidy_daily)
                    WHERE user_id = ?
                """, (
                    s.get('satisfaction'),
                    s.get('currency_name'),
                    s.get('cyber_power'),
                    s.get('materials'),
                    s.get('energy'),
                    s.get('water'),
                    s.get('gas'),
                    s.get('oil_stock'),
                    s.get('diplomacy'),
                    s.get('tax_rate'),
                    s.get('subsidy_daily'),
                    uid
                ))
            else:
                cur.execute("""
                    INSERT INTO states (
                        user_id, satisfaction, currency_name, cyber_power,
                        materials, energy, water, gas, oil_stock, diplomacy, tax_rate, subsidy_daily
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uid,
                    float(s.get('satisfaction', 50.0)),
                    s.get('currency_name', 'ریال'),
                    int(s.get('cyber_power', 10000)),
                    int(s.get('materials', 1000)),
                    int(s.get('energy', 5000)),
                    int(s.get('water', 5000)),
                    int(s.get('gas', 5000)),
                    int(s.get('oil_stock', 0)),
                    float(s.get('diplomacy', 50.0)),
                    float(s.get('tax_rate', 0.0)),
                    int(s.get('subsidy_daily', 0))
                ))
            synced_states += 1

    conn.commit()
    conn.close()
    return {"synced_users": synced_users, "synced_states": synced_states}

def push_user_to_firebase(user_id):
    """Push single user and state to Firebase game/users and game/states"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        return
        
    user_dict = dict(u)
    firebase_request('PUT', f'game/users/{user_id}', user_dict)
    
    cur.execute("SELECT * FROM states WHERE user_id = ?", (user_id,))
    s = cur.fetchone()
    if s:
        state_dict = dict(s)
        firebase_request('PUT', f'game/states/{user_id}', state_dict)
        
    conn.close()

def get_countries():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, flag, iso_code, flag_url, is_special, coin_price, toman_price, population, has_sea, region, currency, oil_reserve, oil_richness, owner_id FROM countries ORDER BY id ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_users():
    # If users table is empty, auto-sync from Firebase first
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    
    if count == 0:
        try:
            sync_from_firebase()
        except Exception:
            pass
            
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
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
            c.name as country_name,
            c.flag as country_flag,
            c.iso_code as country_iso,
            c.flag_url as country_flag_url,
            s.satisfaction,
            s.cyber_power,
            s.currency_name,
            a.is_super as is_super_admin,
            CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as is_admin,
            a.perms as admin_perms
        FROM users u
        LEFT JOIN countries c ON u.country_id = c.id
        LEFT JOIN states s ON u.id = s.user_id
        LEFT JOIN admins a ON u.id = a.id
        ORDER BY u.joined_at DESC
    """)
    users = [dict(r) for r in cur.fetchall()]
    
    # Also find admins who might not be in users table yet
    cur.execute("""
        SELECT a.id, a.name, a.is_super, a.perms, a.added_at
        FROM admins a
        WHERE a.id NOT IN (SELECT id FROM users)
    """)
    orphan_admins = cur.fetchall()
    for oa in orphan_admins:
        users.append({
            "id": oa['id'],
            "username": "",
            "full_name": oa['name'] or 'مدیر سیستم',
            "joined_at": oa['added_at'],
            "royal_coins": 0,
            "money": 0,
            "country_id": None,
            "country_name": "نامشخص",
            "country_flag": "👑",
            "country_taken_at": None,
            "banned": 0,
            "satisfaction": 100,
            "cyber_power": 10000,
            "currency_name": "ریال",
            "is_super_admin": oa['is_super'],
            "is_admin": 1,
            "admin_perms": oa['perms']
        })
        
    conn.close()
    return users

def get_user_detail(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            u.*,
            c.name as country_name,
            c.flag as country_flag,
            c.population,
            c.has_sea,
            c.oil_reserve,
            s.satisfaction,
            s.cyber_power,
            s.currency_name,
            s.tax_rate,
            s.subsidy_daily,
            a.is_super as is_super_admin,
            CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as is_admin,
            a.perms as admin_perms
        FROM users u
        LEFT JOIN countries c ON u.country_id = c.id
        LEFT JOIN states s ON u.id = s.user_id
        LEFT JOIN admins a ON u.id = a.id
        WHERE u.id = ?
    """, (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    user_data = dict(row)
    
    # Get user assets
    cur.execute("""
        SELECT pa.*, eq.name as equip_name, eq.emoji as equip_emoji, eq.attack_power, eq.defense_power
        FROM player_assets pa
        LEFT JOIN equipment eq ON pa.item_id = eq.id
        WHERE pa.user_id = ?
    """, (user_id,))
    user_data['assets'] = [dict(r) for r in cur.fetchall()]
    
    # Get user receipts
    cur.execute("SELECT * FROM receipts WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
    user_data['receipts'] = [dict(r) for r in cur.fetchall()]
    
    # Get user tickets
    cur.execute("SELECT * FROM tickets WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
    user_data['tickets'] = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return user_data

def update_user(user_id, data):
    conn = get_conn()
    cur = conn.cursor()
    
    # Update users table
    cur.execute("""
        UPDATE users
        SET 
            username = COALESCE(?, username),
            full_name = COALESCE(?, full_name),
            royal_coins = COALESCE(?, royal_coins),
            money = COALESCE(?, money),
            country_id = COALESCE(?, country_id),
            banned = COALESCE(?, banned)
        WHERE id = ?
    """, (
        data.get('username'),
        data.get('full_name'),
        data.get('royal_coins'),
        data.get('money'),
        data.get('country_id'),
        data.get('banned'),
        user_id
    ))
    
    # If state fields present, update states table
    if 'satisfaction' in data or 'cyber_power' in data:
        cur.execute("""
            INSERT INTO states (user_id, satisfaction, cyber_power)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                satisfaction = COALESCE(?, satisfaction),
                cyber_power = COALESCE(?, cyber_power)
        """, (
            user_id,
            data.get('satisfaction', 50.0),
            data.get('cyber_power', 10000),
            data.get('satisfaction'),
            data.get('cyber_power')
        ))
        
    conn.commit()
    conn.close()
    
    # Push update to Firebase in background
    try:
        push_user_to_firebase(user_id)
    except Exception:
        pass
        
    return {"success": True, "message": f"کاربر {user_id} با موفقیت به‌روزرسانی شد"}

def add_user(data):
    user_id = int(data.get('id'))
    username = data.get('username', '').lstrip('@')
    full_name = data.get('full_name', '') or username or f'کاربر {user_id}'
    money = int(data.get('money', get_initial_money()))
    royal_coins = int(data.get('royal_coins', 0))
    country_id = data.get('country_id')
    banned = int(data.get('banned', 0))
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (id, username, full_name, joined_at, royal_coins, money, country_id, banned)
        VALUES (?, ?, ?, datetime('now'), ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            royal_coins = excluded.royal_coins,
            money = excluded.money,
            country_id = excluded.country_id,
            banned = excluded.banned
    """, (user_id, username, full_name, royal_coins, money, country_id, banned))
    
    # Initialize state
    cur.execute("""
        INSERT INTO states (user_id, satisfaction, cyber_power, currency_name)
        VALUES (?, 50.0, 10000, 'ریال')
        ON CONFLICT(user_id) DO NOTHING
    """, (user_id,))
    
    conn.commit()
    conn.close()
    
    try:
        push_user_to_firebase(user_id)
    except Exception:
        pass
        
    return {"success": True, "message": f"کاربر {full_name} با موفقیت افزوده شد", "id": user_id}

def toggle_ban(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT banned FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    new_banned = 1
    if row and row['banned'] == 1:
        new_banned = 0
    cur.execute("UPDATE users SET banned = ? WHERE id = ?", (new_banned, user_id))
    conn.commit()
    conn.close()
    
    try:
        push_user_to_firebase(user_id)
    except Exception:
        pass
        
    return {"success": True, "banned": new_banned, "message": "کاربر مسدود شد" if new_banned == 1 else "کاربر رفع مسدودیت شد"}

def adjust_balance(user_id, money_delta, coins_delta):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET 
            money = MAX(0, money + ?),
            royal_coins = MAX(0, royal_coins + ?)
        WHERE id = ?
    """, (money_delta, coins_delta, user_id))
    conn.commit()
    conn.close()
    
    try:
        push_user_to_firebase(user_id)
    except Exception:
        pass
        
    return {"success": True, "message": "موجودی با موفقیت تغییر یافت"}

def toggle_admin(user_id, name, is_super):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM admins WHERE id = ?", (user_id,))
    row = cur.fetchone()
    
    if row:
        cur.execute("DELETE FROM admins WHERE id = ?", (user_id,))
        msg = "دسترسی مدیریت از این کاربر سلب شد"
        is_admin = False
    else:
        cur.execute("""
            INSERT INTO admins (id, name, is_super, perms, added_at)
            VALUES (?, ?, ?, '[]', datetime('now'))
        """, (user_id, name or f'مدیر {user_id}', 1 if is_super else 0))
        msg = "کاربر با موفقیت به عنوان مدیر ثبت شد"
        is_admin = True
        
    conn.commit()
    conn.close()
    return {"success": True, "is_admin": is_admin, "message": msg}

def delete_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    cur.execute("DELETE FROM states WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM player_assets WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    try:
        firebase_request('DELETE', f'game/users/{user_id}')
        firebase_request('DELETE', f'game/states/{user_id}')
    except Exception:
        pass
        
    return {"success": True, "message": f"کاربر {user_id} حذف شد"}

def reset_all_players():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    
    # 1. Free all countries
    cur.execute("UPDATE countries SET owner_id = NULL")
    
    # 2. Reset users table (بودجه اولیه از تنظیمات بازی خوانده می‌شود)
    cur.execute("UPDATE users SET country_id = NULL, country_taken_at = NULL, royal_coins = 0, money = ?, banned = 0",
                (get_initial_money(),))
    
    # 3. Clean gameplay tables
    tables = [
        "player_assets", "player_projects", "soldier_trainings", "companies",
        "bases", "states", "treaties", "strait_blockades", "wars",
        "war_alliances", "market_orders", "currency_requests"
    ]
    for tbl in tables:
        try:
            cur.execute(f"DELETE FROM {tbl}")
        except Exception:
            pass
            
    conn.commit()
    conn.close()
    
    try:
        firebase_request('DELETE', 'game/states')
    except Exception:
        pass
        
    return {"success": True, "message": f"تمام بازیکنان ({total_users} نفر) ریست شدند و تمام کشورها آزاد گردیدند", "count": total_users}

def reset_all_wealth(mode='both_default'):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    
    initial = get_initial_money()
    if mode == 'both_default':
        cur.execute("UPDATE users SET royal_coins = 0, money = ?", (initial,))
        msg = f"سکه شاهی (۰) و بودجه پایه ({initial:,}) برای تمام {total_users} کاربر ریست شد"
    elif mode == 'coins_zero':
        cur.execute("UPDATE users SET royal_coins = 0")
        msg = f"سکه شاهی تمام {total_users} کاربر صفر شد"
    elif mode == 'money_default':
        cur.execute("UPDATE users SET money = ?", (initial,))
        msg = f"بودجه پایه تمام {total_users} کاربر روی {initial:,} تنظیم شد"
    elif mode == 'money_zero':
        cur.execute("UPDATE users SET money = 0")
        msg = f"موجودی پول تمام {total_users} کاربر صفر شد"
    else:
        conn.close()
        return {"success": False, "error": f"Invalid mode: {mode}"}
        
    conn.commit()
    conn.close()
    return {"success": True, "message": msg, "count": total_users}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command provided"}))
        return
        
    cmd = sys.argv[1]
    
    try:
        if cmd == 'get_users':
            res = get_users()
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'get_countries':
            res = get_countries()
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'get_user':
            user_id = int(sys.argv[2])
            res = get_user_detail(user_id)
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'update_user':
            user_id = int(sys.argv[2])
            data = json.loads(sys.argv[3])
            res = update_user(user_id, data)
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'add_user':
            data = json.loads(sys.argv[2])
            res = add_user(data)
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'toggle_ban':
            user_id = int(sys.argv[2])
            res = toggle_ban(user_id)
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'adjust_balance':
            user_id = int(sys.argv[2])
            money_delta = int(sys.argv[3])
            coins_delta = int(sys.argv[4])
            res = adjust_balance(user_id, money_delta, coins_delta)
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'toggle_admin':
            user_id = int(sys.argv[2])
            name = sys.argv[3] if len(sys.argv) > 3 else ""
            is_super = int(sys.argv[4]) if len(sys.argv) > 4 else 0
            res = toggle_admin(user_id, name, is_super)
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'delete_user':
            user_id = int(sys.argv[2])
            res = delete_user(user_id)
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'sync_firebase':
            res = sync_from_firebase()
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'reset_all_players':
            res = reset_all_players()
            print(json.dumps(res, ensure_ascii=False))
        elif cmd == 'reset_all_wealth':
            mode = sys.argv[2] if len(sys.argv) > 2 else 'both_default'
            res = reset_all_wealth(mode)
            print(json.dumps(res, ensure_ascii=False))
        else:
            print(json.dumps({"error": f"Unknown command: {cmd}"}))
    except Exception as e:
        print(json.dumps({"error": str(e), "success": False}))

if __name__ == '__main__':
    main()

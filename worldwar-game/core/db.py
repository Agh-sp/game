"""لایه دیتابیس: اتصال aiosqlite + اسکیمای کامل بازی «جنگ جهانی ۳»."""
import aiosqlite

from core import seed
from core.config import DB_PATH, SUPER_ADMIN_ID
from core.utils import iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS admins (
  id INTEGER PRIMARY KEY,
  name TEXT DEFAULT '',
  is_super INTEGER DEFAULT 0,
  perms TEXT DEFAULT '[]',
  added_by INTEGER,
  added_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT DEFAULT '',
  full_name TEXT DEFAULT '',
  joined_at TEXT DEFAULT (datetime('now')),
  royal_coins INTEGER DEFAULT 0,
  money INTEGER DEFAULT 200,
  country_id INTEGER,
  country_taken_at TEXT,
  banned INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS countries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  flag TEXT DEFAULT '🏳',
  iso_code TEXT DEFAULT '',
  flag_url TEXT DEFAULT '',
  is_special INTEGER DEFAULT 0,
  coin_price INTEGER DEFAULT 0,
  toman_price INTEGER DEFAULT 0,
  population INTEGER DEFAULT 1000000,
  has_sea INTEGER DEFAULT 1,
  region TEXT DEFAULT 'آسیا',
  is_active INTEGER DEFAULT 1,
  owner_id INTEGER,
  gdp_factor REAL DEFAULT 1,
  oil_income_base INTEGER DEFAULT 2,
  leader_name TEXT DEFAULT '',
  leader_title TEXT DEFAULT 'رئیس‌جمهور',
  leader_since TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS states (
  user_id INTEGER PRIMARY KEY,
  satisfaction REAL DEFAULT 50,
  currency_name TEXT DEFAULT 'دینار',
  religion_id INTEGER,
  government_id INTEGER,
  chosen_laws TEXT DEFAULT '{}',
  subsidy_daily INTEGER DEFAULT 0,
  tax_rate REAL DEFAULT 0,
  blackout_power INTEGER DEFAULT 0,
  blackout_water INTEGER DEFAULT 0,
  blackout_gas INTEGER DEFAULT 0,
  leader_block_until TEXT,
  server_jam_until TEXT,
  disarmed_until TEXT,
  trade_banned TEXT DEFAULT '[]',
  last_income TEXT,
  cyber_power INTEGER DEFAULT 10000,
  materials INTEGER DEFAULT 1000
);

CREATE TABLE IF NOT EXISTS equipment_categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT UNIQUE,
  title TEXT,
  emoji TEXT DEFAULT '🪖',
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS equipment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER,
  name TEXT,
  emoji TEXT DEFAULT '⚔️',
  attack_power INTEGER DEFAULT 0,
  defense_power INTEGER DEFAULT 0,
  cyber_power INTEGER DEFAULT 0,
  speed INTEGER DEFAULT 3,
  price_money INTEGER DEFAULT 0,
  price_coins INTEGER DEFAULT 0,
  requires_project_id INTEGER,
  requires_text TEXT DEFAULT '',
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS soldier_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  emoji TEXT DEFAULT '🪖',
  power INTEGER DEFAULT 10,
  cyber_power INTEGER DEFAULT 0,
  cost_per_unit INTEGER DEFAULT 50000,
  train_hours INTEGER DEFAULT 24,
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS soldier_trainings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  type_id INTEGER,
  count INTEGER,
  started_at TEXT DEFAULT (datetime('now')),
  completes_at TEXT
);

CREATE TABLE IF NOT EXISTS buildings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sector TEXT,
  name TEXT,
  emoji TEXT DEFAULT '🏗',
  description TEXT DEFAULT '',
  cost_money INTEGER DEFAULT 0,
  cost_coins INTEGER DEFAULT 0,
  satisfaction REAL DEFAULT 0,
  capacity INTEGER DEFAULT 0,
  duration_hours REAL DEFAULT 0,
  requires_building_id INTEGER,
  requires_ratio INTEGER,
  requires_project_id INTEGER,
  requires_text TEXT DEFAULT '',
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS player_assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  item_type TEXT,
  item_id INTEGER,
  quantity INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(user_id, item_type, item_id)
);

CREATE TABLE IF NOT EXISTS player_projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  building_id INTEGER,
  name TEXT DEFAULT '',
  status TEXT DEFAULT 'in_progress',
  started_at TEXT DEFAULT (datetime('now')),
  completes_at TEXT,
  cost_money INTEGER DEFAULT 0,
  cost_coins INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS company_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT UNIQUE,
  title TEXT,
  emoji TEXT DEFAULT '🏢',
  base_income INTEGER DEFAULT 100000,
  satisfaction REAL DEFAULT 0,
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER,
  type_id INTEGER,
  name TEXT,
  income_daily INTEGER DEFAULT 100000,
  founded_at TEXT DEFAULT (datetime('now')),
  announced INTEGER DEFAULT 0,
  last_withdraw TEXT
);

CREATE TABLE IF NOT EXISTS laws (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT,
  options TEXT DEFAULT '[]',
  religion_effects TEXT DEFAULT '{}',
  government_effects TEXT DEFAULT '{}',
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS religions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  emoji TEXT DEFAULT '🕊',
  description TEXT DEFAULT '',
  effects TEXT DEFAULT '{}',
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS governments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  emoji TEXT DEFAULT '🏛',
  flag TEXT DEFAULT '🏳',
  description TEXT DEFAULT '',
  effects TEXT DEFAULT '{}',
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS missions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT,
  description TEXT DEFAULT '',
  target_type TEXT DEFAULT 'login',
  target_value INTEGER DEFAULT 1,
  reward_money INTEGER DEFAULT 0,
  reward_coins INTEGER DEFAULT 0,
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS mission_claims (
  user_id INTEGER,
  mission_id INTEGER,
  day TEXT,
  claimed_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, mission_id, day)
);

CREATE TABLE IF NOT EXISTS daily_progress (
  user_id INTEGER,
  day TEXT,
  login INTEGER DEFAULT 0,
  built INTEGER DEFAULT 0,
  trained INTEGER DEFAULT 0,
  bought INTEGER DEFAULT 0,
  statements INTEGER DEFAULT 0,
  voted INTEGER DEFAULT 0,
  war INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, day)
);

CREATE TABLE IF NOT EXISTS coin_packages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  coins INTEGER,
  price_toman INTEGER,
  discount_percent REAL DEFAULT 0,
  is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS receipts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  kind TEXT,
  country_id INTEGER,
  coins INTEGER DEFAULT 0,
  toman INTEGER DEFAULT 0,
  photo_file_id TEXT DEFAULT '',
  status TEXT DEFAULT 'pending',
  note TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now')),
  reviewed_by INTEGER,
  reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  kind TEXT,
  text TEXT DEFAULT '',
  photo_file_id TEXT DEFAULT '',
  status TEXT DEFAULT 'open',
  reply TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now')),
  replied_at TEXT,
  replied_by INTEGER
);

CREATE TABLE IF NOT EXISTS un_votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT,
  kind TEXT,
  subject_id INTEGER,
  options TEXT DEFAULT '[]',
  status TEXT DEFAULT 'open',
  ends_at TEXT,
  channel_msg INTEGER,
  created_by INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS un_ballots (
  vote_id INTEGER,
  user_id INTEGER,
  choice INTEGER,
  weight INTEGER DEFAULT 1,
  voted_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (vote_id, user_id)
);

CREATE TABLE IF NOT EXISTS coin_sales (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  coins INTEGER DEFAULT 0,
  rate INTEGER DEFAULT 0,
  gain INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS provinces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  country_id INTEGER NOT NULL,
  idx INTEGER NOT NULL,
  name TEXT DEFAULT '',
  owner_id INTEGER,
  captured_at TEXT,
  UNIQUE(country_id, idx)
);

CREATE TABLE IF NOT EXISTS provinces_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  province_id INTEGER,
  from_owner INTEGER,
  to_owner INTEGER,
  war_id INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alliances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT DEFAULT '',
  leader_id INTEGER,
  status TEXT DEFAULT 'active',
  founded_at TEXT DEFAULT (datetime('now')),
  dissolved_at TEXT
);

CREATE TABLE IF NOT EXISTS alliance_members (
  alliance_id INTEGER,
  user_id INTEGER,
  role TEXT DEFAULT 'member',
  joined_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY(alliance_id, user_id)
);

CREATE TABLE IF NOT EXISTS alliance_invites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alliance_id INTEGER,
  inviter_id INTEGER,
  invitee_id INTEGER,
  status TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS enrichment (
  user_id INTEGER PRIMARY KEY,
  stage INTEGER DEFAULT 0,
  started_at TEXT,
  completes_at TEXT,
  centrifuges INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS wars (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attacker_id INTEGER,
  defender_id INTEGER,
  reason TEXT DEFAULT '',
  permission INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',
  war_crime INTEGER DEFAULT 0,
  started_at TEXT DEFAULT (datetime('now')),
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS battles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  war_id INTEGER,
  attacker_id INTEGER,
  defender_id INTEGER,
  atk_type TEXT,
  atk_power REAL DEFAULT 0,
  def_power REAL DEFAULT 0,
  result TEXT,
  loot INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cyber_ops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attacker_id INTEGER,
  defender_id INTEGER,
  kind TEXT,
  success INTEGER DEFAULT 0,
  amount INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  host_id INTEGER,
  guest_id INTEGER,
  status TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id INTEGER,
  amount INTEGER,
  price INTEGER,
  status TEXT DEFAULT 'open',
  buyer_id INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS statements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  text TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS admin_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admin_id INTEGER,
  action TEXT DEFAULT '',
  detail TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS game_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT DEFAULT '',
  text TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE,
  section TEXT DEFAULT 'general',
  file_id TEXT DEFAULT '',
  uploaded_by INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS seasons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  mode TEXT DEFAULT 'worldwar',
  is_active INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS season_votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  options TEXT DEFAULT '[]',
  required_votes INTEGER DEFAULT 10,
  status TEXT DEFAULT 'open',
  ends_at TEXT,
  channel_msg INTEGER,
  winner TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS season_ballots (
  vote_id INTEGER,
  user_id INTEGER,
  choice INTEGER,
  voted_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (vote_id, user_id)
);

CREATE TABLE IF NOT EXISTS negotiations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  initiator_id INTEGER,
  status TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT (datetime('now')),
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS negotiation_members (
  neg_id INTEGER,
  user_id INTEGER,
  role TEXT DEFAULT 'member',
  joined_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (neg_id, user_id)
);

CREATE TABLE IF NOT EXISTS negotiation_msgs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  neg_id INTEGER,
  sender_id INTEGER,
  text TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS treaties (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT,
  party_a INTEGER,
  party_b INTEGER,
  witness_id INTEGER,
  neg_id INTEGER,
  status TEXT DEFAULT 'pending',
  trade_percent REAL DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  confirmed_at TEXT,
  broken_at TEXT
);

CREATE TABLE IF NOT EXISTS treaty_confirms (
  treaty_id INTEGER,
  user_id INTEGER,
  confirmed_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (treaty_id, user_id)
);

CREATE TABLE IF NOT EXISTS direct_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_id INTEGER,
  to_id INTEGER,
  give_type TEXT,
  give_id INTEGER DEFAULT 0,
  give_qty INTEGER DEFAULT 0,
  want_type TEXT,
  want_id INTEGER DEFAULT 0,
  want_qty INTEGER DEFAULT 0,
  value_estimate INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS straits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT UNIQUE,
  name TEXT,
  emoji TEXT DEFAULT '⚓',
  is_active INTEGER DEFAULT 1,
  owner_id INTEGER,
  captured_at TEXT
);

CREATE TABLE IF NOT EXISTS strait_blockades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  strait_id INTEGER,
  owner_id INTEGER,
  target_user_id INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(strait_id, target_user_id)
);

CREATE TABLE IF NOT EXISTS rescue_campaigns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  war_id INTEGER,
  status TEXT DEFAULT 'open',
  winner_id INTEGER,
  distributed INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  ends_at TEXT,
  closed_at TEXT
);

CREATE TABLE IF NOT EXISTS rescue_donations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER,
  user_id INTEGER,
  energy INTEGER DEFAULT 0,
  voted_for INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS revolutions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  country_id INTEGER,
  severity INTEGER DEFAULT 60,
  started_at TEXT,
  ends_at TEXT,
  status TEXT DEFAULT 'active',
  trigger TEXT DEFAULT '',
  outcome TEXT DEFAULT '',
  money_spent INTEGER DEFAULT 0,
  troops_lost INTEGER DEFAULT 0,
  force_block_until TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS oil_business (
  user_id INTEGER PRIMARY KEY,
  level INTEGER DEFAULT 1,
  auto_sell INTEGER DEFAULT 0,
  last_sale_at TEXT,
  last_income INTEGER DEFAULT 0,
  total_income INTEGER DEFAULT 0,
  sales INTEGER DEFAULT 0,
  barrels_sold INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS oil_offers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id INTEGER,
  barrels INTEGER DEFAULT 0,
  price_money INTEGER DEFAULT 0,
  price_coins INTEGER DEFAULT 0,
  status TEXT DEFAULT 'open',
  buyer_id INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS currency_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  req_type TEXT,
  value TEXT,
  status TEXT DEFAULT 'pending',
  reviewed_by INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fb_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT,
  payload TEXT,
  op TEXT DEFAULT 'set',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assets_user ON player_assets(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_user ON player_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_receipts_status ON receipts(status);
CREATE INDEX IF NOT EXISTS idx_wars_att ON wars(attacker_id);
CREATE INDEX IF NOT EXISTS idx_wars_def ON wars(defender_id);
"""

ALL_TABLES = [
    "users", "admins", "countries", "states", "equipment_categories", "equipment",
    "soldier_types", "soldier_trainings", "buildings", "player_assets",
    "player_projects", "company_types", "companies", "laws", "religions",
    "governments", "missions", "mission_claims", "daily_progress",
    "coin_packages", "receipts", "tickets", "un_votes", "un_ballots",
    "wars", "battles", "cyber_ops", "bases", "trades", "statements",
    "settings", "admin_logs", "game_events", "images", "seasons",
    "season_votes", "season_ballots", "negotiations", "negotiation_members",
    "negotiation_msgs", "treaties", "treaty_confirms", "direct_trades", "straits",
    "strait_blockades", "rescue_campaigns", "rescue_donations", "oil_offers",
    "currency_requests", "fb_queue",
]


async def _add_column(table: str, column: str, decl: str) -> None:
    """افزودن ستون در صورت نبود (مهاجرت بی‌خطر و idempotent)."""
    cols = await db.fetchall(f"PRAGMA table_info({table})")
    names = {c["name"] for c in cols}
    if column not in names:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


MIGRATIONS = [
    ("states", "last_attack_at", "TEXT"),
    ("countries", "province_count", "INTEGER DEFAULT 5"),
    ("countries", "collapsed", "INTEGER DEFAULT 0"),
    ("states", "oil_stock", "INTEGER DEFAULT 0"),
    ("states", "energy", "INTEGER DEFAULT 5000"),
    ("states", "water", "INTEGER DEFAULT 5000"),
    ("states", "gas", "INTEGER DEFAULT 5000"),
    ("states", "materials", "INTEGER DEFAULT 1000"),
    ("states", "diplomacy", "REAL DEFAULT 50"),
    ("countries", "oil_reserve", "INTEGER DEFAULT 0"),
    ("countries", "oil_richness", "REAL DEFAULT 0"),
    ("countries", "currency", "TEXT DEFAULT ''"),
    ("countries", "iso_code", "TEXT DEFAULT ''"),
    ("countries", "flag_url", "TEXT DEFAULT ''"),
    ("countries", "custom_flag", "TEXT DEFAULT ''"),
    ("images", "country_id", "INTEGER DEFAULT 0"),
    ("equipment", "subcategory", "TEXT DEFAULT ''"),
    ("rescue_campaigns", "ends_at", "TEXT"),
    ("battles", "strategy", "TEXT DEFAULT ''"),
    ("countries", "gdp_factor", "REAL DEFAULT 1"),
    ("countries", "oil_income_base", "INTEGER DEFAULT 2"),
    ("countries", "leader_name", "TEXT DEFAULT ''"),
    ("countries", "leader_title", "TEXT DEFAULT 'رئیس‌جمهور'"),
    ("countries", "leader_since", "TEXT DEFAULT ''"),
    ("revolutions", "force_block_until", "TEXT"),
]


def backup_db() -> None:
    """پشتیبان‌گیری خودکار از دیتابیس قبل از اعمال هرگونه تغییر یا راه‌اندازی."""
    import shutil
    from datetime import datetime
    from pathlib import Path
    p = Path(DB_PATH)
    if not p.exists() or p.stat().st_size == 0:
        return
    backup_dir = p.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"wwgame_{stamp}.db"
    try:
        shutil.copy2(p, target)
        backups = sorted(backup_dir.glob("wwgame_*.db"))
        for old in backups[:-7]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass


class Database:
    """پوشش سبک aiosqlite با ردیف‌های dict."""

    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA busy_timeout=15000")
            await self._conn.execute("PRAGMA wal_autocheckpoint=500")
            await self._conn.execute("PRAGMA synchronous=NORMAL")
            await self._conn.execute("PRAGMA foreign_keys=OFF")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect() فراخوانی نشده است")
        return self._conn

    async def execute(self, sql: str, params: tuple = ()) -> int:
        cur = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cur.lastrowid or 0

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        cur = await self.conn.execute(sql, params)
        row = await cur.fetchone()
        return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = await self.conn.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._conn is not None:
            try:
                await self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            await self._conn.close()
            self._conn = None


db = Database(DB_PATH)


async def get_setting(key: str, default: str = "") -> str:
    row = await db.fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return (row["value"] if row else default) or default


INITIAL_MONEY = 200_000_000   # ۲۰۰ میلیون — بودجه اولیه پیش‌فرض


async def get_initial_money() -> int:
    """بودجه اولیه هر بازیکن تازه‌وارد (قابل تنظیم از پنل ادمین)."""
    try:
        value = int(float(await get_setting("initial_money", str(INITIAL_MONEY))))
    except (TypeError, ValueError):
        return INITIAL_MONEY
    return value if value > 0 else INITIAL_MONEY


async def set_setting(key: str, value: str) -> None:
    await db.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


async def init_db() -> None:
    """ایجاد جدول‌ها، مهاجرت‌ها، داده‌های اولیه و سوپرادمین — idempotent و کاملاً محافظت‌شده."""
    backup_db()
    await db.connect()
    await db.conn.executescript(SCHEMA)
    await db.conn.commit()

    # مهاجرت ستون‌های جدید (برای دیتابیس‌های قدیمی)
    for table, column, decl in MIGRATIONS:
        await _add_column(table, column, decl)

    # داده‌های اولیه فقط وقتی جدول خالی است یا با UPDATE بدون حذف
    await seed.run(db)

    # سوپرادمین‌ها از کانفیگ (SUPER_ADMIN_IDS + سوپرادمین‌های ثابت بازی)
    try:
        from core.admins import ensure_super_admins
        await ensure_super_admins()
    except Exception:
        if SUPER_ADMIN_ID:
            await db.execute(
                "INSERT OR IGNORE INTO admins(id, name, is_super, perms) VALUES(?, 'سوپرادمین', 1, '[]')",
                (SUPER_ADMIN_ID,),
            )

    # تنظیمات پیش‌فرض
    from core import texts
    for key, value in DEFAULT_SETTINGS.items():
        if key == "guide_text":
            value = texts.GUIDE
        await db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (key, value))

    # ── کانال/گروه رسمی + نام بازی: مقادیر کد بر مقادیر کهنهٔ دیتابیس اولویت دارند ──
    try:
        import json

        from core import config as cfg
        await db.execute("UPDATE settings SET value=? WHERE key='join_channels'",
                         (json.dumps(list(cfg.OFFICIAL_CHANNELS), ensure_ascii=False),))
        await db.execute("UPDATE settings SET value=? WHERE key='announcement_channel'",
                         (cfg.OFFICIAL_CHANNEL,))
        await db.execute("UPDATE settings SET value=? WHERE key='game_group'",
                         (cfg.OFFICIAL_GROUP,))

        # متن استارت/راهنما: هر مقدار کهنه‌ای که هنوز نام قدیمی بازی را دارد پاک می‌شود
        # تا متن تازهٔ کد نمایش داده شود (متن دلخواه ادمینِ بدون نام قدیمی دست‌نخورده می‌ماند).
        legacy_marks = ("WORLD_WAR_FIRE", "worldwarFIRE", "worldwarfire", "WORLD WAR FIRE")

        def _is_legacy(value: str) -> bool:
            """آیا این مقدار هنوز نام قدیمی بازی را دارد؟"""
            v = value or ""
            if any(m in v for m in legacy_marks):
                return True
            return "جنگ جهانی" in v and cfg.GAME_NAME not in v

        for key in ("start_text", "guide_text"):
            row = await db.fetchone("SELECT value FROM settings WHERE key=?", (key,))
            if row and row["value"] and _is_legacy(row["value"]):
                if key == "guide_text":
                    await db.execute("UPDATE settings SET value=? WHERE key='guide_text'",
                                     (texts.GUIDE,))
                else:
                    await db.execute("UPDATE settings SET value='' WHERE key='start_text'")
        # کارت به کارت بازنشسته شد: شماره کارت/نام صاحب کارت پاک می‌شود تا فروش
        # فقط از طریق آیدی پشتیبانی انجام شود (هر مقداری که ادمین بعداً بگذارد حفظ می‌شود).
        for key in ("c2c_card", "c2c_holder"):
            row = await db.fetchone("SELECT value FROM settings WHERE key=?", (key,))
            if row and (row["value"] or "").strip():
                await db.execute("UPDATE settings SET value='' WHERE key=?", (key,))

        row = await db.fetchone("SELECT value FROM settings WHERE key='season_name'")
        if row and row["value"] and _is_legacy(row["value"]):
            await db.execute("UPDATE settings SET value=? WHERE key='season_name'",
                             ("⚔️ سیزن ۱ — " + cfg.GAME_NAME,))
    except Exception:
        pass

    # مهاجرت مقدار قدیمی بودجه اولیه (۲۰۰) به مقیاس میلیونی (۲۰۰٫۰۰۰٫۰۰۰)
    try:
        row = await db.fetchone("SELECT value FROM settings WHERE key='initial_money'")
        if row and row["value"]:
            try:
                old_value = float(row["value"])
            except (TypeError, ValueError):
                old_value = None
            if old_value is not None and old_value < 1_000:
                await set_setting("initial_money", str(INITIAL_MONEY))
    except Exception:
        pass

    # مهاجرت قاعدهٔ قدیمی تصاحب تنگه (۲.۵ برابر) به نبرد واقعی (۱.۳ برابر)
    try:
        row = await db.fetchone("SELECT value FROM settings WHERE key='strait_capture_ratio'")
        if row and str(row["value"]).strip() in ("2.5", "2,5"):
            await set_setting("strait_capture_ratio", "1.3")
    except Exception:
        pass

    # یکپارچه‌سازی مالکیت کشورها با کاربران (مالکیت دوگانه، مالک بی‌کاربر و ...)
    await sync_country_owners()

    # 🗺 ساخت ۵ استان پایه برای هر کشور (idempotent)
    try:
        from core.provinces import ensure_provinces
        await ensure_provinces()
    except Exception:
        pass


async def sync_country_owners() -> None:
    """هم‌ترازکردن countries.owner_id با users.country_id.

    باگ‌های رایجی که این تابع رفع می‌کند:
      • کاربری کشور دارد ولی owner_id کشور خالی است → کشور در لیست اعلان جنگ/سایبری دیده نمی‌شد.
      • دو کاربر هم‌زمان یک کشور را claim کرده‌اند → کشور دو مالک داشت و جنگ روی id اشتباه ثبت می‌شد.
      • کشور owner_id دارد ولی کاربرش country_id ندارد (انتساب از پنل ادمین) → کاربر کشور را از دست می‌داد.
    """
    try:
        # ۱) کشورهایی که owner_id دارند ولی مالکشان country_id ندارد → به مالک برگردانده می‌شود
        await db.execute("""
            UPDATE users SET country_id = (
                SELECT c.id FROM countries c
                WHERE c.owner_id = users.id AND (users.country_id IS NULL OR users.country_id = 0)
                ORDER BY c.id LIMIT 1
            )
            WHERE (country_id IS NULL OR country_id = 0)
              AND EXISTS (SELECT 1 FROM countries c WHERE c.owner_id = users.id)
              AND banned = 0
        """)
        # ۲) مالکیت دوگانه: اگر owner_id کشور یکی از claimant ها باشد همان می‌ماند،
        #    در غیر این صورت جدیدترین claimant مالک می‌شود و بقیه آزاد می‌شوند
        await db.execute("""
            UPDATE users SET country_id = NULL
            WHERE country_id IS NOT NULL AND banned = 0 AND id NOT IN (
                SELECT COALESCE(
                    (SELECT u2.id FROM users u2
                     WHERE u2.country_id = c.id AND u2.banned = 0 AND u2.id = c.owner_id LIMIT 1),
                    (SELECT u3.id FROM users u3
                     WHERE u3.country_id = c.id AND u3.banned = 0
                     ORDER BY u3.country_taken_at DESC, u3.id DESC LIMIT 1)
                )
                FROM countries c
                WHERE c.id IN (SELECT country_id FROM users WHERE country_id IS NOT NULL AND banned = 0)
            )
        """)
        # ۳) پر کردن owner_id خالی از claimant های واقعی
        await db.execute("""
            UPDATE countries SET owner_id = (
                SELECT u.id FROM users u
                WHERE u.country_id = countries.id AND u.banned = 0
                ORDER BY u.country_taken_at DESC, u.id DESC LIMIT 1
            )
            WHERE EXISTS (SELECT 1 FROM users u WHERE u.country_id = countries.id AND u.banned = 0)
              AND (owner_id IS NULL OR owner_id = 0)
        """)
    except Exception:
        import logging
        logging.getLogger("db").exception("sync_country_owners failed")


DEFAULT_SETTINGS = {
    "coin_sell_rate": "100000000",   # پول پایه‌ای که بابت فروش هر سکه به بازیکن داده می‌شود
    "coin_price_toman": "1000",           # قیمت هر سکه شاهی به تومان
    "coins_to_money_rate": "5000000",     # نرخ تبدیل سکه شاهی به پول پایه
    "sales_support": "@MiddleEastDefendSupport",  # آیدی پشتیبانی فروش (جای کارت به کارت)
    "c2c_card": "",    # خالی = نمایش داده نمی‌شود (فروش از طریق پشتیبانی انجام می‌شود)
    "c2c_holder": "",
    "join_channels": '["@WordWarWord", "@Jangjhani313"]',      # کانال‌های عضویت اجباری (گپ + کانال خبری)
    "announcement_channel": "@Jangjhani313",                   # کانال اعلانات/اخبار بازی
    "game_group": "@WordWarWord",                              # گپ/ابرگروه رسمی بازی
    "start_text": "🌍 به بازی «جنگ جهانی ۳» خوش آمدید!\nبرای ورود به بازی در کانال‌ها و گروه‌های زیر عضو شوید و سپس دکمه «🔍 بررسی عضویت» را بزنید.",
    "bot_off": "0",
    "trade_tax_percent": "5",
    "income_base": "100",
    # بودجه اولیه‌ای که هر بازیکن تازه‌وارد دریافت می‌کند (قابل تغییر از پنل ادمین)
    "initial_money": "200000000",
    # رای‌گیری مجوز جنگ سازمان ملل — ۳۰ دقیقه
    "war_vote_minutes": "30",
    "vote_duration_hours": "24",
    "country_change_hours": "8",
    "cyber_cooldown_hours": "6",
    "food_price_per_ton": "50000",
    "special_toman_multiplier": "100000",
    "guide_text": "",
    # ── درآمد خودکار ۳۰ دقیقه‌ای ──
    "income_interval_minutes": "5",
    # ─── موتور درآمد میلیونی (core/income.py) ───
    "income_tax_base_m": "10",        # پایهٔ مالیات هر دوره (میلیون)
    "income_tax_step_m": "8",         # به ازای هر واحد ضریب اقتصاد کشور (میلیون)
    "income_oil_unit_m": "1",         # ضریب oil_income_base → پول (میلیون)
    "income_strait_m": "14",          # عوارض هر تنگه برای مالک (میلیون)
    "income_growth_cap": "5",         # سقف ضریب ارتقا
    "oil_rig_bonus_percent": "8",     # درصد افزایش درآمد نفت به ازای هر دکل نفتی
    # ─── نبرد و استان‌ها ───
    "attack_cooldown_minutes": "3",   # فاصله بین دو حمله
    "province_defense_min_chance": "10",
    "province_defense_max_chance": "70",
    # ─── اتحاد ───
    "alliance_defense_percent": "30",
    "alliance_max_members": "8",
    # ── بخش‌ها (روشن/خاموش) 1=روشن ──
    "sec_negotiation": "1",
    "sec_direct_trade": "1",
    "sec_rescue_sale": "1",
    "sec_straits": "1",
    "sec_oil": "1",
    "sec_rescue_org": "1",
    # ── نفت ──
    "oil_rig_barrels_per_tick": "500",       # بشکه در هر تیک به ازای هر دکل
    "oil_exploration_cost": "50000000",      # هزینه اکتشاف
    "oil_exploration_add": "2000000000",     # بشکه افزوده در اکتشاف موفق
    "oil_price_per_barrel": "8000",          # ارزش ریالی هر بشکه (محاسبه ارزش معامله)
    # ── انرژی/منابع ──
    "rescue_energy_price": "2000",           # پول به ازای هر کیلووات‌ساعت اهدایی
    "rescue_water_price": "3000",
    "rescue_gas_price": "4000",
    "rescue_oil_price": "8000",
    # ── سازمان نجات ──
    "rescue_vote_hours": "24",
    "rescue_payout_percent": "10",
    # ── رهبری، ترور و انقلاب ──
    "revolution_minutes": "30",              # فرصت مهار انقلاب (دقیقه)
    "revolution_initial_severity": "65",     # شدت اولیه انقلاب
    "revolution_income_penalty": "0.55",     # ضریب درآمد در زمان انقلاب (۵۵٪)
    "revolution_success_satisfaction": "20", # افت رضایت در صورت پیروزی انقلاب
    "revolution_success_money_pct": "0.15",  # غارت خزانه در صورت پیروزی انقلاب
    "assassination_cooldown_hours": "6",
    # ── کسب‌وکار نفت (ارتقا + فروش خودکار) ──
    "oil_auto_sell_minutes": "10",           # هر ۱۰ دقیقه درآمد فروش نفت
    "oil_level_max": "12",                   # سقف ارتقای تجهیزات استخراج
    "oil_level_base_cost": "30000000",       # هزینه ارتقا از سطح ۱ به ۲
    "oil_level_cost_factor": "1.6",          # ضریب گران‌شدن هر سطح بعدی
    "oil_level_barrel_bonus": "0.15",        # +۱۵٪ استخراج به ازای هر سطح
    "oil_level_income_bonus": "0.12",        # +۱۲٪ درآمد فروش به ازای هر سطح
    "oil_sale_need_barrels": "5000",         # بشکه مرجع برای فروش کامل
    # ── تنگه‌ها ──
    "strait_min_naval": "500",              # حداقل قدرت دریایی برای تصاحب تنگه آزاد
    "strait_capture_ratio": "1.3",           # حداقل نسبت توان دریایی برای حمله به تنگه دارای مالک
    "strait_toll_percent": "1.5",            # عوارض درآمد غیرمالیاتی
    # ── ارز ──
    "main_currency": "",                     # نام ارز اصلی فعلی بازی
    "main_currency_owner": "",               # نام کشور مالک ارز اصلی
    "main_currency_score": "0",
    # ── سیزن ──
    "season_name": "فصل آغازین",
    "season_mode": "worldwar",
    "season_vote_hours": "24",
    "season_required_votes": "10",
    # ── گزارش روزانه ادمین ──
    "daily_report_hour": "9",                # ساعت تهران
}

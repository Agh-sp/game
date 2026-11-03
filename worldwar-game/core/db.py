"""لایه دیتابیس: اتصال aiosqlite + اسکیمای کامل بازی جنگ جهانی."""
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
  money INTEGER DEFAULT 50000000,
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
  owner_id INTEGER
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
    ("equipment", "subcategory", "TEXT DEFAULT ''"),
    ("rescue_campaigns", "ends_at", "TEXT"),
]


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
            await self._conn.execute("PRAGMA busy_timeout=8000")
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
            await self._conn.close()
            self._conn = None


db = Database(DB_PATH)


async def get_setting(key: str, default: str = "") -> str:
    row = await db.fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return (row["value"] if row else default) or default


async def set_setting(key: str, value: str) -> None:
    await db.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


async def init_db() -> None:
    """ایجاد جدول‌ها، مهاجرت‌ها، داده‌های اولیه و سوپرادمین — idempotent."""
    await db.connect()
    await db.conn.executescript(SCHEMA)
    await db.conn.commit()

    # مهاجرت ستون‌های جدید (برای دیتابیس‌های قدیمی)
    for table, column, decl in MIGRATIONS:
        await _add_column(table, column, decl)

    # داده‌های اولیه فقط وقتی جدول خالی است
    await seed.run(db)

    # سوپرادمین از کانفیگ
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


DEFAULT_SETTINGS = {
    "coin_price_toman": "1000",           # قیمت هر سکه شاهی به تومان
    "coins_to_money_rate": "5000000",     # نرخ تبدیل سکه شاهی به پول پایه
    "c2c_card": "6037-0000-0000-0000",    # شماره کارت به کارت
    "c2c_holder": "نام صاحب کارت",
    "join_channels": '["@worldwarFIRE", "@worldwarfire_gp"]',  # کانال‌های عضویت اجباری
    "announcement_channel": "@worldwarFIRE",                   # کانال اعلانات
    "game_group": "@worldwarfire_gp",                          # ابرگروه بازی
    "start_text": "🌍 به بازی «جنگ جهانی» خوش آمدید!\nبرای ورود به بازی در کانال‌ها و گروه‌های زیر عضو شوید و سپس دکمه «🔍 بررسی عضویت» را بزنید.",
    "bot_off": "0",
    "trade_tax_percent": "5",
    "income_base": "100",
    "vote_duration_hours": "24",
    "country_change_hours": "8",
    "cyber_cooldown_hours": "6",
    "food_price_per_ton": "50000",
    "special_toman_multiplier": "100000",
    "guide_text": "",
    # ── درآمد خودکار ۳۰ دقیقه‌ای ──
    "income_interval_minutes": "30",
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
    # ── تنگه‌ها ──
    "strait_min_naval": "500",              # حداقل قدرت دریایی برای تصاحب تنگه آزاد
    "strait_capture_ratio": "2.5",           # ضریب تصاحب تنگه دارای مالک
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

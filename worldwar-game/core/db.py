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

CREATE TABLE IF NOT EXISTS nuclear_sites (
  user_id INTEGER PRIMARY KEY,
  stage INTEGER DEFAULT 0,
  kind TEXT DEFAULT '',
  emoji TEXT DEFAULT '☢️',
  hp INTEGER DEFAULT 100,
  max_hp INTEGER DEFAULT 100,
  centrifuges INTEGER DEFAULT 0,
  active INTEGER DEFAULT 1,
  destroyed_at TEXT,
  last_attack_at TEXT,
  leaked INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS nuclear_arsenal (
  user_id INTEGER PRIMARY KEY,
  bombs INTEGER DEFAULT 0,            -- ☢️ کلاهک هسته‌ای آمادهٔ استفاده
  built_total INTEGER DEFAULT 0,      -- تعداد کل ساخته‌شده (آمار)
  last_built_at TEXT,
  last_used_at TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS nuclear_bombs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER,
  name TEXT DEFAULT '',               -- نام دلخواه سلاح (مثل «فاتح هسته‌ای»)
  yield_kt REAL DEFAULT 0,            -- قدرت (کیلوتن)
  state TEXT DEFAULT 'ready',         -- ready | launched | spent | destroyed
  built_at TEXT DEFAULT (datetime('now')),
  used_at TEXT,
  target_id INTEGER DEFAULT 0,
  ready_at TEXT                       -- زمان تحویل کلاهک در حال ساخت (NULL = ساخته شده)
);

CREATE TABLE IF NOT EXISTS nuclear_strikes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attacker_id INTEGER,
  defender_id INTEGER,
  success INTEGER DEFAULT 0,
  damage INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS country_attrition (
  user_id INTEGER PRIMARY KEY,
  wear REAL DEFAULT 0,
  strikes INTEGER DEFAULT 0,
  last_at TEXT,
  last_attacker INTEGER,
  recovering INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ceasefire_offers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  war_id INTEGER,
  from_id INTEGER,
  to_id INTEGER,
  status TEXT DEFAULT 'pending',
  ends_at TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS arms_deals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id INTEGER,
  buyer_id INTEGER,
  item_type TEXT,
  item_id INTEGER,
  quantity INTEGER DEFAULT 0,
  unit_price INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sabotage_ops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attacker_id INTEGER,
  defender_id INTEGER,
  kind TEXT DEFAULT '',
  item_id INTEGER DEFAULT 0,
  success INTEGER DEFAULT 0,
  note TEXT DEFAULT '',
  last_at TEXT DEFAULT (datetime('now')),
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS internet_infra (
  user_id INTEGER PRIMARY KEY,
  level INTEGER DEFAULT 0,
  updated_at TEXT DEFAULT (datetime('now'))
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
  created_at TEXT DEFAULT (datetime('now')),
  kind TEXT DEFAULT 'land',
  name TEXT DEFAULT ''
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
  value TEXT DEFAULT '',
  secret INTEGER DEFAULT 0
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

-- ═══ 🧨 موتور واقع‌گرایی (نسخهٔ ۹) ═══
CREATE TABLE IF NOT EXISTS supply_stock (
  user_id INTEGER PRIMARY KEY,
  ammo REAL DEFAULT 0,
  fuel REAL DEFAULT 0,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS strikes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  kind TEXT DEFAULT 'unrest',
  severity REAL DEFAULT 0,
  demand TEXT DEFAULT '',
  started_at TEXT,
  ends_at TEXT,
  status TEXT DEFAULT 'active',
  outcome TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS debts (
  user_id INTEGER PRIMARY KEY,
  principal INTEGER DEFAULT 0,
  remaining INTEGER DEFAULT 0,
  rate_percent REAL DEFAULT 2,
  periods INTEGER DEFAULT 0,
  taken_at TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS market (
  key TEXT PRIMARY KEY,
  name TEXT DEFAULT '',
  price REAL DEFAULT 0,
  prev_price REAL DEFAULT 0,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS market_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT DEFAULT '',
  price REAL DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT DEFAULT '',
  user_id INTEGER DEFAULT 0,
  ip TEXT DEFAULT '',
  detail TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  to_user INTEGER DEFAULT 0,
  text TEXT DEFAULT '',
  sent INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS party_state (
  user_id INTEGER PRIMARY KEY,
  party TEXT DEFAULT 'industry',
  support REAL DEFAULT 50,
  campaign INTEGER DEFAULT 0,
  next_at TEXT,
  terms INTEGER DEFAULT 0,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS refugee_flows (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_user INTEGER,
  to_user INTEGER,
  count INTEGER DEFAULT 0,
  reason TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS intel_levels (
  user_id INTEGER PRIMARY KEY,
  value INTEGER DEFAULT 0,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS intel_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attacker_id INTEGER,
  defender_id INTEGER,
  est_attack INTEGER DEFAULT 0,
  est_defense INTEGER DEFAULT 0,
  real_attack INTEGER DEFAULT 0,
  real_defense INTEGER DEFAULT 0,
  radius REAL DEFAULT 0,
  accuracy INTEGER DEFAULT 0,
  exposed INTEGER DEFAULT 0,
  expires_at TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS season_weather (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season_index INTEGER DEFAULT 0,
  season TEXT DEFAULT 'spring',
  started_at TEXT,
  ends_at TEXT,
  drought INTEGER DEFAULT 0,
  storm INTEGER DEFAULT 0,
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
    "currency_requests", "fb_queue", "nuclear_sites", "nuclear_strikes",
    "internet_infra", "country_attrition", "ceasefire_offers", "arms_deals",
    "sabotage_ops", "supply_stock", "strikes", "debts",
    "market", "market_history", "season_weather", "intel_levels", "intel_reports", "refugee_flows", "party_state", "security_events", "security_alerts", "nuclear_arsenal", "nuclear_bombs",
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
    ("states", "food", "INTEGER DEFAULT 0"),
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
    ("bases", "kind", "TEXT DEFAULT 'land'"),
    ("bases", "name", "TEXT DEFAULT ''"),
    # 🧨 موتور واقع‌گرایی
    ("users", "inflation", "REAL DEFAULT 0"),
    ("states", "unrest", "REAL DEFAULT 0"),
    ("states", "unrest_peak", "REAL DEFAULT 0"),
    ("states", "strike_until", "TEXT"),
    ("states", "strike_demand", "TEXT DEFAULT ''"),
    ("states", "revolt_until", "TEXT"),
    ("states", "supply_loss_until", "TEXT"),
    ("states", "revolt_winner", "TEXT DEFAULT ''"),
    ("states", "last_unrest_day", "TEXT DEFAULT ''"),
    ("countries", "collapse_reason", "TEXT DEFAULT ''"),
    ("countries", "collapse_at", "TEXT"),
    ("season_weather", "ends_at", "TEXT"),
    ("season_weather", "drought", "INTEGER DEFAULT 0"),
    ("season_weather", "storm", "INTEGER DEFAULT 0"),
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


# کلیدهایی که مقدارشان محرمانه است (کلید وبهوک، گذرواژهٔ پنل) و از نمای
# عمومی جدول settings در پنل وب پنهان می‌شوند.
SECRET_SETTING_KEYS = ("webhook_secret", "panel_password",
                       "security_alert_to", "broadcast_lock_until")


async def set_setting(key: str, value: str) -> None:
    await db.execute(
        "INSERT INTO settings(key, value, secret) VALUES(?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value, 1 if key in SECRET_SETTING_KEYS else 0),
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
    # ستون «محرمانه» در settings و علامت‌گذاری کلیدهای حساس (دیتابیس‌های قبلی)
    await _add_column("settings", "secret", "INTEGER DEFAULT 0")
    try:
        marks = ",".join("?" for _ in SECRET_SETTING_KEYS)
        await db.execute(f"UPDATE settings SET secret=1 WHERE key IN ({marks})",
                         SECRET_SETTING_KEYS)
    except Exception:
        pass

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
    "income_tax_base_m": "55",        # پایهٔ مالیات هر دوره (میلیون)
    "income_tax_step_m": "25",        # به ازای هر واحد ضریب اقتصاد کشور (میلیون)
    "income_oil_unit_m": "3",         # ضریب oil_income_base → پول (میلیون)
    "income_oil_floor_m": "55",       # کف پایهٔ درآمد نفتی هر دوره (میلیون)
    "income_strait_m": "45",          # عوارض هر تنگه برای مالک (میلیون)
    "income_resource_m": "18",        # فروش مازاد هر بخش منابع (برق/آب/گاز/غذا) — میلیون
    "income_floor_m": "110",          # کف تضمینی کل درآمد هر دوره (میلیون)
    # ── ♻️ فروش دستی منابع (gamebot/handlers/resources.py) ──
    "res_price_power": "60",          # پول هر واحد برق
    "res_price_water": "40",          # پول هر واحد آب
    "res_price_gas": "90",            # پول هر واحد گاز
    "res_price_food": "120",          # پول هر واحد غذا
    "res_price_oil": "25000",         # پول هر بشکه نفت
    "res_price_materials": "9000",    # پول هر واحد مصالح
    "sec_resource_sale": "1",         # بخش فروش منابع روشن/خاموش
    "income_growth_cap": "8",         # سقف ضریب ارتقا
    "oil_rig_bonus_percent": "12",    # درصد افزایش درآمد نفت به ازای هر دکل نفتی
    # ─── نبرد و استان‌ها ───
    "attack_cooldown_minutes": "3",   # فاصله بین دو حمله
    "cyber_cooldown_minutes": "20",   # فاصله بین دو عملیات سایبری (قبلاً ۶ ساعت)
    "naval_base_cost": "300000000",   # هزینهٔ ساخت پایگاه دریایی (اجارهٔ بندر)
    "naval_base_sea_power": "1500",   # قدرت دریایی که هر پایگاه دریایی فراهم می‌کند
    "capture_province_bonus": "15",   # شانس اضافه تصرف استان در حملهٔ تسخیر (درصد)
    "conquest_loot_bonus": "20",      # درصد غارت بیشتر در حملهٔ تسخیر
    # ── ☢️ تأسیسات هسته‌ای ──
    "nuclear_leak_chance": "35",      # شانس نشت رادیواکتیو در تخریب کامل (درصد)
    "nuclear_rebuild_cost": "120000000",  # هزینهٔ پایهٔ بازسازی تأسیسات
    "nuclear_site_hp": "100",         # استحکام پایهٔ تأسیسات
    # ── 🕊 آتش‌بس و صلح (core/ceasefire.py) ──
    "ceasefire_offer_hours": "24",          # مهلت پاسخ به پیشنهاد آتش‌بس
    "ceasefire_cooldown_hours": "6",        # فاصلهٔ مجاز بین دو پیشنهاد آتش‌بس
    "attrition_surrender_threshold": "60",  # حداقل فرسایش برای مجاز بودن تسلیم
    "surrender_provinces": "2",             # تعداد استانی که در تسلیم واگذار می‌شود
    # ── 🛒 بازار تسلیحات (core/arms.py) ──
    "arms_commission_percent": "5",         # کمیسیون بازار تسلیحات
    "arms_max_quantity": "5000",            # حداکثر تعداد هر معاملهٔ تسلیحات
    "arms_listing_hours": "48",             # اعتبار آگهی فروش تسلیحات
    # ── ☢️ غنی‌سازی اورانیوم (core/enrichment.py) ──
    "enrichment_stage_minutes": "5",        # مدت هر مرحلهٔ غنی‌سازی به دقیقه
    # ── 🎯 خرابکاری در تأسیسات (core/sabotage.py) ──
    "sabotage_cooldown_minutes": "20",      # کول‌داون بین دو خرابکاری (دقیقه)
    "sabotage_satisfaction_hit": "3",       # افت رضایت مدافع در هر خرابکاری موفق
    "sabotage_wear_add": "8",               # فرسایش اضافه‌شده به مدافع
    # ── ⚔️ جنگ فرسایشی و نابودی واقعی (core/attrition.py) ──
    "attrition_per_strike": "12",          # فرسایش اضافه‌شده به ازای هر حملهٔ موفق (٪)
    "attrition_failed_strike_share": "0.35",  # سهم فرسایش در حملهٔ ناموفق
    "attrition_max_wear": "90",            # سقف فرسایش (٪)
    "attrition_decay_per_hour": "6",       # بازیابی خودکار در هر ساعت (٪)
    "attrition_defense_penalty": "0.6",    # ضریب کاهش توان دفاعی بر اثر فرسایش
    "attrition_income_penalty": "1.0",     # ضریب کاهش درآمد بر اثر فرسایش
    "attrition_morale_base": "3",          # ریزش پایهٔ رضایت در هر حملهٔ موفق
    "attrition_morale_per_wear": "0.12",   # ریزش اضافه به ازای هر درصد فرسایش
    "attrition_collapse_threshold": "85",  # آستانهٔ سقوط بر اثر فرسایش (٪)
    # ── 🌐 رفاه اینترنت (core/internet.py) ──
    "internet_max_level": "5",              # حداکثر سطح زیرساخت اینترنت
    "internet_upgrade_cost": "80000000",    # هزینهٔ پایهٔ ارتقای یک سطح (پول)
    "internet_materials_per_level": "250",  # مصالح لازم پایه برای هر ارتقا
    "internet_growth_bonus": "5",           # درصد افزایش ضریب درآمد به ازای هر سطح
    "internet_satisfaction_bonus": "2",     # امتیاز رضایت به ازای هر سطح
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
    "strait_capture_ratio": "1.3",           # نسبت توان لازم برای تصرف در یک حمله
    "strait_attrition_percent": "18",        # درصد فرسایش ناوگان مدافع در هر حمله
    "strait_attrition_min_attacker": "5",    # حداقل درصد تلفات مهاجم در هر حمله
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
    # ═══ 🧨 موتور واقع‌گرایی ═══
    # ۱) 🚚 زنجیرهٔ تأمین و مهمات
    "sec_supply": "1",                        # بخش تأمین روشن/خاموش
    "supply_ammo_per_tick": "120",            # مهمات تولیدی هر دوره (پایه)
    "supply_fuel_per_tick": "150",            # سوخت تولیدی هر دوره (پایه)
    "supply_ammo_per_soldier": "2.5",         # مصرف مهمات به ازای هر یگان مهاجم
    "supply_fuel_per_soldier": "3",           # مصرف سوخت به ازای هر یگان مهاجم
    "supply_attack_penalty": "0.55",          # ضریب قدرت حمله با انبار خالی
    "supply_penalty_cap": "45",               # حداکثر درصد افت (٪)
    "supply_ration_per_soldier": "3",         # مصرف تدارکات روزانه هر سرباز
    "supply_unfed_penalty": "0.35",           # سهم افت قدرت با انبار خالی در گوش‌به‌زنگ
    "supply_sabotage_pct": "0.08",            # سهم انبار که هر خرابکاری صنعتی می‌سوزاند
    "supply_buy_price": "60000",              # قیمت هر واحد مهمات در بازار داخلی
    "supply_fuel_price": "50000",             # قیمت هر واحد سوخت داخلی
    # ۲) ✊ اعتصاب و اعتراض خیابانی
    "sec_unrest": "1",
    "unrest_decay_per_period": "4",           # بازیابی خودکار هر دورهٔ درآمد (امتیاز)
    "unrest_strike_threshold": "65",          # آستانهٔ اعتصاب سراسری
    "unrest_strike_minutes": "120",           # مدت اعتصاب (دقیقه)
    "unrest_strike_income_penalty": "0.5",    # ضریب درآمد در اعتصاب
    "unrest_subsidy_step": "15",              # هر بستهٔ یارانه چند امتیاز کم می‌کند
    "unrest_subsidy_cost_m": "40",            # هزینهٔ هر بسته (میلیون)
    "unrest_crackdown_gain": "22",            # کاهش ناآرامی با سرکوب نظامی
    "unrest_crackdown_sat": "6",              # افت رضایت با سرکوب
    "unrest_crackdown_loss_pct": "0.06",      # سهم سربازان ازدست‌رفته در سرکوب
    "unrest_ignore_gain": "12",               # کاهش ناآرامی با نادیده‌گرفتن
    "unrest_ignore_sat": "9",                 # افت رضایت با نادیده‌گرفتن
    "unrest_rise_per_miss": "22",             # افزایش ناآرامی بابت هر دورهٔ بی‌اعتنایی
    "unrest_strike_fail_penalty": "18",       # افت رضایت با شکست مذاکره
    # ۳) ✊ شورش و جنگ داخلی
    "sec_revolt": "1",
    "revolt_threshold": "90",                 # آستانهٔ شروع جنگ داخلی
    "revolt_minutes": "90",                   # مدت مهار شورش
    "revolt_income_penalty": "0.35",          # ضریب درآمد در جنگ داخلی
    "revolt_negotiate_cost_m": "150",         # هزینهٔ امتیازدهی به شورشی‌ها (میلیون)
    "revolt_negotiate_gain": "35",            # کاهش شدت با امتیازدهی
    "revolt_bribe_cost_m": "300",             # هزینهٔ نفوذ و خریدن فرماندهان (میلیون)
    "revolt_bribe_chance": "60",              # شانس موفقیت رشوه (٪)
    "revolt_bribe_gain": "40",                # کاهش شدت در صورت موفقیت رشوه
    "revolt_crush_loss_pct": "0.18",          # سهم سربازان ازدست‌رفته در سرکوب
    "revolt_rival_share": "0.10",             # سهم دارایی‌ها به شورشی‌ها
    "revolt_rival_money_pct": "0.25",         # سهم خزانه به شورشی‌ها
    # ۶) 🗳 انتخابات دوره‌ای و احزاب
    "sec_elections": "1",
    "election_interval_hours": "48",          # فاصلهٔ انتخابات‌های دوره‌ای
    "election_campaign_cost_m": "25",         # هزینهٔ هر رأی تبلیغاتی (میلیون)
    "election_bonus_step": "0.35",            # اثر هر رأی تبلیغاتی
    "election_opposition_threshold": "55",    # از این درصد، اپوزیسیون برنده می‌شود
    "election_party_income_bonus": "0.05",    # پاداش حزب حاکم بر درآمد
    # ۴) 🕵 جاسوسی و مه اطلاعات
    "sec_intel": "1",
    "intel_cost_m": "12",                     # هزینهٔ هر عملیات جاسوسی (میلیون)
    "intel_radius_base": "0.35",              # پهنای بازهٔ برآورد (پایه)
    "intel_radius_step": "0.05",              # کاهش پهنای بازه به ازای هر سطح
    "intel_max_level": "5",                   # سقف سطح شبکهٔ اطلاعاتی
    "intel_expose_chance": "25",              # شانس لو رفتن جاسوس (٪)
    "intel_expire_hours": "12",               # اعتبار گزارش جاسوسی (ساعت)
    # ۷) 🛢 بازار جهانی نفت
    "sec_oil_market": "1",
    "oil_market_base_usd": "80",              # قیمت پایهٔ هر بشکه (دلار)
    "oil_market_shock_war_pct": "12",         # جهش قیمت با هر جنگ تمام‌عیار
    "oil_market_shock_blockade_pct": "18",    # جهش قیمت با بسته‌شدن هر تنگه
    "oil_market_drift_pct": "3",              # نوسان تصادفی بازار (٪)
    "oil_market_min_usd": "35",               # کف قیمت
    "oil_market_max_usd": "180",              # سقف قیمت
    "oil_market_income_weight": "0.75",       # وزن اثر قیمت روی درآمد نفتی
    # ۵) 🏃 پناهندگان و فرار مغزها
    "sec_refugees": "1",
    "refugee_pct_per_province": "0.05",       # سهم جمعیت هر استان اشغال‌شده
    "refugee_pct_per_hit": "0.02",            # سهم جمعیت هر قطعی/بمباران
    "refugee_return_cost_m": "10",            # هزینهٔ اسکان هر ۱۰۰۰ پناهنده (میلیون)
    "refugee_satisfaction_hit": "1.5",        # افت رضایت میزبان با پذیرش
    # ۸) 📡 پایگاه نظامی خارجی
    "sec_foreign_base": "1",
    "fbase_pay_m": "60",                      # درآمد میزبان از هر پایگاه (میلیون بر دوره)
    "fbase_defense_bonus_pct": "20",          # بونوس دفاعی میزبان از حضور مهمان
    "fbase_tech_bonus_pct": "5",              # بونوس قدرت مهمان از حضور در پایگاه
    "fbase_crisis_sat": "10",                 # افت رضایت میزبان با لغو پایگاه
    "fbase_crisis_diplomacy": "15",           # افت روابط عمومی میزبان با لغو
    "fbase_auto_join": "1",                   # ورود خودکار مهمان به جنگ میزبان
    # ۹) ⚡ حملهٔ سایبری با اثر آبشاری
    "sec_grideffect": "1",
    "grid_hours_per_success": "6",            # قطعی برق به ازای هر خرابکاری موفق
    "grid_max_hours": "24",
    "grid_income_penalty_pct": "6",           # افت درآمد به ازای هر ساعت قطعی (٪)
    "grid_repair_cost_m_per_hour": "12",      # هزینهٔ خاموش‌نماندن (ترمیم اضطراری)
    "grid_satisfaction_hit": "1.2",           # افت رضایت به ازای هر ساعت
    # ۱۰) 🍁 فصل‌ها و آب‌وهوا
    "sec_weather": "1",
    "weather_season_hours": "24",             # طول هر فصل در بازی
    "weather_winter_attack_pct": "12",        # کندی عملیات در زمستان (٪)
    "weather_winter_energy_pct": "18",        # مصرف بیشتر انرژی در زمستان (٪)
    "weather_summer_water_pct": "15",         # افت آب در تابستان (٪)
    "weather_drought_chance": "20",           # شانس خشکسالی در تابستان (٪)
    "weather_storm_chance": "15",             # شانس طوفان در پاییز (٪)
    "weather_storm_attack_pct": "10",         # کندی حمله در طوفان (٪)
    "weather_harvest_bonus_m": "25",          # بونوس برداشت در پاییز (میلیون)
    # ═══ ☢️ سلاح هسته‌ای (کلاهک) ═══
    "nuke_bomb_cost_m": "1800",              # هزینهٔ ساخت هر کلاهک (میلیون)
    "nuke_bomb_materials": "40000",          # مصالح لازم هر کلاهک
    "nuke_bomb_coins": "25",                 # سکه شاهی هر کلاهک
    "nuke_bomb_minutes": "30",               # زمان ساخت هر کلاهک (دقیقه)
    "nuke_bomb_yield_kt": "150",             # قدرت هر کلاهک (کیلوتن)
    "nuke_bomb_limit": "8",                  # حداکثر کلاهک در زرادخانه
    "nuke_strike_cooldown_hours": "12",      # فاصلهٔ لازم بین دو حملهٔ هسته‌ای
    "nuke_blast_provinces": "40",            # درصد احتمال جدا شدن هر استان
    "nuke_blast_max_provinces": "2",         # حداکثر استان جداشده در یک حمله
    "nuke_blast_loot_percent": "25",         # درصد غارت خزانهٔ هدف
    "nuke_blast_wear": "35",                 # فرسایش اضافه‌شده به کشور هدف
    "nuke_blast_satisfaction": "45",         # افت رضایت کشور هدف
    "nuke_blast_civilian": "900000",         # تلفات غیرنظامی تخمینی (نفر)
    "nuke_fallout_self": "6",                # افت رضایت خود مهاجم (جهانی محکوم می‌شود)
    "nuke_catastrophe_chance": "6",          # احتمال تبدیل به فاجعهٔ انسانی (کلاهک منفجر نمی‌شود؟)
    "battle_reserve_loss_percent": "2",     # 🎯 فرسایش ذخیره‌گاه در نبرد (٪)
    "battle_defender_kill_ratio": "1.5",    # 🎯 سقف تلفات مدافع به ازای هر یگان مهاجم
    "nuke_global_condemn": "1",              # ۱ = همهٔ کشورها هزینهٔ سیاسی می‌دهند
    # ═══ 🛡 امنیت عملیاتی ═══
    "security_alert_to": "",                   # آیدی‌های هشدار امنیتی (با کاما)
    "broadcast_lock_until": "",                 # اگر پر باشد، پیام همگانی قفل است
    "broadcast_require_code": "1",              # ۱ = کد تأیید ۴رقمی لازم است
    "broadcast_max_per_hour": "1",              # حداکثر ارسال همگانی در ساعت
    "broadcast_max_recipients": "0",            # ۰ = بی‌سقف؛ وگرنه سقف گیرنده در هر ارسال
    "broadcast_delay_ms": "60",                 # فاصلهٔ ارسال هر پیام (ضد محدودیت تلگرام)
    "security_notify_fail_auth": "1",           # هشدار هنگام تلاش ناموفق ورود
    "security_auto_lock_on_spam": "1",          # قفل خودکار همگانی با تکرار مشکوک
}
